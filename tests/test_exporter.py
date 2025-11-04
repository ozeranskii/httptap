from __future__ import annotations

import json
import pathlib

import pytest
from rich.console import Console

from httptap.exporter import JSONExporter
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics

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
    assert data["initial_url"] == "https://example.test"
    assert data["total_steps"] == 2
    assert data["summary"]["total_time_ms"] == pytest.approx(200.5)
    assert data["steps"][0]["response"]["status"] == 200

    output_text = console.export_text()
    assert "Exported analysis" in output_text


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
