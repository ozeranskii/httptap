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
