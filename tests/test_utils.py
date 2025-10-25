from datetime import datetime, timezone

import pytest
from faker import Faker

from httptap.utils import (
    UTC,
    calculate_days_until,
    mask_sensitive_value,
    parse_certificate_date,
    parse_http_date,
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

    def test_validate_empty_string(self) -> None:
        """Test that empty string is invalid."""
        assert validate_url("") is False

    def test_validate_relative_url(self) -> None:
        """Test that relative URLs are invalid."""
        assert validate_url("/path/to/resource") is False
