import ssl
from datetime import datetime, timezone
from pathlib import Path

import pytest
from faker import Faker

from httptap.utils import (
    UTC,
    calculate_days_until,
    create_ssl_context,
    mask_sensitive_value,
    parse_certificate_date,
    parse_http_date,
    read_request_data,
    sanitize_headers,
    validate_url,
)


class TestMaskSensitiveValue:
    """Test suite for mask_sensitive_value function."""

    def test_mask_long_value_shows_first_and_last_chars(
        self,
        faker: Faker,
    ) -> None:
        """Test masking long values shows first and last characters."""
        value = faker.pystr(min_chars=12, max_chars=24)

        result = mask_sensitive_value(value, show_chars=4)

        assert result == f"{value[:4]}****{value[-4:]}"

    def test_mask_short_value_returns_full_mask(
        self,
        faker: Faker,
    ) -> None:
        """Test that short values are fully masked."""
        value = faker.pystr(min_chars=1, max_chars=7)
        result = mask_sensitive_value(value, show_chars=4)
        assert result == "****"

    def test_mask_exact_length_returns_full_mask(
        self,
        faker: Faker,
    ) -> None:
        """Test that values exactly 2*show_chars long are fully masked."""
        value = faker.pystr(min_chars=8, max_chars=8)
        result = mask_sensitive_value(value, show_chars=4)
        assert result == "****"

    def test_mask_custom_show_chars(self, faker: Faker) -> None:
        """Test masking with custom show_chars parameter."""
        value = faker.pystr(min_chars=10, max_chars=16)
        result = mask_sensitive_value(value, show_chars=2)
        assert result == f"{value[:2]}****{value[-2:]}"

    def test_mask_very_long_value(self) -> None:
        """Test masking very long values."""
        long_value = "x" * 100
        result = mask_sensitive_value(long_value, show_chars=4)
        assert result.startswith("xxxx")
        assert result.endswith("xxxx")
        assert "****" in result


class TestSanitizeHeaders:
    """Test suite for sanitize_headers function."""

    @pytest.mark.parametrize(
        "header",
        ["Authorization", "Cookie", "Set-Cookie"],
    )
    def test_sanitize_headers_masks_sensitive_values(
        self,
        faker: Faker,
        header: str,
    ) -> None:
        """Test that sensitive headers are masked."""
        headers = {
            header: faker.pystr(min_chars=8, max_chars=16),
            "X-Trace": faker.pystr(min_chars=6, max_chars=12),
        }
        sanitized = sanitize_headers(headers)
        assert sanitized[header] != headers[header]
        assert sanitized["X-Trace"] == headers["X-Trace"]

    def test_sanitize_headers_case_insensitive(self, faker: Faker) -> None:
        """Test that header matching is case-insensitive."""
        headers = {
            "authorization": faker.pystr(min_chars=8, max_chars=16),
            "COOKIE": faker.pystr(min_chars=8, max_chars=16),
            "SeT-CoOkIe": faker.pystr(min_chars=8, max_chars=16),
        }
        sanitized = sanitize_headers(headers)

        # All should be masked (case-insensitive matching)
        assert sanitized["authorization"] != "Bearer token"
        assert sanitized["COOKIE"] != "session=123"
        assert sanitized["SeT-CoOkIe"] != "auth=456"

    def test_sanitize_headers_preserves_non_sensitive(self, faker: Faker) -> None:
        """Test that non-sensitive headers are preserved."""
        headers = {
            "Content-Type": faker.mime_type(),
            "User-Agent": faker.user_agent(),
            "X-Custom": faker.pystr(min_chars=4, max_chars=12),
        }
        sanitized = sanitize_headers(headers)

        assert sanitized == headers

    def test_sanitize_headers_empty_dict(self) -> None:
        """Test sanitizing empty headers dictionary."""
        sanitized = sanitize_headers({})
        assert sanitized == {}

    def test_sanitize_headers_api_key_variants(self, faker: Faker) -> None:
        """Test that API key header variants are masked."""
        headers = {
            "api-key": faker.pystr(min_chars=10, max_chars=16),
            "x-api-key": faker.pystr(min_chars=10, max_chars=16),
        }
        sanitized = sanitize_headers(headers)

        assert sanitized["api-key"] != "secret123"
        assert sanitized["x-api-key"] != "secret456"


