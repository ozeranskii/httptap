"""Performance benchmarks for httptap core modules.

These benchmarks target pure-computation functions in the models,
formatters, utils, exporter, and visualizer modules to track
performance over time.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from httptap.constants import HTTPMethod
from httptap.exporter import JSONExporter
from httptap.formatters import (
    format_bytes_human,
    format_error,
    format_metrics_line,
    format_network_info,
    format_response_info,
    format_step_header,
)
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.utils import (
    calculate_days_until,
    mask_sensitive_value,
    parse_certificate_date,
    parse_http_date,
    sanitize_headers,
    validate_url,
)
from httptap.visualizer import WaterfallVisualizer

if TYPE_CHECKING:
    from pytest_codspeed.plugin import BenchmarkFixture


@pytest.fixture
def sample_timing() -> TimingMetrics:
    return TimingMetrics(
        dns_ms=10.5,
        connect_ms=45.2,
        tls_ms=67.8,
        ttfb_ms=156.4,
        total_ms=234.7,
    )


@pytest.fixture
def sample_network() -> NetworkInfo:
    return NetworkInfo(
        ip="93.184.216.34",
        ip_family="IPv4",
        http_version="HTTP/2.0",
        tls_version="TLSv1.3",
        tls_cipher="TLS_AES_256_GCM_SHA384",
        cert_cn="example.com",
        cert_days_left=120,
        tls_verified=True,
    )


@pytest.fixture
def sample_response() -> ResponseInfo:
    return ResponseInfo(
        status=200,
        bytes=4096,
        content_type="application/json",
        server="nginx/1.25",
        location=None,
    )


@pytest.fixture
def sample_step(
    sample_timing: TimingMetrics,
    sample_network: NetworkInfo,
    sample_response: ResponseInfo,
) -> StepMetrics:
    return StepMetrics(
        url="https://example.com/api/v1/data",
        step_number=1,
        timing=sample_timing,
        network=sample_network,
        response=sample_response,
        request_method=HTTPMethod.GET.value,
        request_headers={"Accept": "application/json"},
        request_body_bytes=0,
    )


@pytest.fixture
def sample_error_step(sample_timing: TimingMetrics, sample_network: NetworkInfo) -> StepMetrics:
    return StepMetrics(
        url="https://example.com/fail",
        step_number=1,
        timing=sample_timing,
        network=sample_network,
        error="Connection refused",
        note="Check if the server is running",
        request_method=HTTPMethod.GET.value,
        request_headers={},
        request_body_bytes=0,
    )


@pytest.mark.benchmark(group="models")
def test_bench_timing_calculate_derived(benchmark: BenchmarkFixture, sample_timing: TimingMetrics) -> None:
    benchmark(sample_timing.calculate_derived)


@pytest.mark.benchmark(group="models")
def test_bench_timing_to_dict(benchmark: BenchmarkFixture, sample_timing: TimingMetrics) -> None:
    benchmark(sample_timing.to_dict)


@pytest.mark.benchmark(group="models")
def test_bench_network_to_dict(benchmark: BenchmarkFixture, sample_network: NetworkInfo) -> None:
    benchmark(sample_network.to_dict)


@pytest.mark.benchmark(group="models")
def test_bench_response_to_dict(benchmark: BenchmarkFixture, sample_response: ResponseInfo) -> None:
    benchmark(sample_response.to_dict)


@pytest.mark.benchmark(group="models")
def test_bench_step_to_dict(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(sample_step.to_dict)


@pytest.mark.benchmark(group="models")
def test_bench_step_is_redirect(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(lambda: sample_step.is_redirect)


@pytest.mark.benchmark(group="models")
def test_bench_step_has_error(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(lambda: sample_step.has_error)


@pytest.mark.benchmark(group="formatters")
def test_bench_format_bytes_human_small(benchmark: BenchmarkFixture) -> None:
    benchmark(format_bytes_human, 512)


@pytest.mark.benchmark(group="formatters")
def test_bench_format_bytes_human_large(benchmark: BenchmarkFixture) -> None:
    benchmark(format_bytes_human, 1_048_576)


@pytest.mark.benchmark(group="formatters")
def test_bench_format_metrics_line(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(format_metrics_line, sample_step)


@pytest.mark.benchmark(group="formatters")
def test_bench_format_network_info(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(format_network_info, sample_step)


@pytest.mark.benchmark(group="formatters")
def test_bench_format_response_info(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(format_response_info, sample_step)


@pytest.mark.benchmark(group="formatters")
def test_bench_format_step_header(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(format_step_header, sample_step)


@pytest.mark.benchmark(group="formatters")
def test_bench_format_error(benchmark: BenchmarkFixture, sample_error_step: StepMetrics) -> None:
    benchmark(format_error, sample_error_step)


@pytest.mark.benchmark(group="utils")
def test_bench_mask_sensitive_value(benchmark: BenchmarkFixture) -> None:
    benchmark(mask_sensitive_value, "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret")


@pytest.mark.benchmark(group="utils")
def test_bench_sanitize_headers(benchmark: BenchmarkFixture) -> None:
    benchmark.pedantic(
        sanitize_headers,
        setup=lambda: (
            (),
            {
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "text/html",
                    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
                    "X-Request-Id": "abc-123-def-456",
                    "Cookie": "session=s3cr3t_v4lu3; tracking=abc123",
                },
            },
        ),
        warmup_rounds=1,
        rounds=5,
    )


@pytest.mark.benchmark(group="utils")
def test_bench_parse_http_date(benchmark: BenchmarkFixture) -> None:
    benchmark(parse_http_date, "Mon, 22 Oct 2025 12:00:00 GMT")


@pytest.mark.benchmark(group="utils")
def test_bench_parse_certificate_date(benchmark: BenchmarkFixture) -> None:
    benchmark(parse_certificate_date, "Oct 22 12:00:00 2025 GMT")


@pytest.mark.benchmark(group="utils")
def test_bench_validate_url_valid(benchmark: BenchmarkFixture) -> None:
    benchmark(validate_url, "https://example.com/api/v1/data?key=value")


@pytest.mark.benchmark(group="utils")
def test_bench_validate_url_invalid(benchmark: BenchmarkFixture) -> None:
    benchmark(validate_url, "ftp://example.com/file")


@pytest.mark.benchmark(group="utils")
def test_bench_calculate_days_until(benchmark: BenchmarkFixture) -> None:
    target = datetime.now(timezone.utc) + timedelta(days=120)
    benchmark(calculate_days_until, target)


@pytest.mark.benchmark(group="exporter")
def test_bench_build_summary(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark.pedantic(
        JSONExporter._build_summary,
        setup=lambda: (([sample_step] * 5, "https://example.com"), {}),
        warmup_rounds=1,
        rounds=5,
    )


@pytest.mark.benchmark(group="exporter")
def test_bench_step_to_json(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(lambda: json.dumps(sample_step.to_dict()))


@pytest.mark.benchmark(group="visualizer")
def test_bench_get_phases(benchmark: BenchmarkFixture, sample_step: StepMetrics) -> None:
    benchmark(WaterfallVisualizer._get_phases, sample_step)


@pytest.mark.benchmark(group="visualizer")
def test_bench_compute_phase_widths(benchmark: BenchmarkFixture) -> None:
    visualizer = WaterfallVisualizer(console=Console(quiet=True))
    durations = [10.5, 45.2, 67.8, 156.4, 234.7]
    benchmark(visualizer._compute_phase_widths, durations)
