"""Utility functions for httptap.

This module provides helper functions for common operations like
masking sensitive data, parsing headers, URL validation, and SSL context
management.
"""

import json
import os
import re
import socket
import ssl
from collections.abc import Collection, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

__all__ = [
    "MASK_PATTERN",
    "SENSITIVE_HEADERS",
    "URL_HEADERS",
    "UTC",
    "calculate_days_until",
    "create_ssl_context",
    "format_address_family",
    "mask_sensitive_value",
    "parse_certificate_date",
    "parse_http_date",
    "read_request_data",
    "redact_url_credentials",
    "sanitize_headers",
    "url_hostname",
    "url_validation_error",
    "validate_url",
]

SENSITIVE_HEADERS: set[str] = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "api-key",
    "x-api-key",
}

# Headers whose value is a URL; only the userinfo of these is masked.
URL_HEADERS: set[str] = {"location", "content-location"}

MASK_PATTERN = "****"


def mask_sensitive_value(value: str, show_chars: int = 4) -> str:
    """Mask sensitive value showing only first and last characters.

    Args:
        value: The value to mask.
        show_chars: Number of characters to show at start and end.

    Returns:
        Masked value like "abc****xyz" or "****" if too short.

    Examples:
        >>> mask_sensitive_value("Bearer token123456")
        'Bear****3456'
        >>> mask_sensitive_value("short")
        '****'

    """
    if len(value) <= show_chars * 2:
        return MASK_PATTERN

    return f"{value[:show_chars]}{MASK_PATTERN}{value[-show_chars:]}"


# RFC 3986, appendix B: the optional scheme followed by "//" that precedes the authority.
_URL_AUTHORITY_PREFIX_RE = re.compile(r"(?:[^:/?#]+:)?//")


def redact_url_credentials(url: str) -> str:
    """Mask the password (or a bare token) in the userinfo part of a URL.

    The authority is located textually rather than with ``urlsplit`` so that
    malformed URLs (an unterminated IPv6 literal, an invalid port) are still
    redacted instead of raising, which matters when they are echoed in errors.

    Args:
        url: URL that may contain ``user:password@`` credentials.

    Returns:
        URL with the password replaced by the mask, or the original URL
        when it has no userinfo.

    Examples:
        >>> redact_url_credentials("http://user:secret@proxy:3128")
        'http://user:****@proxy:3128'
        >>> redact_url_credentials("socks5h://token@gateway:1080")
        'socks5h://****@gateway:1080'
        >>> redact_url_credentials("http://proxy:3128")
        'http://proxy:3128'
        >>> redact_url_credentials("user:secret@proxy:3128")
        'user:****@proxy:3128'

    """
    # Without a "//" prefix the leading segment is taken as the authority, so
    # scheme-less proxy values such as ``user:pass@host:3128`` are masked too.
    prefix = _URL_AUTHORITY_PREFIX_RE.match(url)
    start = prefix.end() if prefix else 0
    end = next((index for index in range(start, len(url)) if url[index] in "/?#"), len(url))
    userinfo, separator, hostport = url[start:end].rpartition("@")
    if not separator:
        return url

    username, has_password, _ = userinfo.partition(":")
    masked = f"{username}:{MASK_PATTERN}" if has_password else MASK_PATTERN
    return f"{url[:start]}{masked}@{hostport}{url[end:]}"