class TestParseHttpDate:
    """Test suite for parse_http_date function."""

    def test_parse_valid_http_date(self, faker: Faker) -> None:
        """Test parsing valid RFC 7231 HTTP date."""
        date = faker.date_time(tzinfo=UTC).replace(microsecond=0)
        date_str = date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        result = parse_http_date(date_str)

        assert result is not None
        assert result == date
        assert result.tzinfo == UTC

    def test_parse_invalid_http_date_returns_none(self, faker: Faker) -> None:
        """Test that invalid date format returns None."""
        result = parse_http_date(faker.sentence())
        assert result is None

    def test_parse_http_date_wrong_format_returns_none(self, faker: Faker) -> None:
        """Test that wrong date format returns None."""
        result = parse_http_date(faker.iso8601())
        assert result is None

    def test_parse_http_date_missing_gmt_returns_none(self, faker: Faker) -> None:
        """Test that dates without GMT suffix return None."""
        date = faker.date_time(tzinfo=timezone.utc).replace(microsecond=0)
        result = parse_http_date(
            date.strftime("%a, %d %b %Y %H:%M:%S UTC"),
        )
        assert result is None


class TestParseCertificateDate:
    """Test suite for parse_certificate_date function."""

    def test_parse_valid_certificate_date(self, faker: Faker) -> None:
        """Test parsing valid certificate date format."""
        date = faker.date_time(tzinfo=UTC).replace(microsecond=0)
        date_str = date.strftime("%b %d %H:%M:%S %Y GMT")
        result = parse_certificate_date(date_str)

        assert result is not None
        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day
        assert result.hour == date.hour
        assert result.tzinfo == UTC

    def test_parse_invalid_certificate_date_returns_none(
        self,
        faker: Faker,
    ) -> None:
        """Test that invalid certificate date returns None."""
        result = parse_certificate_date(faker.sentence())
        assert result is None

    def test_parse_certificate_date_wrong_format_returns_none(
        self,
        faker: Faker,
    ) -> None:
        """Test that wrong format returns None."""
        result = parse_certificate_date(faker.iso8601())
        assert result is None


class TestCalculateDaysUntil:
    """Test suite for calculate_days_until function."""

    def test_calculate_days_until_future_date(self) -> None:
        """Test calculating days until future date."""
        from datetime import timedelta

        future = datetime.now(UTC) + timedelta(days=30)
        days = calculate_days_until(future)

        # Should be approximately 30 days (allow ±1 for timing)
        assert 29 <= days <= 30

    def test_calculate_days_until_past_date(self) -> None:
        """Test calculating days for past date (negative)."""
        from datetime import timedelta

        past = datetime.now(UTC) - timedelta(days=10)
        days = calculate_days_until(past)

        # Should be approximately -10 days (allow ±1 for timing/rounding)
        assert -11 <= days <= -9

    def test_calculate_days_until_today(self) -> None:
        """Test calculating days until today."""
        today = datetime.now(UTC)
        days = calculate_days_until(today)

        # Should be 0 or very close
        assert -1 <= days <= 0


class TestValidateUrl:
    """Test suite for validate_url function."""

    def test_validate_https_url(self) -> None:
        """Test that HTTPS URLs are valid."""
        assert validate_url("https://example.com") is True

    def test_validate_http_url(self) -> None:
        """Test that HTTP URLs are valid."""
        assert validate_url("http://example.com") is True

    def test_validate_url_with_path(self) -> None:
        """Test URLs with paths are valid."""
        assert validate_url("https://example.com/path/to/resource") is True

    def test_validate_url_with_query(self) -> None:
        """Test URLs with query parameters are valid."""
        assert validate_url("https://example.com?param=value") is True

    def test_validate_url_with_port(self) -> None:
        """Test URLs with port numbers are valid."""
        assert validate_url("https://example.com:8443/path") is True

    def test_validate_ftp_url_invalid(self) -> None:
        """Test that FTP URLs are invalid."""
        assert validate_url("ftp://example.com") is False

    def test_validate_invalid_scheme(self) -> None:
        """Test that invalid schemes are rejected."""
        assert validate_url("file:///path/to/file") is False

    def test_validate_no_scheme(self) -> None:
        """Test that URLs without scheme are invalid."""
        assert validate_url("example.com") is False


