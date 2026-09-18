"""TLS certificate inspection functionality.

This module provides utilities for extracting and analyzing TLS certificate
information from SSL connections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol, overload, runtime_checkable

from cryptography import x509
from cryptography.x509.oid import NameOID

from .utils import calculate_days_until, parse_certificate_date

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from .models import NetworkInfo


@runtime_checkable
class SSLObjectLike(Protocol):
    """Structural type for any object exposing the SSL inspection surface.

    This intentionally matches every peer object httpcore hands back through
    ``network_stream.get_extra_info`` — the high-level :class:`ssl.SSLSocket`
    and :class:`ssl.SSLObject`, as well as the low-level ``_ssl._SSLSocket``
    returned by the sync backend. All three implement the same methods, so
    callers duck-type against this protocol instead of branching on the
    concrete class (which previously caused certificate data to be dropped for
    every object that was not exactly an :class:`ssl.SSLSocket`).
    """

    def version(self) -> str | None:
        """Return the negotiated TLS protocol version."""

    def cipher(self) -> tuple[Any, ...] | None:
        """Return the active cipher suite description."""

    @overload
    def getpeercert(
        self,
        binary_form: Literal[False] = False,  # noqa: FBT002
    ) -> Mapping[str, Any] | None: ...

    @overload
    def getpeercert(self, binary_form: Literal[True]) -> bytes | None: ...

    @overload
    def getpeercert(
        self,
        binary_form: bool,  # noqa: FBT001
    ) -> Mapping[str, Any] | bytes | None: ...


class TLSInspectionError(Exception):
    """Raised when TLS inspection fails."""


class CertificateInfo:
    """TLS certificate information.

    Attributes:
        common_name: Certificate Common Name (CN).
        subject_alt_names: List of Subject Alternative Names.
        issuer: Certificate issuer.
        not_before: Certificate validity start date.
        not_after: Certificate validity end date.
        days_until_expiry: Days until certificate expires.
        serial_number: Certificate serial number.

    """

    __slots__ = (
        "common_name",
        "days_until_expiry",
        "issuer",
        "not_after",
        "not_before",
        "serial_number",
        "subject_alt_names",
    )

    def __init__(self, cert_dict: dict[str, Any]) -> None:
        """Initialize certificate info from SSL certificate dictionary.

        Args:
            cert_dict: Certificate dictionary from ssl.SSLSocket.getpeercert().

        Raises:
            TLSInspectionError: If certificate data is invalid.

        """
        self.common_name = self._extract_common_name(cert_dict)
        self.subject_alt_names = self._extract_san(cert_dict)
        self.issuer = self._extract_issuer(cert_dict)
        self.not_before = self._parse_date(cert_dict.get("notBefore"))
        self.not_after = self._parse_date(cert_dict.get("notAfter"))
        self.days_until_expiry = self._calculate_days_left()
        self.serial_number = cert_dict.get("serialNumber")

    @staticmethod
    def _extract_common_name(cert_dict: dict[str, Any]) -> str | None:
        """Extract Common Name from certificate subject.

        Args:
            cert_dict: Certificate dictionary.

        Returns:
            Common Name or None if not found.

        """
        subject = cert_dict.get("subject", ())
        for entry in subject:
            for key, value in entry:
                if key == "commonName":
                    return str(value)
        return None

    @staticmethod
    def _extract_san(cert_dict: dict[str, Any]) -> list[str]:
        """Extract Subject Alternative Names from certificate.

        Args:
            cert_dict: Certificate dictionary.

        Returns:
            List of SAN entries (DNS names).

        """
        san_list = []
        san = cert_dict.get("subjectAltName", ())
        for san_type, san_value in san:
            if san_type == "DNS":
                san_list.append(str(san_value))
        return san_list

    @staticmethod
    def _extract_issuer(cert_dict: dict[str, Any]) -> str | None:
        """Extract issuer Common Name from certificate.

        Args:
            cert_dict: Certificate dictionary.

        Returns:
            Issuer CN or None if not found.

        """
        issuer = cert_dict.get("issuer", ())
        for entry in issuer:
            for key, value in entry:
                if key == "commonName":
                    return str(value)
        return None

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse certificate date string.

        Args:
            date_str: Date string from certificate.

        Returns:
            Parsed datetime or None if parsing fails.

        """
        if not date_str:
            return None
        return parse_certificate_date(date_str)

    def _calculate_days_left(self) -> int | None:
        """Calculate days until certificate expiration.

        Returns:
            Days until expiry (negative if expired) or None if date unavailable.

        """
        if not self.not_after:
            return None
        return calculate_days_until(self.not_after)

    @classmethod
    def from_der(cls, cert_der: bytes) -> CertificateInfo:
        """Build certificate information from a DER-encoded certificate.

        ``ssl.SSLSocket.getpeercert()`` returns an empty dictionary when
        verification is disabled, but the binary form remains available.

        Args:
            cert_der: DER-encoded peer certificate.

        Returns:
            Parsed certificate information.

        Raises:
            ValueError: If ``cert_der`` is not a valid X.509 certificate.

        """
        certificate = x509.load_der_x509_certificate(cert_der)
        cert_info = cls.__new__(cls)
        cert_info.common_name = cls._x509_common_name(certificate.subject)
        cert_info.subject_alt_names = cls._x509_subject_alt_names(certificate)
        cert_info.issuer = cls._x509_common_name(certificate.issuer)
        cert_info.not_before = certificate.not_valid_before_utc
        cert_info.not_after = certificate.not_valid_after_utc
        cert_info.days_until_expiry = calculate_days_until(cert_info.not_after)
        cert_info.serial_number = format(certificate.serial_number, "X")
        return cert_info

    @staticmethod
    def _x509_common_name(name: x509.Name) -> str | None:
        """Extract a common name from an X.509 subject or issuer."""
        attributes = name.get_attributes_for_oid(NameOID.COMMON_NAME)
        return str(attributes[0].value) if attributes else None

    @staticmethod
    def _x509_subject_alt_names(certificate: x509.Certificate) -> list[str]:
        """Extract DNS subject alternative names from an X.509 certificate."""
        try:
            extension = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        except x509.ExtensionNotFound:
            return []
        return list(extension.value.get_values_for_type(x509.DNSName))


