"""Unit tests for data models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics


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

    def test_initialization_with_values(self) -> None:
        """Test initializing TimingMetrics with specific values."""
        timing = TimingMetrics(
            dns_ms=10.5,
            connect_ms=20.3,
            tls_ms=50.1,
            ttfb_ms=100.0,
            total_ms=150.0,
            is_estimated=True,
        )

        assert timing.dns_ms == 10.5
        assert timing.connect_ms == 20.3
        assert timing.tls_ms == 50.1
        assert timing.ttfb_ms == 100.0
        assert timing.total_ms == 150.0
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
        assert network.tls_version is None
        assert network.tls_cipher is None
        assert network.cert_cn is None
        assert network.cert_days_left is None

    def test_initialization_with_values(self) -> None:
        """Test initializing NetworkInfo with specific values."""
        network = NetworkInfo(
            ip="93.184.216.34",
            ip_family="IPv4",
            tls_version="TLSv1.3",
            tls_cipher="TLS_AES_256_GCM_SHA384",
            cert_cn="example.com",
            cert_days_left=90,
        )

        assert network.ip == "93.184.216.34"
        assert network.ip_family == "IPv4"
        assert network.tls_version == "TLSv1.3"
        assert network.tls_cipher == "TLS_AES_256_GCM_SHA384"
        assert network.cert_cn == "example.com"
        assert network.cert_days_left == 90

    def test_to_dict_includes_all_fields(self) -> None:
        """Test that to_dict() includes all network fields."""
        network = NetworkInfo(
            ip="2606:2800:220:1:248:1893:25c8:1946",
            ip_family="IPv6",
            tls_version="TLSv1.2",
            tls_cipher="ECDHE-RSA-AES128-GCM-SHA256",
            cert_cn="example.com",
            cert_days_left=45,
        )

        result = network.to_dict()

        assert result == {
            "ip": "2606:2800:220:1:248:1893:25c8:1946",
            "ip_family": "IPv6",
            "tls_version": "TLSv1.2",
            "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
            "cert_cn": "example.com",
            "cert_days_left": 45,
        }

    def test_to_dict_handles_none_values(self) -> None:
        """Test that to_dict() handles None values correctly."""
        network = NetworkInfo(ip="1.2.3.4")

        result = network.to_dict()

        assert result["ip"] == "1.2.3.4"
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

    def test_initialization_with_values(self) -> None:
        """Test initializing ResponseInfo with specific values."""
        test_date = datetime(2025, 10, 22, 12, 0, 0, tzinfo=UTC)
        headers = {"content-type": "application/json", "server": "nginx"}

        response = ResponseInfo(
            status=200,
            bytes=1024,
            content_type="application/json",
            server="nginx",
            date=test_date,
            location=None,
            headers=headers,
        )

        assert response.status == 200
        assert response.bytes == 1024
        assert response.content_type == "application/json"
        assert response.server == "nginx"
        assert response.date == test_date
        assert response.location is None
        assert response.headers == headers

    def test_to_dict_includes_all_fields(self) -> None:
        """Test that to_dict() includes all response fields."""
        test_date = datetime(2025, 10, 22, 12, 0, 0, tzinfo=UTC)
        headers = {"server": "Apache"}

        response = ResponseInfo(
            status=404,
            bytes=512,
            content_type="text/html",
            server="Apache",
            date=test_date,
            location="/new-page",
            headers=headers,
        )

        result = response.to_dict()

        assert result["status"] == 404
        assert result["bytes"] == 512
        assert result["content_type"] == "text/html"
        assert result["server"] == "Apache"
        assert result["date"] == "2025-10-22T12:00:00+00:00"
        assert result["location"] == "/new-page"
        assert result["headers"] == headers

    def test_to_dict_handles_none_date(self) -> None:
        """Test that to_dict() handles None date correctly."""
        response = ResponseInfo(status=200)

        result = response.to_dict()

        assert result["date"] is None

    def test_to_dict_formats_date_as_iso(self) -> None:
        """Test that to_dict() formats date as ISO string."""
        test_date = datetime(2025, 1, 15, 18, 30, 45, tzinfo=UTC)
        response = ResponseInfo(date=test_date)

        result = response.to_dict()

        assert result["date"] == "2025-01-15T18:30:45+00:00"


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

    def test_initialization_with_values(self) -> None:
        """Test initializing StepMetrics with specific values."""
        timing = TimingMetrics(total_ms=100.0)
        network = NetworkInfo(ip="1.2.3.4")
        response = ResponseInfo(status=200)

        step = StepMetrics(
            url="https://example.com",
            step_number=2,
            timing=timing,
            network=network,
            response=response,
            error="Connection failed",
            note="Retry attempt",
        )

        assert step.url == "https://example.com"
        assert step.step_number == 2
        assert step.timing is timing
        assert step.network is network
        assert step.response is response
        assert step.error == "Connection failed"
        assert step.note == "Retry attempt"

    def test_to_dict_includes_all_fields(self) -> None:
        """Test that to_dict() includes all step fields."""
        step = StepMetrics(
            url="https://example.com/api",
            step_number=3,
        )

        result = step.to_dict()

        assert result["url"] == "https://example.com/api"
        assert result["step_number"] == 3
        assert "timing" in result
        assert "network" in result
        assert "response" in result
        assert result["error"] is None
        assert result["note"] is None

    def test_has_error_returns_true_when_error_present(self) -> None:
        """Test that has_error property returns True when error exists."""
        step = StepMetrics(error="Timeout occurred")

        assert step.has_error is True

    def test_has_error_returns_false_when_no_error(self) -> None:
        """Test that has_error property returns False when no error."""
        step = StepMetrics()

        assert step.has_error is False

    def test_is_redirect_returns_true_for_3xx_with_location(self) -> None:
        """Test that is_redirect returns True for 3xx status with Location."""
        response = ResponseInfo(status=301, location="https://example.com/new")
        step = StepMetrics(response=response)

        assert step.is_redirect is True

    def test_is_redirect_returns_false_for_3xx_without_location(self) -> None:
        """Test that is_redirect returns False for 3xx without Location."""
        response = ResponseInfo(status=304, location=None)
        step = StepMetrics(response=response)

        assert step.is_redirect is False

    def test_is_redirect_returns_false_for_2xx(self) -> None:
        """Test that is_redirect returns False for 2xx status."""
        response = ResponseInfo(status=200, location="https://example.com")
        step = StepMetrics(response=response)

        # Even with Location header, 2xx is not a redirect
        assert step.is_redirect is False

    def test_is_redirect_returns_false_for_4xx(self) -> None:
        """Test that is_redirect returns False for 4xx status."""
        response = ResponseInfo(status=404, location=None)
        step = StepMetrics(response=response)

        assert step.is_redirect is False

    def test_is_redirect_returns_false_when_status_is_none(self) -> None:
        """Test that is_redirect returns False when status is None."""
        response = ResponseInfo(status=None, location="https://example.com")
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

    def test_to_dict_nests_sub_models(self) -> None:
        """Test that to_dict() properly nests sub-model dictionaries."""
        timing = TimingMetrics(dns_ms=10.0)
        network = NetworkInfo(ip="1.2.3.4")
        response = ResponseInfo(status=200)
        step = StepMetrics(timing=timing, network=network, response=response)

        result = step.to_dict()

        assert isinstance(result["timing"], dict)
        assert result["timing"]["dns_ms"] == 10.0
        assert isinstance(result["network"], dict)
        assert result["network"]["ip"] == "1.2.3.4"
        assert isinstance(result["response"], dict)
        assert result["response"]["status"] == 200
