from __future__ import annotations

import re

import pytest

from httptap.formatters import (
    format_bytes_human,
    format_error,
    format_metrics_line,
    format_network_info,
    format_response_info,
    format_step_header,
)
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics


def build_step(status: int) -> StepMetrics:
    timing = TimingMetrics(
        dns_ms=5.0,
        connect_ms=10.0,
        tls_ms=20.0,
        ttfb_ms=60.0,
        total_ms=100.0,
    )
    network = NetworkInfo(
        ip="198.51.100.1",
        ip_family="IPv4",
        tls_version="TLSv1.3",
        tls_cipher="TLS_AES_256_GCM_SHA384",
        cert_cn="example.test",
        cert_days_left=42,
    )
    response = ResponseInfo(
        status=status,
        bytes=512,
        server="unit-tests",
        location="/next",
    )
    return StepMetrics(
        url="https://example.test",
        step_number=3,
        timing=timing,
        network=network,
        response=response,
    )


def test_format_step_header() -> None:
    step = build_step(200)
    header = format_step_header(step)
    assert "Step 3" in header
    assert "example.test" in header


def test_format_network_info_renders_tls_details() -> None:
    step = build_step(200)
    info = format_network_info(step)
    assert info is not None
    assert "TLS: TLSv1.3" in info
    assert "Expires" in info


def test_format_response_info_handles_redirect() -> None:
    step = build_step(301)
    info = format_response_info(step)
    assert info is not None
    assert "Status" in info
    assert "→" in info


def test_format_metrics_line_contains_all_phases() -> None:
    step = build_step(200)
    line = format_metrics_line(step)
    assert re.search(r"dns=5.0", line)
    assert "connect=10.0" in line
    assert "status=200" in line


def test_format_bytes_human_units() -> None:
    assert format_bytes_human(512) == "512 B"
    assert format_bytes_human(2048) == "2.0 KB"
    assert format_bytes_human(1048576) == "1.0 MB"


class TestFormatError:
    """Test suite for format_error function."""

    def test_format_error_with_error_only(self) -> None:
        """Test formatting error without note."""
        step = StepMetrics(error="Connection timeout")
        panel = format_error(step)

        # Panel should contain error text
        assert panel.title == "[bold red]Error[/bold red]"
        assert panel.border_style == "red"

    def test_format_error_with_note(self) -> None:
        """Test formatting error with note."""
        step = StepMetrics(error="SSL verification failed", note="Try --no-verify flag")
        panel = format_error(step)

        # Panel should be created (checking attributes)
        assert panel.title == "[bold red]Error[/bold red]"
        assert panel.border_style == "red"


class TestFormatNetworkInfo:
    """Test suite for format_network_info function."""

    def test_format_network_info_with_all_fields(self) -> None:
        """Test formatting network info with all fields present."""
        network = NetworkInfo(
            ip="192.0.2.1",
            ip_family="IPv4",
            http_version="HTTP/2.0",
            tls_version="TLSv1.3",
            tls_cipher="TLS_AES_256_GCM_SHA384",
            cert_cn="example.com",
            cert_days_left=60,
        )
        step = StepMetrics(network=network, proxied_via="socks5://proxy:1080")
        info = format_network_info(step)

        assert info is not None
        assert "192.0.2.1 (IPv4)" in info
        assert "HTTP: HTTP/2.0" in info
        assert "TLS: TLSv1.3" in info
        assert "Cipher: TLS_AES_256_GCM_SHA384" in info
        assert "Cert: example.com" in info
        assert "Expires: 60d" in info
        assert "Proxy: socks5://proxy:1080" in info

    def test_format_network_info_with_no_data(self) -> None:
        """Test formatting network info when no data available."""
        step = StepMetrics(network=NetworkInfo())
        info = format_network_info(step)

        assert info is None

    def test_format_network_info_with_ip_only(self) -> None:
        """Test formatting network info with only IP."""
        network = NetworkInfo(ip="2001:db8::1")
        step = StepMetrics(network=network)
        info = format_network_info(step)

        assert info is not None
        assert "2001:db8::1" in info

    def test_format_network_info_with_ip_and_family(self) -> None:
        """Test formatting network info with IP and family."""
        network = NetworkInfo(ip="2001:db8::1", ip_family="IPv6")
        step = StepMetrics(network=network)
        info = format_network_info(step)

        assert info is not None
        assert "2001:db8::1 (IPv6)" in info

    def test_format_network_info_tls_verification_warning(self) -> None:
        """Test that TLS verification warning is rendered when disabled."""
        network = NetworkInfo(ip="192.0.2.5", tls_verified=False)
        step = StepMetrics(network=network)
        info = format_network_info(step)

        assert info is not None
        assert "⚠ TLS verification disabled" in info

    def test_format_network_info_orders_http_before_tls(self) -> None:
        """Ensure HTTP version is reported ahead of TLS details."""
        network = NetworkInfo(
            ip="192.0.2.5",
            http_version="HTTP/1.1",
            tls_version="TLSv1.2",
        )
        step = StepMetrics(network=network)
        info = format_network_info(step)

        assert info is not None
        http_index = info.index("HTTP: HTTP/1.1")
        tls_index = info.index("TLS: TLSv1.2")
        assert http_index < tls_index

    @pytest.mark.parametrize(
        ("days_left", "expected_style"),
        [
            (5, "red"),  # Critical: less than 30 days
            (29, "red"),
            (30, "yellow"),  # Warning: 30-89 days
            (60, "yellow"),
            (89, "yellow"),
            (90, "green"),  # OK: 90 days or more
            (120, "green"),
        ],
    )
    def test_format_network_info_cert_expiry_colors(
        self,
        days_left: int,
        expected_style: str,
    ) -> None:
        """Test cert expiry colors based on days remaining."""
        network = NetworkInfo(cert_cn="example.com", cert_days_left=days_left)
        step = StepMetrics(network=network)
        info = format_network_info(step)

        assert info is not None
        assert f"[{expected_style}]" in info
        assert f"Expires: {days_left}d" in info

    def test_format_network_info_custom_ca(self) -> None:
        """Test that custom CA indicator is shown when tls_custom_ca is True."""
        network = NetworkInfo(tls_verified=True, tls_custom_ca=True)
        step = StepMetrics(network=network)

        info = format_network_info(step)

        assert info is not None
        assert "TLS CA: custom bundle" in info