def apply_certificate_info(network_info: NetworkInfo, cert_info: CertificateInfo) -> None:
    """Copy parsed certificate fields onto a :class:`NetworkInfo`.

    Existing values are preserved: each target field is only filled when it is
    still unset, so metadata already captured from another source (for example
    the live connection) is never clobbered by a later fallback probe.

    Args:
        network_info: Destination metadata container to enrich in place.
        cert_info: Parsed certificate details to copy from.

    """
    network_info.cert_cn = network_info.cert_cn or cert_info.common_name
    if network_info.cert_days_left is None:
        network_info.cert_days_left = cert_info.days_until_expiry
    network_info.cert_sans = network_info.cert_sans or list(cert_info.subject_alt_names)
    network_info.cert_issuer = network_info.cert_issuer or cert_info.issuer
    network_info.cert_serial = network_info.cert_serial or cert_info.serial_number
    network_info.cert_not_before = network_info.cert_not_before or cert_info.not_before
    network_info.cert_not_after = network_info.cert_not_after or cert_info.not_after


def extract_certificate_info(ssl_object: SSLObjectLike) -> CertificateInfo | None:
    """Extract certificate information from a live SSL object.

    Args:
        ssl_object: Any connected SSL object exposing ``getpeercert`` — an
            :class:`ssl.SSLSocket`, :class:`ssl.SSLObject`, or the low-level
            ``_ssl._SSLSocket`` handed back by httpcore's sync backend.

    Returns:
        CertificateInfo object or None if certificate unavailable (e.g. when
        verification is disabled and the peer certificate is not surfaced as a
        parsed dictionary).

    Raises:
        TLSInspectionError: If certificate extraction fails.

    """
    try:
        cert_dict = ssl_object.getpeercert()
        if cert_dict:
            return CertificateInfo(dict(cert_dict))

        cert_der = ssl_object.getpeercert(binary_form=True)
        return CertificateInfo.from_der(cert_der) if isinstance(cert_der, bytes) and cert_der else None
    except Exception as e:
        msg = f"Failed to extract certificate info: {e}"
        raise TLSInspectionError(msg) from e


def extract_tls_info(
    ssl_socket: SSLObjectLike,
) -> tuple[str | None, str | None, CertificateInfo | None]:
    """Extract TLS version, cipher, and certificate information.

    Args:
        ssl_socket: Connected SSL socket.

    Returns:
        Tuple of (tls_version, cipher_suite, certificate_info).

    Examples:
        >>> with context.wrap_socket(sock, server_hostname=host) as tls_sock:
        ...     version, cipher, cert_info = extract_tls_info(tls_sock)
        ...     print(f"TLS: {version}, Cipher: {cipher}")
        TLS: TLSv1.3, Cipher: TLS_AES_256_GCM_SHA384

    """
    try:
        tls_version = ssl_socket.version()
        cipher_info = ssl_socket.cipher()
        cipher_suite = cipher_info[0] if cipher_info else None
        cert_info = extract_certificate_info(ssl_socket)
    except Exception as e:
        msg = f"Failed to extract TLS info: {e}"
        raise TLSInspectionError(msg) from e

    return tls_version, cipher_suite, cert_info
