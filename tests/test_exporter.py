from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta

import pytest
from rich.console import Console

from httptap._pkgmeta import get_package_info
from httptap.constants import REDIRECT_LIMIT_NOTE
from httptap.exporter import JSONExporter
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.prometheus import PrometheusExporter, _label_value
from httptap.slo import SLOResult, SLOViolation

PathType = pathlib.Path


def build_step(url: str, status: int, total_ms: float) -> StepMetrics:
    timing = TimingMetrics(total_ms=total_ms)
    network = NetworkInfo(ip="192.0.2.1")
    response = ResponseInfo(status=status, bytes=128)
    return StepMetrics(
        url=url,
        step_number=1,
        timing=timing,
        network=network,
        response=response,
    )


def test_exporter_writes_expected_payload(tmp_path: PathType) -> None:
    console = Console(record=True)
    exporter = JSONExporter(console)

    steps = [
        build_step("https://example.test", 200, 120.5),
        build_step("https://example.test/next", 200, 80.0),
    ]

    output_path = tmp_path / "report.json"
    exporter.export(steps, "https://example.test", str(output_path))

    data = json.loads(output_path.read_text())
    assert data["schema_version"] == 1
    assert data["httptap_version"] == get_package_info().version
    assert data["timestamp"].endswith("Z")
    timestamp = datetime.fromisoformat(data["timestamp"])
    assert timestamp.utcoffset() == timedelta(0)
    assert data["initial_url"] == "https://example.test"
    assert data["total_steps"] == 2
    assert data["summary"]["total_time_ms"] == pytest.approx(200.5)
    assert data["steps"][0]["response"]["status"] == 200

    output_text = console.export_text()
    assert "Exported analysis" in output_text