class TestFormatResponseInfo:
    """Test suite for format_response_info function."""

    def test_format_response_info_with_all_fields(self) -> None:
        """Test formatting response info with all fields."""
        response = ResponseInfo(
            status=200,
            bytes=1024,
            server="nginx/1.21",
            location="/redirected",
        )
        step = StepMetrics(response=response)
        info = format_response_info(step)

        assert info is not None
        assert "Status: 200" in info
        assert "Size:" in info
        assert "Server: nginx/1.21" in info
        assert "→" in info
        assert "/redirected" in info

    def test_format_response_info_with_no_data(self) -> None:
        """Test formatting response info when no data available."""
        step = StepMetrics(response=ResponseInfo())
        info = format_response_info(step)

        assert info is None

    @pytest.mark.parametrize(
        ("status", "expected_style"),
        [
            (200, "green"),
            (201, "green"),
            (299, "green"),
            (301, "yellow"),
            (302, "yellow"),
            (399, "yellow"),
            (400, "red"),
            (404, "red"),
            (500, "red"),
        ],
    )
    def test_format_response_info_status_colors(
        self,
        status: int,
        expected_style: str,
    ) -> None:
        """Test status colors based on HTTP status code."""
        response = ResponseInfo(status=status)
        step = StepMetrics(response=response)
        info = format_response_info(step)

        assert info is not None
        assert f"[{expected_style}]" in info
        assert f"Status: {status}" in info

    def test_format_response_info_with_zero_bytes(self) -> None:
        """Test formatting response with zero bytes (should not show size)."""
        response = ResponseInfo(status=204, bytes=0)
        step = StepMetrics(response=response)
        info = format_response_info(step)

        assert info is not None
        assert "Status: 204" in info
        assert "Size:" not in info

    def test_format_response_info_with_positive_bytes(self) -> None:
        """Test formatting response with positive bytes."""
        response = ResponseInfo(status=200, bytes=2048)
        step = StepMetrics(response=response)
        info = format_response_info(step)

        assert info is not None
        assert "Size: 2.0 KB" in info


class TestFormatBytesHuman:
    """Test suite for format_bytes_human function."""

    @pytest.mark.parametrize(
        ("num_bytes", "expected"),
        [
            (0, "0 B"),
            (1, "1 B"),
            (512, "512 B"),
            (1023, "1023 B"),
            (1024, "1.0 KB"),
            (2048, "2.0 KB"),
            (1024 * 1024 - 1, "1024.0 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024 * 1024 * 2, "2.0 MB"),
            (1024 * 1024 * 1024, "1024.0 MB"),
        ],
    )
    def test_format_bytes_human_various_sizes(
        self,
        num_bytes: int,
        expected: str,
    ) -> None:
        """Test byte formatting for various sizes."""
        result = format_bytes_human(num_bytes)
        assert result == expected


class TestFormatMetricsLine:
    """Test suite for format_metrics_line function."""

    def test_format_metrics_line_with_all_fields(self) -> None:
        """Test metrics line with all fields present."""
        timing = TimingMetrics(
            dns_ms=5.5,
            connect_ms=10.2,
            tls_ms=20.8,
            ttfb_ms=60.1,
            total_ms=100.3,
        )
        network = NetworkInfo(ip="192.0.2.1", ip_family="IPv4", tls_version="TLSv1.3")
        response = ResponseInfo(status=200, bytes=1024)
        step = StepMetrics(
            step_number=1,
            timing=timing,
            network=network,
            response=response,
        )

        line = format_metrics_line(step)

        assert "Step 1:" in line
        assert "dns=5.5" in line
        assert "connect=10.2" in line
        assert "tls=20.8" in line
        assert "ttfb=60.1" in line
        assert "total=100.3" in line
        assert "status=200" in line
        assert "bytes=1024" in line
        assert "ip=192.0.2.1" in line
        assert "family=IPv4" in line
        assert "tls_version=TLSv1.3" in line

    def test_format_metrics_line_with_minimal_fields(self) -> None:
        """Test metrics line with only required fields."""
        step = StepMetrics(step_number=2)

        line = format_metrics_line(step)

        assert "Step 2:" in line
        assert "dns=0.0" in line
        assert "status=None" in line
        assert "bytes=0" in line
        # Optional fields should not be present
        assert "ip=" not in line or "ip=None" not in line

    def test_format_metrics_line_with_no_optional_network_fields(self) -> None:
        """Test metrics line without optional network fields."""
        timing = TimingMetrics(total_ms=100.0)
        response = ResponseInfo(status=200)
        step = StepMetrics(step_number=3, timing=timing, response=response)

        line = format_metrics_line(step)

        assert "Step 3:" in line
        assert "total=100.0" in line
        assert "status=200" in line
        # No IP, family, or TLS version
        assert "ip=" not in line
        assert "family=" not in line
        assert "tls_version=" not in line
