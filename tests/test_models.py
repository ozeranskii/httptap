"""Unit tests for data models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.utils import UTC

if TYPE_CHECKING:
    from faker import Faker


class TestTimingMetrics:
    """Test suite for TimingMetrics model."""

    def test_initialization_with_defaults(self) -> None:
        """Test that TimingMetrics initializes with zero values."""
        timing = TimingMetrics()

        assert timing.dns_ms == 0.0
        assert timing.connect_ms == 0.0
        assert timing.tls_ms == 0.0
        assert timing.ttfb_ms == 0.0
        assert timing.total_ms == 0.0
        assert timing.wait_ms == 0.0
        assert timing.xfer_ms == 0.0
        assert timing.is_estimated is False

    def test_initialization_with_values(self, faker: Faker) -> None:
        """Test initializing TimingMetrics with specific values."""
        dns_ms = faker.pyfloat(left_digits=2, right_digits=1, positive=True)
        connect_ms = faker.pyfloat(left_digits=2, right_digits=1, positive=True)
        tls_ms = faker.pyfloat(left_digits=2, right_digits=1, positive=True)
        ttfb_ms = faker.pyfloat(left_digits=3, right_digits=1, positive=True)
        total_ms = ttfb_ms + faker.pyfloat(left_digits=2, right_digits=1, positive=True)

        timing = TimingMetrics(
            dns_ms=dns_ms,
            connect_ms=connect_ms,
            tls_ms=tls_ms,
            ttfb_ms=ttfb_ms,
            total_ms=total_ms,
            is_estimated=True,
        )

        assert timing.dns_ms == dns_ms
        assert timing.connect_ms == connect_ms
        assert timing.tls_ms == tls_ms
        assert timing.ttfb_ms == ttfb_ms
        assert timing.total_ms == total_ms
        assert timing.is_estimated is True

    def test_calculate_derived_computes_wait_ms(self) -> None:
        """Test that calculate_derived() computes wait_ms correctly."""
        timing = TimingMetrics(
            dns_ms=10.0,
            connect_ms=20.0,
            tls_ms=30.0,
            ttfb_ms=100.0,
            total_ms=120.0,
        )

        timing.calculate_derived()

        # Expected: wait_ms = ttfb_ms - (dns_ms + connect_ms + tls_ms) = 40ms
        assert timing.wait_ms == 40.0

    def test_calculate_derived_computes_xfer_ms(self) -> None:
        """Test that calculate_derived() computes xfer_ms correctly."""
        timing = TimingMetrics(
            ttfb_ms=100.0,
            total_ms=150.0,
        )

        timing.calculate_derived()

        # Expected: xfer_ms = total_ms - ttfb_ms = 50ms
        assert timing.xfer_ms == 50.0

    def test_calculate_derived_clamps_negative_wait_to_zero(self) -> None:
        """Test that negative wait_ms is clamped to zero."""
        timing = TimingMetrics(
            dns_ms=50.0,
            connect_ms=50.0,
            tls_ms=50.0,
            ttfb_ms=100.0,  # Less than sum of phases
            total_ms=120.0,
        )

        timing.calculate_derived()

        # wait_ms would be 100 - 150 = -50, but clamped to 0
        assert timing.wait_ms == 0.0

    def test_calculate_derived_clamps_negative_xfer_to_zero(self) -> None:
        """Test that negative xfer_ms is clamped to zero."""
        timing = TimingMetrics(
            ttfb_ms=100.0,
            total_ms=90.0,  # Less than TTFB (edge case)
        )

        timing.calculate_derived()

        # xfer_ms would be 90 - 100 = -10, but clamped to 0
        assert timing.xfer_ms == 0.0

    def test_to_dict_includes_all_fields(self) -> None:
        """Test that to_dict() includes all timing fields."""
        timing = TimingMetrics(
            dns_ms=10.0,
            connect_ms=20.0,
            tls_ms=30.0,
            ttfb_ms=80.0,
            total_ms=100.0,
            wait_ms=20.0,
            xfer_ms=20.0,
            is_estimated=True,
        )

        result = timing.to_dict()

        assert result == {
            "dns_ms": 10.0,
            "connect_ms": 20.0,
            "tls_ms": 30.0,
            "ttfb_ms": 80.0,
            "total_ms": 100.0,
            "wait_ms": 20.0,
            "xfer_ms": 20.0,
            "is_estimated": True,
        }


class TestNetworkInfo:
    """Test suite for NetworkInfo model."""

    def test_initialization_with_defaults(self) -> None:
        """Test that NetworkInfo initializes with None values."""
        network = NetworkInfo()

        assert network.ip is None
        assert network.ip_family is None
        assert network.http_version is None
        assert network.tls_version is None
        assert network.tls_cipher is None
        assert network.cert_cn is None
        assert network.cert_days_left is None

    def test_initialization_with_values(self, faker: Faker) -> None:
        """Test initializing NetworkInfo with specific values."""
        ip = faker.ipv4()
        ip_family = "IPv4"
        http_version = "HTTP/1.1"
        tls_version = faker.random_element(["TLSv1.2", "TLSv1.3"])
        tls_cipher = faker.pystr(min_chars=12, max_chars=32)
        cert_cn = faker.domain_name()
        cert_days_left = faker.pyint(min_value=1, max_value=365)

        network = NetworkInfo(
            ip=ip,
            ip_family=ip_family,
            http_version=http_version,
            tls_version=tls_version,
            tls_cipher=tls_cipher,
            cert_cn=cert_cn,
            cert_days_left=cert_days_left,
        )

        assert network.ip == ip
        assert network.ip_family == ip_family
        assert network.http_version == http_version
        assert network.tls_version == tls_version
        assert network.tls_cipher == tls_cipher
        assert network.cert_cn == cert_cn
        assert network.cert_days_left == cert_days_left

    def test_to_dict_includes_all_fields(self, faker: Faker) -> None:
        """Test that to_dict() includes all network fields."""
        ip = faker.ipv6()
        ip_family = "IPv6"
        http_version = "HTTP/2.0"
        tls_version = faker.random_element(["TLSv1.2", "TLSv1.3"])
        tls_cipher = faker.pystr(min_chars=12, max_chars=32)
        cert_cn = faker.domain_name()
        cert_days_left = faker.pyint(min_value=1, max_value=365)

        network = NetworkInfo(
            ip=ip,
            ip_family=ip_family,
            http_version=http_version,
            tls_version=tls_version,
            tls_cipher=tls_cipher,
            cert_cn=cert_cn,
            cert_days_left=cert_days_left,
            tls_verified=True,
        )

        result = network.to_dict()

        assert result == {
            "ip": ip,
            "ip_family": ip_family,
            "http_version": http_version,
            "tls_version": tls_version,
            "tls_cipher": tls_cipher,
            "cert_cn": cert_cn,
            "cert_days_left": cert_days_left,
            "tls_verified": True,
        }

    def test_to_dict_handles_none_values(self, faker: Faker) -> None:
        """Test that to_dict() handles None values correctly."""
        ip = faker.ipv4()
        network = NetworkInfo(ip=ip)

        result = network.to_dict()

        assert result["ip"] == ip
        assert result["http_version"] is None
        assert result["tls_version"] is None
        assert result["cert_cn"] is None


class TestResponseInfo:
    """Test suite for ResponseInfo model."""

    def test_initialization_with_defaults(self) -> None:
        """Test that ResponseInfo initializes with default values."""
        response = ResponseInfo()

        assert response.status is None
        assert response.bytes == 0
        assert response.content_type is None
        assert response.server is None
        assert response.date is None
        assert response.location is None
        assert response.headers == {}

    def test_initialization_with_values(self, faker: Faker) -> None:
        """Test initializing ResponseInfo with specific values."""
        test_date = faker.date_time(tzinfo=UTC)
        headers = {faker.word(): faker.pystr(min_chars=4, max_chars=12)}
        status = faker.random_element([200, 201, 204])
        byte_count = faker.pyint(min_value=128, max_value=4096)
        content_type = faker.mime_type()
        server = faker.hostname()

        response = ResponseInfo(
            status=status,
            bytes=byte_count,
            content_type=content_type,
            server=server,
            date=test_date,
            location=None,
            headers=headers,
        )

        assert response.status == status
        assert response.bytes == byte_count
        assert response.content_type == content_type
        assert response.server == server
        assert response.date == test_date
        assert response.location is None
        assert response.headers == headers

    def test_to_dict_includes_all_fields(self, faker: Faker) -> None:
        """Test that to_dict() includes all response fields."""
        test_date = faker.date_time(tzinfo=UTC)
        headers = {faker.word(): faker.pystr(min_chars=4, max_chars=12)}
        status = faker.random_element([400, 404, 410])
        byte_count = faker.pyint(min_value=128, max_value=2048)
        content_type = faker.mime_type()
        server = faker.hostname()
        location = f"/{faker.word()}"

        response = ResponseInfo(
            status=status,
            bytes=byte_count,
            content_type=content_type,
            server=server,
            date=test_date,
            location=location,
            headers=headers,
        )

        result = response.to_dict()

        assert result["status"] == status
        assert result["bytes"] == byte_count
        assert result["content_type"] == content_type
        assert result["server"] == server
        assert result["date"] == test_date.isoformat()
        assert result["location"] == location
        assert result["headers"] == headers

    def test_to_dict_handles_none_date(self) -> None:
        """Test that to_dict() handles None date correctly."""
        response = ResponseInfo(status=200)

        result = response.to_dict()

        assert result["date"] is None

    def test_to_dict_formats_date_as_iso(self, faker: Faker) -> None:
        """Test that to_dict() formats date as ISO string."""
        test_date = faker.date_time(tzinfo=UTC)
        response = ResponseInfo(date=test_date)

        result = response.to_dict()

        assert result["date"] == test_date.isoformat()


class TestStepMetrics:
    """Test suite for StepMetrics model."""

    def test_initialization_with_defaults(self) -> None:
        """Test that StepMetrics initializes with default values."""
        step = StepMetrics()

        assert step.url == ""
        assert step.step_number == 1
        assert isinstance(step.timing, TimingMetrics)
        assert isinstance(step.network, NetworkInfo)
        assert isinstance(step.response, ResponseInfo)
        assert step.error is None
        assert step.note is None

    def test_initialization_with_values(self, faker: Faker) -> None:
        """Test initializing StepMetrics with specific values."""
        timing = TimingMetrics(total_ms=100.0)
        network = NetworkInfo(ip=faker.ipv4())
        response = ResponseInfo(status=faker.random_element([200, 201]))
        url = faker.url()
        error_message = faker.sentence()
        note = faker.sentence()

        step = StepMetrics(
            url=url,
            step_number=2,
            timing=timing,
            network=network,
            response=response,
            error=error_message,
            note=note,
        )

        assert step.url == url
        assert step.step_number == 2
        assert step.timing is timing
        assert step.network is network
        assert step.response is response
        assert step.error == error_message
        assert step.note == note

    def test_to_dict_includes_all_fields(self, faker: Faker) -> None:
        """Test that to_dict() includes all step fields."""
        url = faker.url()
        step_number = faker.pyint(min_value=1, max_value=5)
        step = StepMetrics(url=url, step_number=step_number)

        result = step.to_dict()

        assert result["url"] == url
        assert result["step_number"] == step_number
        assert "timing" in result
        assert "network" in result
        assert "response" in result
        assert result["error"] is None
        assert result["note"] is None

    def test_has_error_returns_true_when_error_present(self, faker: Faker) -> None:
        """Test that has_error property returns True when error exists."""
        step = StepMetrics(error=faker.sentence())

        assert step.has_error is True

    def test_has_error_returns_false_when_no_error(self) -> None:
        """Test that has_error property returns False when no error."""
        step = StepMetrics()

        assert step.has_error is False

    def test_is_redirect_returns_true_for_3xx_with_location(self, faker: Faker) -> None:
        """Test that is_redirect returns True for 3xx status with Location."""
        response = ResponseInfo(status=301, location=faker.uri())
        step = StepMetrics(response=response)

        assert step.is_redirect is True

    def test_is_redirect_returns_false_for_3xx_without_location(self) -> None:
        """Test that is_redirect returns False for 3xx without Location."""
        response = ResponseInfo(status=304, location=None)
        step = StepMetrics(response=response)

        assert step.is_redirect is False

    def test_is_redirect_returns_false_for_2xx(self, faker: Faker) -> None:
        """Test that is_redirect returns False for 2xx status."""
        response = ResponseInfo(status=200, location=faker.uri())
        step = StepMetrics(response=response)

        # Even with Location header, 2xx is not a redirect
        assert step.is_redirect is False

    def test_is_redirect_returns_false_for_4xx(self, faker: Faker) -> None:
        """Test that is_redirect returns False for 4xx status."""
        response = ResponseInfo(status=404, location=faker.uri())
        step = StepMetrics(response=response)

        assert step.is_redirect is False

    def test_is_redirect_returns_false_when_status_is_none(self, faker: Faker) -> None:
        """Test that is_redirect returns False when status is None."""
        response = ResponseInfo(status=None, location=faker.uri())
        step = StepMetrics(response=response)

        assert step.is_redirect is False

    @pytest.mark.parametrize(
        "status",
        [300, 301, 302, 303, 307, 308],
    )
    def test_is_redirect_true_for_various_3xx_codes(self, status: int) -> None:
        """Test that is_redirect works for various redirect status codes."""
        response = ResponseInfo(status=status, location="/redirect")
        step = StepMetrics(response=response)

        assert step.is_redirect is True

    def test_to_dict_nests_sub_models(self, faker: Faker) -> None:
        """Test that to_dict() properly nests sub-model dictionaries."""
        timing = TimingMetrics(dns_ms=10.0)
        network = NetworkInfo(ip=faker.ipv4())
        response = ResponseInfo(status=faker.random_element([200, 201]))
        step = StepMetrics(timing=timing, network=network, response=response)

        result = step.to_dict()

        assert isinstance(result["timing"], dict)
        assert result["timing"]["dns_ms"] == 10.0
        assert isinstance(result["network"], dict)
        assert result["network"]["ip"] == network.ip
        assert isinstance(result["response"], dict)
        assert result["response"]["status"] == response.status