def test_exporter_writes_to_stdout_for_dash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: PathType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dash writes JSON to stdout rather than creating a file."""
    monkeypatch.chdir(tmp_path)
    exporter = JSONExporter(Console(record=True))
    step = build_step("https://example.test", 200, 120.5)

    exporter.export([step], "https://example.test", "-")

    assert json.loads(capsys.readouterr().out)["initial_url"] == "https://example.test"
    assert not (tmp_path / "-").exists()


def test_exporter_includes_request_metadata(tmp_path: PathType) -> None:
    """Test that request metadata is included in JSON export."""
    console = Console(record=True)
    exporter = JSONExporter(console)

    step = StepMetrics(
        url="https://httpbin.test/post",
        step_number=1,
        request_method="POST",
        request_headers={"Content-Type": "application/json", "Authorization": "Bear****oken"},
        request_body_bytes=42,
        timing=TimingMetrics(total_ms=150.0),
        network=NetworkInfo(ip="192.0.2.1"),
        response=ResponseInfo(status=200, bytes=256),
    )

    output_path = tmp_path / "report.json"
    exporter.export([step], "https://httpbin.test/post", str(output_path))

    data = json.loads(output_path.read_text())
    assert "request" in data["steps"][0]
    assert data["steps"][0]["request"]["method"] == "POST"
    assert data["steps"][0]["request"]["headers"]["Content-Type"] == "application/json"
    assert data["steps"][0]["request"]["headers"]["Authorization"] == "Bear****oken"
    assert data["steps"][0]["request"]["body_bytes"] == 42


def test_exporter_includes_all_http_methods(tmp_path: PathType) -> None:
    """Test that all HTTP methods are correctly exported."""
    console = Console(record=True)
    exporter = JSONExporter(console)

    methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    steps = []

    for idx, method in enumerate(methods, 1):
        step = StepMetrics(
            url=f"https://httpbin.test/{method.lower()}",
            step_number=idx,
            request_method=method,
            request_body_bytes=0 if method in ("GET", "HEAD", "OPTIONS") else 24,
            timing=TimingMetrics(total_ms=100.0),
            network=NetworkInfo(ip="192.0.2.1"),
            response=ResponseInfo(status=200, bytes=128),
        )
        steps.append(step)

    output_path = tmp_path / "methods.json"
    exporter.export(steps, "https://httpbin.test/", str(output_path))

    data = json.loads(output_path.read_text())
    assert len(data["steps"]) == 7

    for idx, method in enumerate(methods):
        assert data["steps"][idx]["request"]["method"] == method


def test_exporter_with_empty_request_headers(tmp_path: PathType) -> None:
    """Test that empty request headers are handled correctly."""
    console = Console(record=True)
    exporter = JSONExporter(console)

    step = StepMetrics(
        url="https://httpbin.test/get",
        step_number=1,
        request_method="GET",
        request_headers={},
        request_body_bytes=0,
        timing=TimingMetrics(total_ms=100.0),
        network=NetworkInfo(ip="192.0.2.1"),
        response=ResponseInfo(status=200, bytes=128),
    )

    output_path = tmp_path / "empty_headers.json"
    exporter.export([step], "https://httpbin.test/get", str(output_path))

    data = json.loads(output_path.read_text())
    assert data["steps"][0]["request"]["headers"] == {}
    assert data["steps"][0]["request"]["method"] == "GET"
    assert data["steps"][0]["request"]["body_bytes"] == 0


def test_exporter_omits_slo_when_not_provided(tmp_path: PathType) -> None:
    """The ``slo`` key is absent from the summary unless explicitly set."""
    exporter = JSONExporter(Console(record=True))
    step = build_step("https://example.test", 200, 100.0)
    output_path = tmp_path / "no-slo.json"

    exporter.export([step], "https://example.test", str(output_path))

    data = json.loads(output_path.read_text())
    assert "slo" not in data["summary"]


def test_exporter_preserves_redirect_limit_response_data(tmp_path: PathType) -> None:
    """Redirect-limit warnings count as errors without discarding response data."""
    exporter = JSONExporter(Console(record=True))
    step = build_step("https://example.test/redirect", 302, 100.0)
    step.note = f"{REDIRECT_LIMIT_NOTE} (10)"
    step.redirect_limit_reached = True
    output_path = tmp_path / "redirect-limit.json"

    exporter.export([step], "https://example.test", str(output_path))

    data = json.loads(output_path.read_text())
    assert data["summary"] == {
        "total_time_ms": 100.0,
        "final_status": 302,
        "final_url": "https://example.test/redirect",
        "final_bytes": 128,
        "errors": 1,
    }


def test_exporter_includes_slo_pass(tmp_path: PathType) -> None:
    """A passing SLO is embedded as ``summary.slo`` with an empty violations list."""
    exporter = JSONExporter(Console(record=True))
    step = build_step("https://example.test", 200, 100.0)
    result = SLOResult(thresholds_ms={"total": 500.0}, violations=())
    output_path = tmp_path / "slo-pass.json"

    exporter.export(
        [step],
        "https://example.test",
        str(output_path),
        slo_result=result,
    )

    data = json.loads(output_path.read_text())
    assert data["summary"]["slo"] == {
        "pass": True,
        "thresholds_ms": {"total": 500.0},
        "violations": [],
    }


def test_exporter_includes_slo_fail(tmp_path: PathType) -> None:
    """A failing SLO lists violations with ``key``, thresholds, actual, delta."""
    exporter = JSONExporter(Console(record=True))
    step = build_step("https://example.test", 200, 900.0)
    violation = SLOViolation(key="total", threshold_ms=500.0, actual_ms=900.0)
    result = SLOResult(thresholds_ms={"total": 500.0}, violations=(violation,))
    output_path = tmp_path / "slo-fail.json"

    exporter.export(
        [step],
        "https://example.test",
        str(output_path),
        slo_result=result,
    )

    data = json.loads(output_path.read_text())
    slo = data["summary"]["slo"]
    assert slo["pass"] is False
    assert slo["thresholds_ms"] == {"total": 500.0}
    assert slo["violations"] == [
        {
            "key": "total",
            "threshold_ms": 500.0,
            "actual_ms": 900.0,
            "delta_ms": 400.0,
        }
    ]


def test_prometheus_exporter_writes_phase_gauges(tmp_path: PathType) -> None:
    """Prometheus output uses seconds and avoids a URL label."""
    step = build_step("https://example.test/private?token=secret", 200, 120.5)
    step.timing.dns_ms = 10.0
    step.timing.connect_ms = 20.0
    step.timing.ttfb_ms = 100.0
    step.timing.calculate_derived()
    output_path = tmp_path / "metrics" / "httptap.prom"

    PrometheusExporter(Console(record=True)).export([step], str(output_path))

    output = output_path.read_text(encoding="utf-8")
    assert "# TYPE httptap_request_duration_seconds gauge" in output
    assert "# TYPE httptap_response_status_code gauge" in output
    assert 'httptap_request_success{host="example.test",step="1"} 1' in output
    assert 'httptap_request_duration_seconds{host="example.test",step="1",phase="dns"} 0.01' in output
    assert 'httptap_response_status_code{host="example.test",step="1"} 200' in output
    assert 'httptap_last_run_timestamp_seconds{host="example.test"}' in output
    assert "/private" not in output
    assert "token" not in output


def test_prometheus_failed_step_exports_only_success_gauge() -> None:
    """A failed request must not look like a fast successful one."""
    step = build_step("https://down.example.test/", 200, 0.0)
    step.error = "Request failed: connection refused"

    output = PrometheusExporter._render([step], now=1700000000.0)

    assert 'httptap_request_success{host="down.example.test",step="1"} 0' in output
    assert "httptap_request_duration_seconds{" not in output
    assert "httptap_response_status_code{" not in output
    assert 'httptap_last_run_timestamp_seconds{host="down.example.test"} 1700000000.000' in output


def test_prometheus_render_without_steps_has_only_metadata() -> None:
    output = PrometheusExporter._render([])

    assert "{" not in output
    assert output.startswith("# HELP httptap_request_success")


def test_prometheus_status_omitted_when_unknown() -> None:
    step = build_step("https://example.test/", 200, 1.0)
    step.response.status = None

    assert "httptap_response_status_code{" not in PrometheusExporter._render([step], now=0.0)


def test_prometheus_label_values_are_escaped() -> None:
    assert _label_value('a"b\\c\nd') == 'a\\"b\\\\c\\nd'


def test_prometheus_write_failure_removes_temporary_file(tmp_path: PathType, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_replace(_self: PathType, _target: PathType) -> None:
        message = "read-only target"
        raise OSError(message)

    monkeypatch.setattr(pathlib.Path, "replace", fail_replace)
    output_path = tmp_path / "httptap.prom"

    with pytest.raises(OSError, match="read-only target"):
        PrometheusExporter(Console(record=True)).export(
            [build_step("https://example.test/", 200, 1.0)],
            str(output_path),
        )

    assert list(tmp_path.iterdir()) == []
