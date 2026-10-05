"""OTLP export against the real OpenTelemetry SDK and a local collector."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

import pytest

from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.otlp import OTLPExporter, OTLPExportError

trace_service_pb2 = pytest.importorskip("opentelemetry.proto.collector.trace.v1.trace_service_pb2")
pytest.importorskip("opentelemetry.sdk.trace")

if TYPE_CHECKING:
    from collections.abc import Iterator


class _Collector(BaseHTTPRequestHandler):
    received: list[bytes]

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        type(self).received.append(self.rfile.read(length))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        """Keep the test output free of per-request access logs."""


@pytest.fixture
def collector() -> Iterator[tuple[str, list[bytes]]]:
    handler = type("Collector", (_Collector,), {"received": []})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1/traces", handler.received
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _step(number: int, status: int, total_ms: float) -> StepMetrics:
    timing = TimingMetrics(dns_ms=1.0, connect_ms=2.0, tls_ms=3.0, ttfb_ms=10.0, total_ms=total_ms)
    timing.calculate_derived()
    return StepMetrics(
        url=f"https://example.test/{number}",
        step_number=number,
        request_method="GET",
        timing=timing,
        network=NetworkInfo(ip="192.0.2.1"),
        response=ResponseInfo(status=status),
    )


def test_redirect_chain_is_exported_as_one_sequential_trace(collector: tuple[str, list[bytes]]) -> None:
    endpoint, received = collector

    OTLPExporter().export([_step(1, 302, 20.0), _step(2, 200, 30.0)], endpoint, timeout=5.0)

    request = trace_service_pb2.ExportTraceServiceRequest()
    request.ParseFromString(received[0])
    spans = [span for rs in request.resource_spans for ss in rs.scope_spans for span in ss.spans]
    by_name: dict[str, list] = {}
    for span in spans:
        by_name.setdefault(span.name, []).append(span)

    (root,) = by_name["httptap.analysis"]
    first, second = sorted(by_name["http.request"], key=lambda span: span.start_time_unix_nano)
    assert {span.trace_id for span in spans} == {root.trace_id}
    assert first.parent_span_id == root.span_id
    assert second.parent_span_id == root.span_id
    assert first.end_time_unix_nano <= second.start_time_unix_nano
    assert root.start_time_unix_nano == first.start_time_unix_nano
    assert root.end_time_unix_nano == second.end_time_unix_nano
    assert len(by_name["http.dns"]) == 2


def test_unreachable_collector_fails_within_timeout() -> None:
    with pytest.raises(OTLPExportError, match="Failed to export traces"):
        OTLPExporter().export([_step(1, 200, 10.0)], "http://127.0.0.1:9/v1/traces", timeout=1.0)
