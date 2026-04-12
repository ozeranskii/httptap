from __future__ import annotations

import re

import pytest

from httptap.constants import (
    PROXY_SOURCE_CLI,
    PROXY_SOURCE_DISABLED,
    PROXY_SOURCE_NO_MATCH,
    PROXY_SOURCE_NO_PROXY,
)
from httptap.formatters import (
    format_bytes_human,
    format_compact_line,
    format_error,
    format_metrics_line,
    format_network_info,
    format_response_info,
    format_slo_panel,
    format_step_header,
)
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.slo import SLOResult, SLOViolation


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
        """Test formatting network info when no data available shows direct proxy."""
        step = StepMetrics(network=NetworkInfo())
        info = format_network_info(step)

        assert info is not None
        assert "Proxy: direct" in info

    def test_format_network_info_proxy_from_cli(self) -> None:
        """Test proxy display when set via --proxy CLI arg."""
        network = NetworkInfo(proxy_url="socks5h://gw:1080", proxy_source=PROXY_SOURCE_CLI)
        step = StepMetrics(network=network, proxied_via="socks5h://gw:1080")
        info = format_network_info(step)

        assert info is not None
        assert "Proxy: socks5h://gw:1080 (from arg --proxy)" in info

    def test_format_network_info_proxy_from_env(self) -> None:
        """Test proxy display when resolved from env var."""
        network = NetworkInfo(proxy_url="http://proxy:3128", proxy_source="HTTPS_PROXY")
        step = StepMetrics(network=network, proxied_via="http://proxy:3128")
        info = format_network_info(step)

        assert info is not None
        assert "Proxy: http://proxy:3128 (from env HTTPS_PROXY)" in info

    def test_format_network_info_no_proxy_bypass(self) -> None:
        """Test proxy display when NO_PROXY matched."""
        network = NetworkInfo(proxy_source=PROXY_SOURCE_NO_PROXY)
        step = StepMetrics(network=network)
        info = format_network_info(step)

        assert info is not None
        assert "Proxy: none (bypassed by env no_proxy)" in info

    def test_format_network_info_no_matching_proxy_scheme(self) -> None:
        """Test proxy display when proxy env vars exist but none matched."""
        network = NetworkInfo(proxy_source=PROXY_SOURCE_NO_MATCH)
        step = StepMetrics(network=network)
        info = format_network_info(step)

        assert info is not None
        assert "Proxy: direct (no matching proxy scheme in env)" in info

    def test_format_network_info_noproxy_flag(self) -> None:
        """Test proxy display when --proxy "" is used."""
        network = NetworkInfo(proxy_source=PROXY_SOURCE_DISABLED)
        step = StepMetrics(network=network)
        info = format_network_info(step)

        assert info is not None
        assert 'Proxy: disabled (from --proxy "")' in info

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

    def test_format_metrics_line_proxy_from_cli(self) -> None:
        """Test metrics line shows proxy from --proxy arg."""
        network = NetworkInfo(proxy_url="socks5h://gw:1080", proxy_source=PROXY_SOURCE_CLI)
        step = StepMetrics(
            step_number=1,
            network=network,
            proxied_via="socks5h://gw:1080",
            response=ResponseInfo(status=200),
        )

        line = format_metrics_line(step)

        assert "proxy=socks5h://gw:1080" in line
        assert "proxy_from=arg" in line

    def test_format_metrics_line_proxy_from_env(self) -> None:
        """Test metrics line shows proxy from env var."""
        network = NetworkInfo(proxy_url="http://proxy:3128", proxy_source="HTTPS_PROXY")
        step = StepMetrics(
            step_number=1,
            network=network,
            proxied_via="http://proxy:3128",
            response=ResponseInfo(status=200),
        )

        line = format_metrics_line(step)

        assert "proxy=http://proxy:3128" in line
        assert "proxy_from=env:HTTPS_PROXY" in line

    def test_format_metrics_line_proxy_no_proxy_bypass(self) -> None:
        """Test metrics line shows NO_PROXY bypass."""
        network = NetworkInfo(proxy_source=PROXY_SOURCE_NO_PROXY)
        step = StepMetrics(step_number=1, network=network, response=ResponseInfo(status=200))

        line = format_metrics_line(step)

        assert "proxy=none" in line
        assert "proxy_from=env:no_proxy" in line

    def test_format_metrics_line_proxy_noproxy_flag(self) -> None:
        """Test metrics line shows --proxy "" disabled."""
        network = NetworkInfo(proxy_source=PROXY_SOURCE_DISABLED)
        step = StepMetrics(step_number=1, network=network, response=ResponseInfo(status=200))

        line = format_metrics_line(step)

        assert "proxy=disabled" in line
        assert 'proxy_from=--proxy ""' in line

    def test_format_metrics_line_proxy_no_scheme_match(self) -> None:
        """Test metrics line shows no matching proxy scheme."""
        network = NetworkInfo(proxy_source=PROXY_SOURCE_NO_MATCH)
        step = StepMetrics(step_number=1, network=network, response=ResponseInfo(status=200))

        line = format_metrics_line(step)

        assert "proxy=direct" in line
        assert "proxy_from=no_scheme_match" in line

    def test_format_metrics_line_proxy_direct(self) -> None:
        """Test metrics line shows direct when no proxy configured."""
        step = StepMetrics(step_number=1, response=ResponseInfo(status=200))

        line = format_metrics_line(step)

        assert "proxy=direct" in line
        assert "proxy_from" not in line

    def test_format_metrics_line_slo_pass(self) -> None:
        """A passing SLO appends ``slo=pass`` without a violations list."""
        step = StepMetrics(step_number=1, response=ResponseInfo(status=200))
        result = SLOResult(thresholds_ms={"total": 500.0}, violations=())

        line = format_metrics_line(step, slo_result=result)

        assert line.endswith("slo=pass")
        assert "slo_violations" not in line

    def test_format_metrics_line_slo_fail(self) -> None:
        """A failing SLO appends ``slo=fail`` and violations list."""
        step = StepMetrics(step_number=1, response=ResponseInfo(status=200))
        violation = SLOViolation(key="total", threshold_ms=500.0, actual_ms=900.0)
        result = SLOResult(thresholds_ms={"total": 500.0}, violations=(violation,))

        line = format_metrics_line(step, slo_result=result)

        assert "slo=fail" in line
        assert "slo_violations=total" in line

    def test_format_metrics_line_slo_multiple_violations(self) -> None:
        """Multiple violations are joined by commas in stable order."""
        step = StepMetrics(step_number=1, response=ResponseInfo(status=200))
        violations = (
            SLOViolation(key="connect", threshold_ms=100.0, actual_ms=150.0),
            SLOViolation(key="total", threshold_ms=500.0, actual_ms=900.0),
            SLOViolation(key="ttfb", threshold_ms=200.0, actual_ms=300.0),
        )
        result = SLOResult(thresholds_ms={}, violations=violations)

        line = format_metrics_line(step, slo_result=result)

        assert "slo_violations=connect,total,ttfb" in line