def sanitize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Sanitize HTTP headers by masking sensitive values.

    Args:
        headers: Dictionary of HTTP headers.

    Returns:
        New dictionary with sensitive values masked and URL credentials in
        ``Location``-style headers redacted.

    Examples:
        >>> sanitize_headers({"Authorization": "Bearer secret"})
        {'Authorization': 'Bear****cret'}
        >>> sanitize_headers({"Location": "https://user:secret@example.com/"})
        {'Location': 'https://user:****@example.com/'}

    """
    sanitized = {}
    for key, value in headers.items():
        name = key.lower()
        if name in SENSITIVE_HEADERS:
            sanitized[key] = mask_sensitive_value(value)
        elif name in URL_HEADERS:
            sanitized[key] = redact_url_credentials(value)
        else:
            sanitized[key] = value
    return sanitized


def parse_http_date(date_str: str) -> datetime | None:
    """Parse HTTP date header to datetime.

    Supports RFC 7231 HTTP-date format.

    Args:
        date_str: Date string from HTTP Date header.

    Returns:
        Parsed datetime in UTC or None if parsing fails.

    Examples:
        >>> parse_http_date("Mon, 22 Oct 2025 12:00:00 GMT")
        datetime.datetime(2025, 10, 22, 12, 0, tzinfo=UTC)

    """
    try:
        # RFC 7231 format: "Mon, 22 Oct 2025 12:00:00 GMT"
        http_date = date_str.replace("GMT", "+0000")
        parsed = datetime.strptime(
            http_date,
            "%a, %d %b %Y %H:%M:%S %z",
        )
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def parse_certificate_date(date_str: str) -> datetime | None:
    """Parse certificate date to datetime.

    Args:
        date_str: Certificate date string (e.g., "Oct 22 12:00:00 2025 GMT").

    Returns:
        Parsed datetime in UTC or None if parsing fails.

    """
    try:
        # Certificate format: "Oct 22 12:00:00 2025 GMT"
        cert_date = date_str.replace("GMT", "+0000")
        parsed = datetime.strptime(
            cert_date,
            "%b %d %H:%M:%S %Y %z",
        )
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def calculate_days_until(target_date: datetime) -> int:
    """Calculate days from now until target date.

    Args:
        target_date: Target datetime in UTC.

    Returns:
        Number of days until target (negative if in past).

    """
    now = datetime.now(UTC)
    return (target_date - now).days


def format_address_family(family: int) -> str:
    """Return a human-readable label for a socket address family.

    Args:
        family: Numeric socket address family (e.g., ``socket.AF_INET``).

    Returns:
        ``"IPv4"``, ``"IPv6"``, or ``"AF_<num>"`` for any other family.

    """
    if family == socket.AF_INET6:
        return "IPv6"
    if family == socket.AF_INET:
        return "IPv4"
    return f"AF_{family}"


def create_ssl_context(*, verify_ssl: bool, ca_bundle_path: str | None = None) -> ssl.SSLContext:
    """Return an SSL context honoring the requested verification policy.

    Args:
        verify_ssl: Whether to enforce certificate validation and modern
            security defaults.
        ca_bundle_path: Path to custom CA certificate bundle file (PEM format).
            Only used when verify_ssl is True. If None, uses system CA bundle.

    Returns:
        Configured ``ssl.SSLContext`` instance.
    """
    if verify_ssl:
        context = ssl.create_default_context()

        if ca_bundle_path:
            try:
                context.load_verify_locations(cafile=ca_bundle_path)
            except (ssl.SSLError, FileNotFoundError, PermissionError, OSError) as e:
                msg = f"Failed to load CA bundle from '{ca_bundle_path}': {e}"
                raise ValueError(msg) from e

        return context

    # For legacy mode create a mutable context allowing older protocols.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    # Allow legacy cipher suites / key sizes (e.g., RC4, small DH groups)
    with suppress(ssl.SSLError):  # pragma: no cover - platform dependent
        context.set_ciphers("ALL:@SECLEVEL=0")

    # Permit older protocol versions to assist with legacy endpoints
    if hasattr(context, "minimum_version") and hasattr(ssl, "TLSVersion"):
        context.minimum_version = ssl.TLSVersion.MINIMUM_SUPPORTED
    if hasattr(context, "maximum_version") and hasattr(ssl, "TLSVersion"):
        context.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED

    if hasattr(ssl, "OP_NO_SSLv3"):
        context.options &= ~ssl.OP_NO_SSLv3  # pragma: no cover - platform dependent
    if hasattr(ssl, "OP_NO_TLSv1"):
        context.options &= ~ssl.OP_NO_TLSv1
    if hasattr(ssl, "OP_NO_TLSv1_1"):
        context.options &= ~ssl.OP_NO_TLSv1_1

    return context


CONTENT_TYPE_BY_EXTENSION = {
    ".json": "application/json",
    ".xml": "application/xml",
    ".txt": "text/plain",
    ".text": "text/plain",
}


def _load_data_from_source(data_arg: str) -> tuple[bytes, Path | None]:
    """Load data from inline string or file reference.

    Inline data is converted back to the exact bytes given on the command
    line: ``os.fsencode`` reverses the ``surrogateescape`` decoding of argv,
    so arguments that are not valid UTF-8 are sent unchanged.
    """
    if data_arg.startswith("@"):
        filepath = Path(data_arg[1:])
        return filepath.read_bytes(), filepath
    return os.fsencode(data_arg), None


def _detect_content_type_from_extension(source: Path) -> str | None:
    """Detect Content-Type based on file extension."""
    return CONTENT_TYPE_BY_EXTENSION.get(source.suffix)


def _is_json_data(data: bytes) -> bool:
    """Check if data is valid JSON."""
    try:
        json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    else:
        return True


def _detect_content_type(data: bytes, source: Path | None) -> str | None:
    """Detect Content-Type using multiple strategies."""
    if source and (content_type := _detect_content_type_from_extension(source)):
        return content_type

    if _is_json_data(data):
        return "application/json"

    return None


def read_request_data(data_arg: str | None) -> tuple[bytes | None, dict[str, str]]:
    """Read request body data and auto-detect Content-Type.

    Supports inline data or reading from file using @filename syntax.
    Automatically detects JSON content and sets appropriate Content-Type.

    Args:
        data_arg: Request body data string, or @filename to read from file, or None.

    Returns:
        Tuple of (content_bytes, headers_to_add) where headers_to_add contains
        Content-Type if it could be auto-detected.

    Raises:
        FileNotFoundError: If @filename is specified but file doesn't exist.
        OSError: If file cannot be read.

    Examples:
        >>> content, headers = read_request_data('{"name": "John"}')
        >>> content
        b'{"name": "John"}'
        >>> headers
        {'Content-Type': 'application/json'}

        >>> content, headers = read_request_data(None)
        >>> content is None
        True
        >>> headers
        {}

    """
    if not data_arg:
        return None, {}

    data, source = _load_data_from_source(data_arg)
    content_type = _detect_content_type(data, source)

    headers = {"Content-Type": content_type} if content_type else {}
    return data, headers


_WHITESPACE_RE = re.compile(r"\s")


def validate_url(url: str) -> bool:
    """Validate URL format.

    Requires an http/https scheme and a non-empty host. A scheme alone is not
    enough: ``https:///path`` and ``https://?query`` parse to an empty host and
    would fail at connection time with an opaque error, so they are rejected
    here where the message can be actionable.

    Args:
        url: URL string to validate.

    Returns:
        True if URL is valid HTTP/HTTPS URL, False otherwise.

    Examples:
        >>> validate_url("https://example.com")
        True
        >>> validate_url("ftp://example.com")
        False
        >>> validate_url("https://")
        False
        >>> validate_url("https:///path")
        False
        >>> validate_url("http://127.0.0.1:99999/")
        False

    """
    if _WHITESPACE_RE.search(url):
        return False
    # Same rules as url_validation_error, without building messages on this hot path.
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in _HTTP_SCHEMES or not parts.hostname:
        return False
    try:
        return parts.port != 0
    except ValueError:
        return False


def url_hostname(url: str) -> str:
    """Return the lowercase hostname of ``url``, or ``""`` when it has none or cannot be parsed.

    Examples:
        >>> url_hostname("https://Example.com:8443/path")
        'example.com'
        >>> url_hostname("http://[::1/path")
        ''

    """
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


_HTTP_SCHEMES = frozenset({"http", "https"})


def url_validation_error(url: str, schemes: Collection[str]) -> str | None:
    """Explain why ``url`` is not an absolute URL usable for a connection.

    Args:
        url: URL string to check.
        schemes: Accepted lowercase schemes.

    Returns:
        A short reason (malformed authority, unsupported scheme, missing host,
        invalid port), or ``None`` when the URL is usable.

    Examples:
        >>> url_validation_error("http://127.0.0.1:99999/", {"http"})
        'Port out of range 0-65535'
        >>> url_validation_error("ftp://example.com/", {"http", "https"})
        "unsupported scheme 'ftp'"
        >>> url_validation_error("https://example.com/", {"http", "https"}) is None
        True

    """
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        # Malformed authority, e.g. an unterminated IPv6 literal.
        return str(exc)

    if parts.scheme not in schemes:
        return f"unsupported scheme {parts.scheme!r}" if parts.scheme else "missing scheme"
    if not parts.hostname:
        return "missing host"
    return _port_error(parts)


def _port_error(parts: SplitResult) -> str | None:
    """Return why the port of ``parts`` is unusable, or ``None`` if it is fine."""
    try:
        # ``port`` is parsed lazily and raises for non-numeric or out-of-range values.
        port = parts.port
    except ValueError as exc:
        return str(exc)
    if port == 0:
        return "port must be between 1 and 65535"
    return None
