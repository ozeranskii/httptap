"""Unit tests for TLS certificate inspection utilities."""

from __future__ import annotations

import ssl
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from httptap.tls_inspector import (
    CertificateInfo,
    TLSInspectionError,
    extract_certificate_info,
    extract_tls_info,
)


class TestCertificateInfo:
    """Test suite for CertificateInfo class."""

    def test_init_with_complete_certificate(self) -> None:
        """Test initialization with complete certificate data."""
        not_before_str = "Oct 22 00:00:00 2024 GMT"
        not_after_str = "Oct 22 00:00:00 2026 GMT"

        cert_dict: dict[str, Any] = {
            "subject": ((("commonName", "example.com"),),),
            "subjectAltName": (("DNS", "example.com"), ("DNS", "www.example.com")),
            "issuer": ((("commonName", "Let's Encrypt"),),),
            "notBefore": not_before_str,
            "notAfter": not_after_str,
            "serialNumber": "ABC123",
        }

        cert_info = CertificateInfo(cert_dict)

        assert cert_info.common_name == "example.com"
        assert cert_info.subject_alt_names == ["example.com", "www.example.com"]
        assert cert_info.issuer == "Let's Encrypt"
        assert cert_info.not_before is not None
        assert cert_info.not_after is not None
        assert cert_info.serial_number == "ABC123"
        assert isinstance(cert_info.days_until_expiry, int)

    def test_extract_common_name_success(self) -> None:
        """Test extracting Common Name from certificate subject."""
        cert_dict: dict[str, Any] = {
            "subject": ((("countryName", "US"), ("commonName", "test.example.com")),),
        }

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.common_name == "test.example.com"

    def test_extract_common_name_missing(self) -> None:
        """Test extracting Common Name when not present."""
        cert_dict: dict[str, Any] = {
            "subject": ((("countryName", "US"),),),
        }

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.common_name is None

    def test_extract_common_name_empty_subject(self) -> None:
        """Test extracting Common Name with empty subject."""
        cert_dict: dict[str, Any] = {"subject": ()}

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.common_name is None

    def test_extract_san_multiple_entries(self) -> None:
        """Test extracting multiple Subject Alternative Names."""
        cert_dict: dict[str, Any] = {
            "subjectAltName": (
                ("DNS", "example.com"),
                ("DNS", "www.example.com"),
                ("DNS", "api.example.com"),
            ),
        }

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.subject_alt_names == [
            "example.com",
            "www.example.com",
            "api.example.com",
        ]

    def test_extract_san_empty(self) -> None:
        """Test extracting SAN when not present."""
        cert_dict: dict[str, Any] = {}

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.subject_alt_names == []

    def test_extract_san_filters_non_dns(self) -> None:
        """Test that non-DNS SAN entries are filtered out."""
        cert_dict: dict[str, Any] = {
            "subjectAltName": (
                ("DNS", "example.com"),
                ("IP Address", "93.184.216.34"),
                ("DNS", "www.example.com"),
            ),
        }

        cert_info = CertificateInfo(cert_dict)
        # Should only include DNS entries
        assert cert_info.subject_alt_names == ["example.com", "www.example.com"]

    def test_extract_issuer_success(self) -> None:
        """Test extracting issuer Common Name."""
        cert_dict: dict[str, Any] = {
            "issuer": ((("countryName", "US"), ("commonName", "DigiCert Global Root CA")),),
        }

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.issuer == "DigiCert Global Root CA"

    def test_extract_issuer_missing(self) -> None:
        """Test extracting issuer when not present."""
        cert_dict: dict[str, Any] = {
            "issuer": ((("countryName", "US"),),),
        }

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.issuer is None

    def test_parse_date_success(self) -> None:
        """Test parsing certificate date string."""
        cert_dict: dict[str, Any] = {
            "notBefore": "Oct 22 12:00:00 2024 GMT",
            "notAfter": "Oct 22 12:00:00 2025 GMT",
        }

        cert_info = CertificateInfo(cert_dict)

        assert cert_info.not_before is not None
        assert cert_info.not_before.year == 2024
        assert cert_info.not_before.month == 10
        assert cert_info.not_before.day == 22

    def test_parse_date_invalid_returns_none(self) -> None:
        """Test that invalid date strings return None."""
        cert_dict: dict[str, Any] = {
            "notBefore": "invalid date",
        }

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.not_before is None

    def test_parse_date_missing_returns_none(self) -> None:
        """Test that missing date fields return None."""
        cert_dict: dict[str, Any] = {}

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.not_before is None
        assert cert_info.not_after is None

    def test_calculate_days_left_future(self) -> None:
        """Test calculating days until expiry for future date."""
        # Certificate expires in 90 days
        future_date = datetime.now(UTC) + timedelta(days=90)
        future_str = future_date.strftime("%b %d %H:%M:%S %Y GMT")

        cert_dict: dict[str, Any] = {
            "notAfter": future_str,
        }

        cert_info = CertificateInfo(cert_dict)

        # Should be approximately 90 days (allow ±1 for timing)
        assert cert_info.days_until_expiry is not None
        assert 89 <= cert_info.days_until_expiry <= 90

    def test_calculate_days_left_expired(self) -> None:
        """Test calculating days for expired certificate (negative)."""
        # Certificate expired 10 days ago
        past_date = datetime.now(UTC) - timedelta(days=10)
        past_str = past_date.strftime("%b %d %H:%M:%S %Y GMT")

        cert_dict: dict[str, Any] = {
            "notAfter": past_str,
        }

        cert_info = CertificateInfo(cert_dict)

        # Should be negative (approximately -10, allow ±1 for timing/rounding)
        assert cert_info.days_until_expiry is not None
        assert -11 <= cert_info.days_until_expiry <= -9

    def test_calculate_days_left_missing_date(self) -> None:
        """Test that missing expiry date returns None."""
        cert_dict: dict[str, Any] = {}

        cert_info = CertificateInfo(cert_dict)
        assert cert_info.days_until_expiry is None


