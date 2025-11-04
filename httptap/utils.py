"""Utility functions for httptap.

This module provides helper functions for common operations like
masking sensitive data, parsing headers, URL validation, and SSL context
management.
"""

import json
import re
import ssl
from collections.abc import Mapping
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - exercised indirectly
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # Python < 3.11 # pragma: no cover - exercised indirectly
    UTC = timezone.utc

__all__ = [
    "MASK_PATTERN",
    "SENSITIVE_HEADERS",
    "UTC",
    "calculate_days_until",
    "create_ssl_context",
    "mask_sensitive_value",
    "parse_certificate_date",
    "parse_http_date",
    "read_request_data",
    "sanitize_headers",
    "validate_url",
]

# Headers that should have their values masked for security
SENSITIVE_HEADERS: set[str] = {
    "authorization",
    "cookie",
    "set-cookie",
    "api-key",
    "x-api-key",
}

# Pattern for masking - show first 4 and last 4 characters
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


def sanitize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Sanitize HTTP headers by masking sensitive values.

    Args:
        headers: Dictionary of HTTP headers.

    Returns:
        New dictionary with sensitive values masked.

    Examples:
        >>> sanitize_headers({"Authorization": "Bearer secret"})
        {'Authorization': 'Bear****cret'}

    """
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            sanitized[key] = mask_sensitive_value(value)
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


def create_ssl_context(*, verify_ssl: bool) -> ssl.SSLContext:
    """Return an SSL context honoring the requested verification policy.

    Args:
        verify_ssl: Whether to enforce certificate validation and modern
            security defaults.

    Returns:
        Configured ``ssl.SSLContext`` instance.
    """
    if verify_ssl:
        return ssl.create_default_context()

    # For legacy mode create a mutable context allowing older protocols.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)

    # Disable certificate verification and hostname checks
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    # Allow legacy cipher suites / key sizes (e.g., RC4, small DH groups)
    with suppress(ssl.SSLError):  # pragma: no cover - platform dependent
        context.set_ciphers("ALL:@SECLEVEL=0")

    # Permit older protocol versions to assist with legacy endpoints
    if hasattr(context, "minimum_version") and hasattr(ssl, "TLSVersion"):
        context.minimum_version = getattr(ssl.TLSVersion, "SSLv3", ssl.TLSVersion.MINIMUM_SUPPORTED)
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
    """Load data from inline string or file reference."""
    if data_arg.startswith("@"):
        filepath = Path(data_arg[1:])
        return filepath.read_bytes(), filepath
    return data_arg.encode("utf-8"), None


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


def validate_url(url: str) -> bool:
    """Validate URL format.

    Args:
        url: URL string to validate.

    Returns:
        True if URL is valid HTTP/HTTPS URL, False otherwise.

    Examples:
        >>> validate_url("https://example.com")
        True
        >>> validate_url("ftp://example.com")
        False

    """
    return bool(re.match(r"^https?://", url))