class TestCreateSSLContext:
    """Tests for the create_ssl_context helper."""

    def test_create_ssl_context_verification_enabled(self) -> None:
        """Default mode should enforce certificate validation."""

        ctx = create_ssl_context(verify_ssl=True)

        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_create_ssl_context_verification_disabled(self) -> None:
        """Legacy mode disables verification and relaxes protocol bounds."""

        ctx = create_ssl_context(verify_ssl=False)

        assert ctx.verify_mode == ssl.CERT_NONE
        assert ctx.check_hostname is False

        if hasattr(ctx, "minimum_version") and hasattr(ssl, "TLSVersion"):
            assert ctx.minimum_version <= ssl.TLSVersion.TLSv1

    def test_create_ssl_context_without_tlsversion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Function handles environments lacking ssl.TLSVersion."""

        class DummyContext:
            def __init__(self, protocol: int) -> None:  # noqa: ARG002
                self.check_hostname = True
                self.verify_mode = ssl.CERT_REQUIRED
                self.minimum_version = "original-min"
                self.maximum_version = "original-max"
                self.options = 0

            def set_ciphers(self, _value: str) -> None:
                self.ciphers = _value

        monkeypatch.delattr(ssl, "TLSVersion", raising=False)
        monkeypatch.setattr(ssl, "SSLContext", DummyContext)

        ctx = create_ssl_context(verify_ssl=False)

        assert ctx.verify_mode == ssl.CERT_NONE
        assert ctx.minimum_version == "original-min"  # type: ignore[comparison-overlap]
        assert ctx.maximum_version == "original-max"  # type: ignore[comparison-overlap]

    def test_create_ssl_context_without_disable_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Function handles environments lacking OP_NO_* constants."""

        monkeypatch.delattr(ssl, "OP_NO_SSLv3", raising=False)
        monkeypatch.delattr(ssl, "OP_NO_TLSv1", raising=False)
        monkeypatch.delattr(ssl, "OP_NO_TLSv1_1", raising=False)

        ctx = create_ssl_context(verify_ssl=False)

        assert ctx.verify_mode == ssl.CERT_NONE

    def test_validate_empty_string(self) -> None:
        """Test that empty string is invalid."""
        assert validate_url("") is False

    def test_validate_relative_url(self) -> None:
        """Test that relative URLs are invalid."""
        assert validate_url("/path/to/resource") is False