class TestExtractCertificateInfo:
    """Test suite for extract_certificate_info function."""

    def test_extract_certificate_info_success(self) -> None:
        """Test successful certificate info extraction."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.getpeercert.return_value = {
            "subject": ((("commonName", "example.com"),),),
            "notAfter": "Oct 22 12:00:00 2025 GMT",
        }

        cert_info = extract_certificate_info(mock_ssl_socket)

        assert cert_info is not None
        assert cert_info.common_name == "example.com"

    def test_extract_certificate_info_no_cert_returns_none(self) -> None:
        """Test that missing certificate returns None."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.getpeercert.return_value = None

        cert_info = extract_certificate_info(mock_ssl_socket)

        assert cert_info is None

    def test_extract_certificate_info_empty_dict_returns_none(self) -> None:
        """Test that empty certificate dict returns None."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.getpeercert.return_value = {}

        cert_info = extract_certificate_info(mock_ssl_socket)

        # Empty dict is falsy, should return None
        assert cert_info is None

    def test_extract_certificate_info_exception_raises_inspection_error(self) -> None:
        """Test that exceptions are wrapped in TLSInspectionError."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.getpeercert.side_effect = ssl.SSLError("Certificate error")

        with pytest.raises(TLSInspectionError, match="Failed to extract certificate"):
            extract_certificate_info(mock_ssl_socket)


class TestExtractTLSInfo:
    """Test suite for extract_tls_info function."""

    def test_extract_tls_info_complete(self) -> None:
        """Test extracting complete TLS information."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.version.return_value = "TLSv1.3"
        mock_ssl_socket.cipher.return_value = ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)
        mock_ssl_socket.getpeercert.return_value = {
            "subject": ((("commonName", "example.com"),),),
            "notAfter": "Oct 22 12:00:00 2025 GMT",
        }

        tls_version, cipher_suite, cert_info = extract_tls_info(mock_ssl_socket)

        assert tls_version == "TLSv1.3"
        assert cipher_suite == "TLS_AES_256_GCM_SHA384"
        assert cert_info is not None
        assert cert_info.common_name == "example.com"

    def test_extract_tls_info_no_cipher_returns_none(self) -> None:
        """Test that missing cipher info returns None for cipher."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.version.return_value = "TLSv1.2"
        mock_ssl_socket.cipher.return_value = None
        mock_ssl_socket.getpeercert.return_value = None

        tls_version, cipher_suite, cert_info = extract_tls_info(mock_ssl_socket)

        assert tls_version == "TLSv1.2"
        assert cipher_suite is None
        assert cert_info is None

    def test_extract_tls_info_empty_cipher_tuple(self) -> None:
        """Test that empty cipher tuple returns None."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.version.return_value = "TLSv1.2"
        mock_ssl_socket.cipher.return_value = ()
        mock_ssl_socket.getpeercert.return_value = None

        _tls_version, cipher_suite, _cert_info = extract_tls_info(mock_ssl_socket)

        assert cipher_suite is None

    def test_extract_tls_info_version_exception_raises_inspection_error(self) -> None:
        """Test that exceptions during TLS info extraction are wrapped."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.version.side_effect = ssl.SSLError("Version error")

        with pytest.raises(TLSInspectionError, match="Failed to extract TLS info"):
            extract_tls_info(mock_ssl_socket)

    def test_extract_tls_info_cipher_exception_raises_inspection_error(self) -> None:
        """Test that cipher exceptions are wrapped."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.version.return_value = "TLSv1.3"
        mock_ssl_socket.cipher.side_effect = RuntimeError("Cipher error")

        with pytest.raises(TLSInspectionError, match="Failed to extract TLS info"):
            extract_tls_info(mock_ssl_socket)

    def test_extract_tls_info_no_certificate(self) -> None:
        """Test TLS info extraction when certificate is not available."""
        mock_ssl_socket = MagicMock(spec=ssl.SSLSocket)
        mock_ssl_socket.version.return_value = "TLSv1.3"
        mock_ssl_socket.cipher.return_value = ("TLS_AES_128_GCM_SHA256", "TLSv1.3", 128)
        mock_ssl_socket.getpeercert.return_value = None

        tls_version, cipher_suite, cert_info = extract_tls_info(mock_ssl_socket)

        assert tls_version == "TLSv1.3"
        assert cipher_suite == "TLS_AES_128_GCM_SHA256"
        assert cert_info is None
