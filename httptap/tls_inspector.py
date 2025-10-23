"""TLS certificate inspection functionality.

This module provides utilities for extracting and analyzing TLS certificate
information from SSL connections.
"""

import ssl
from datetime import datetime
from typing import Any

from .utils import calculate_days_until, parse_certificate_date


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


def extract_certificate_info(ssl_socket: ssl.SSLSocket) -> CertificateInfo | None:
    """Extract certificate information from SSL socket.

    Args:
        ssl_socket: Connected SSL socket.

    Returns:
        CertificateInfo object or None if certificate unavailable.

    Raises:
        TLSInspectionError: If certificate extraction fails.

    """
    try:
        cert_dict = ssl_socket.getpeercert()
        if not cert_dict:
            return None
        return CertificateInfo(cert_dict)
    except Exception as e:
        msg = f"Failed to extract certificate info: {e}"
        raise TLSInspectionError(msg) from e


def extract_tls_info(
    ssl_socket: ssl.SSLSocket,
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
        # Extract TLS version
        tls_version = ssl_socket.version()

        # Extract cipher suite
        cipher_info = ssl_socket.cipher()
        cipher_suite = cipher_info[0] if cipher_info else None

        # Extract certificate info
        cert_info = extract_certificate_info(ssl_socket)
    except Exception as e:
        msg = f"Failed to extract TLS info: {e}"
        raise TLSInspectionError(msg) from e

    return tls_version, cipher_suite, cert_info