class TestReadRequestData:
    """Test suite for read_request_data function."""

    def test_read_request_data_none_input(self) -> None:
        """Test that None input returns None content and empty headers."""
        content, headers = read_request_data(None)

        assert content is None
        assert headers == {}

    def test_read_request_data_empty_string(self) -> None:
        """Test that empty string returns None content and empty headers."""
        content, headers = read_request_data("")

        assert content is None
        assert headers == {}

    def test_read_request_data_inline_json(self) -> None:
        """Test reading inline JSON data auto-detects Content-Type."""
        json_data = '{"name": "John", "age": 30}'
        content, headers = read_request_data(json_data)

        assert content == json_data.encode("utf-8")
        assert headers == {"Content-Type": "application/json"}

    def test_read_request_data_inline_non_json(self) -> None:
        """Test reading inline non-JSON data returns no Content-Type."""
        plain_data = "this is not json"
        content, headers = read_request_data(plain_data)

        assert content == plain_data.encode("utf-8")
        assert headers == {}

    def test_read_request_data_from_json_file(self, tmp_path: Path) -> None:
        """Test reading data from .json file auto-detects Content-Type."""
        json_file = tmp_path / "data.json"
        json_content = '{"status": "active"}'
        json_file.write_text(json_content)

        content, headers = read_request_data(f"@{json_file}")

        assert content == json_content.encode("utf-8")
        assert headers == {"Content-Type": "application/json"}

    def test_read_request_data_from_xml_file(self, tmp_path: Path) -> None:
        """Test reading data from .xml file auto-detects Content-Type."""
        xml_file = tmp_path / "data.xml"
        xml_content = "<root><item>value</item></root>"
        xml_file.write_text(xml_content)

        content, headers = read_request_data(f"@{xml_file}")

        assert content == xml_content.encode("utf-8")
        assert headers == {"Content-Type": "application/xml"}

    def test_read_request_data_from_txt_file(self, tmp_path: Path) -> None:
        """Test reading data from .txt file auto-detects Content-Type."""
        txt_file = tmp_path / "data.txt"
        txt_content = "plain text content"
        txt_file.write_text(txt_content)

        content, headers = read_request_data(f"@{txt_file}")

        assert content == txt_content.encode("utf-8")
        assert headers == {"Content-Type": "text/plain"}

    def test_read_request_data_from_text_extension_file(
        self,
        tmp_path: Path,
    ) -> None:
        """Test reading data from .text file auto-detects Content-Type."""
        text_file = tmp_path / "data.text"
        text_content = "plain text content"
        text_file.write_text(text_content)

        content, headers = read_request_data(f"@{text_file}")

        assert content == text_content.encode("utf-8")
        assert headers == {"Content-Type": "text/plain"}

    def test_read_request_data_unknown_extension_with_json_content(
        self,
        tmp_path: Path,
    ) -> None:
        """Test file with unknown extension but JSON content detects JSON."""
        unknown_file = tmp_path / "data.dat"
        json_content = '{"key": "value"}'
        unknown_file.write_text(json_content)

        content, headers = read_request_data(f"@{unknown_file}")

        assert content == json_content.encode("utf-8")
        assert headers == {"Content-Type": "application/json"}

    def test_read_request_data_unknown_extension_non_json(
        self,
        tmp_path: Path,
    ) -> None:
        """Test file with unknown extension and non-JSON content."""
        unknown_file = tmp_path / "data.dat"
        plain_content = "not json content"
        unknown_file.write_text(plain_content)

        content, headers = read_request_data(f"@{unknown_file}")

        assert content == plain_content.encode("utf-8")
        assert headers == {}

    def test_read_request_data_file_not_found(self) -> None:
        """Test that reading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            read_request_data("@nonexistent.json")

    def test_read_request_data_inline_json_array(self) -> None:
        """Test reading inline JSON array auto-detects Content-Type."""
        json_data = '[{"id": 1}, {"id": 2}]'
        content, headers = read_request_data(json_data)

        assert content == json_data.encode("utf-8")
        assert headers == {"Content-Type": "application/json"}

    def test_read_request_data_inline_json_with_unicode(self) -> None:
        """Test reading JSON with unicode characters."""
        json_data = '{"message": "Hello 世界"}'
        content, headers = read_request_data(json_data)

        assert content == json_data.encode("utf-8")
        assert headers == {"Content-Type": "application/json"}

    def test_read_request_data_malformed_json(self) -> None:
        """Test that malformed JSON is treated as plain text."""
        malformed = '{"invalid": json}'
        content, headers = read_request_data(malformed)

        assert content == malformed.encode("utf-8")
        assert headers == {}

    def test_read_request_data_binary_file(self, tmp_path: Path) -> None:
        """Test reading binary file with unknown extension."""
        binary_file = tmp_path / "data.bin"
        binary_content = b"\x00\x01\x02\x03\xff\xfe"
        binary_file.write_bytes(binary_content)

        content, headers = read_request_data(f"@{binary_file}")

        assert content == binary_content
        assert headers == {}

    def test_read_request_data_json_file_extension_priority(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that file extension takes priority over content inspection."""
        json_file = tmp_path / "data.json"
        # Write non-JSON content to .json file
        json_file.write_text("not valid json")

        content, headers = read_request_data(f"@{json_file}")

        # Extension should take priority, so Content-Type is application/json
        # even though content is not valid JSON
        assert content == b"not valid json"
        assert headers == {"Content-Type": "application/json"}