class TestFormatCompactLine:
    """Human-readable single-line output for ``--compact``."""

    def _make_step(
        self,
        *,
        status: int | None = 200,
        bytes_: int = 1234,
        method: str = "GET",
        url: str = "https://example.com",
        total_ms: float = 234.7,
    ) -> StepMetrics:
        timing = TimingMetrics(
            dns_ms=1.5,
            connect_ms=45.2,
            tls_ms=67.8,
            ttfb_ms=156.4,
            total_ms=total_ms,
        )
        return StepMetrics(
            url=url,
            step_number=1,
            timing=timing,
            response=ResponseInfo(status=status, bytes=bytes_),
            request_method=method,
        )

    def test_contains_all_phase_timings_with_ms_suffix(self) -> None:
        line = format_compact_line(self._make_step())
        for phase in ("dns=1.5ms", "connect=45.2ms", "tls=67.8ms", "ttfb=156.4ms", "total=234.7ms"):
            assert phase in line

    def test_leads_with_status_and_method(self) -> None:
        line = format_compact_line(self._make_step(status=200, method="GET"))
        assert line.startswith("Step 1: 200 GET https://example.com")

    def test_renders_human_readable_size(self) -> None:
        line = format_compact_line(self._make_step(bytes_=2048))
        assert line.endswith("2.0 KB")

    def test_small_size_shows_bytes(self) -> None:
        line = format_compact_line(self._make_step(bytes_=500))
        assert line.endswith("500 B")

    def test_missing_status_rendered_as_dash(self) -> None:
        step = self._make_step(status=None)
        line = format_compact_line(step)
        assert line.startswith("Step 1: — ")

    def test_defaults_method_to_get_when_absent(self) -> None:
        step = StepMetrics(
            step_number=1,
            url="https://example.com",
            timing=TimingMetrics(total_ms=100.0),
            response=ResponseInfo(status=200, bytes=0),
        )
        line = format_compact_line(step)
        assert " GET " in line

    def test_single_line_no_newlines(self) -> None:
        line = format_compact_line(self._make_step())
        assert "\n" not in line


class TestFormatSLOPanel:
    """``format_slo_panel`` produces a Rich panel matching the SLO status."""

    @staticmethod
    def _panel_text(result: SLOResult) -> str:
        from rich.console import Console

        console = Console(record=True, width=120)
        console.print(format_slo_panel(result))
        return console.export_text()

    def test_pass_panel_shows_thresholds(self) -> None:
        result = SLOResult(
            thresholds_ms={"total": 500.0, "ttfb": 200.0},
            violations=(),
        )
        text = self._panel_text(result)

        assert "SLO: pass" in text
        assert "total≤500ms" in text
        assert "ttfb≤200ms" in text
        assert "Violations" not in text

    def test_fail_panel_lists_violations(self) -> None:
        violation = SLOViolation(key="total", threshold_ms=500.0, actual_ms=723.4)
        result = SLOResult(
            thresholds_ms={"total": 500.0},
            violations=(violation,),
        )
        text = self._panel_text(result)

        assert "SLO: fail" in text
        assert "Violations" in text
        assert "total" in text
        assert "723.4" in text
        assert "500" in text
        assert "+223.4" in text

    def test_panel_with_no_thresholds_shows_placeholder(self) -> None:
        result = SLOResult(thresholds_ms={}, violations=())
        text = self._panel_text(result)

        assert "SLO: pass" in text
        assert "(none)" in text
