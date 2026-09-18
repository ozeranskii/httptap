"""Tests for optional OTLP trace construction."""

from __future__ import annotations

import pytest

from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.otlp import OTLPDependencyError, OTLPExporter, OTLPExportError, ensure_otel_available


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}
        self.end_time: int | None = None
        self.status: object | None = None

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def set_status(self, status: object) -> None:
        self.status = status

    def end(self, *, end_time: int) -> None:
        self.end_time = end_time


class _Tracer:
    def __init__(self) -> None:
        self.spans: list[tuple[str, _Span, dict[str, object]]] = []

    def start_span(self, name: str, **kwargs: object) -> _Span:
        span = _Span()
        self.spans.append((name, span, kwargs))
        return span


class _Trace:
    class StatusCode:
        ERROR = "error"

    class Status:
        def __init__(self, code: str, description: str) -> None:
            self.code = code
            self.description = description

    @staticmethod
    def set_span_in_context(span: _Span) -> _Span:
        return span


class _Provider:
    def __init__(self, tracer: _Tracer) -> None:
        self.tracer = tracer
        self.processor: object | None = None
        self.shutdown_called = False

    def add_span_processor(self, processor: object) -> None:
        self.processor = processor

    def get_tracer(self, _name: str) -> _Tracer:
        return self.tracer

    def shutdown(self) -> None:
        self.shutdown_called = True


class _FailedExporter:
    def __init__(self, *, endpoint: str) -> None:
        self.endpoint = endpoint
        self.shutdown_called = False

    def export(self, _spans: list[object]) -> str:
        return "failure"

    def shutdown(self) -> None:
        self.shutdown_called = True


class _SpanExportResult:
    SUCCESS = "success"


def _step() -> StepMetrics:
    timing = TimingMetrics(dns_ms=10.0, connect_ms=20.0, tls_ms=30.0, ttfb_ms=80.0, total_ms=100.0)
    timing.calculate_derived()
    return StepMetrics(
        url="https://example.test/private?token=secret",
        step_number=2,
        request_method="GET",
        timing=timing,
        network=NetworkInfo(ip="192.0.2.1", http_version="HTTP/2", tls_version="TLSv1.3"),
        response=ResponseInfo(status=200, bytes=42),
    )


def test_otlp_exporter_creates_request_and_phase_spans() -> None:
    """Every request has child spans for its measured timing phases."""
    tracer = _Tracer()

    OTLPExporter._record_step(_Trace, tracer, _step())

    assert [name for name, _, _ in tracer.spans] == [
        "http.request",
        "http.dns",
        "http.connect",
        "http.tls",
        "http.wait",
        "http.xfer",
    ]
    request_span = tracer.spans[0][1]
    assert request_span.attributes["httptap.step_number"] == 2
    assert request_span.attributes["http.request.method"] == "GET"
    assert request_span.attributes["server.address"] == "example.test"
    assert "url.full" not in request_span.attributes
    assert tracer.spans[1][1].attributes == {"httptap.phase": "dns", "httptap.duration_ms": 10.0}


def test_ensure_otel_available_explains_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing optional dependencies produce an actionable error."""

    def raise_import_error(_name: str) -> None:
        raise ImportError

    monkeypatch.setattr("httptap.otlp.import_module", raise_import_error)

    with pytest.raises(OTLPDependencyError, match=r"httptap\[otel\]"):
        ensure_otel_available()


def test_otlp_exporter_reports_collector_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed collector response is propagated to the CLI layer."""
    tracer = _Tracer()
    provider = _Provider(tracer)
    exporter_instances: list[_FailedExporter] = []

    def make_provider() -> _Provider:
        return provider

    def make_exporter(*, endpoint: str) -> _FailedExporter:
        exporter = _FailedExporter(endpoint=endpoint)
        exporter_instances.append(exporter)
        return exporter

    monkeypatch.setattr(
        OTLPExporter,
        "_load_dependencies",
        staticmethod(lambda: (_Trace, make_provider, make_exporter, _SpanExportResult)),
    )

    with pytest.raises(OTLPExportError, match="Failed to export traces"):
        OTLPExporter().export([_step()], "http://collector.test:4318/v1/traces")

    assert provider.shutdown_called is True
    assert exporter_instances[0].shutdown_called is True
