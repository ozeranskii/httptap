"""Tests for OTLP trace construction with stand-ins for the OpenTelemetry SDK."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import ClassVar

import pytest

from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.otlp import OTLPDependencyError, OTLPExporter, OTLPExportError, _OTel, ensure_otel_available


class _Span:
    def __init__(self, name: str, kwargs: dict[str, object]) -> None:
        self.name = name
        self.kwargs = kwargs
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
        self.spans: list[_Span] = []

    def start_span(self, name: str, **kwargs: object) -> _Span:
        span = _Span(name, kwargs)
        self.spans.append(span)
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
    def __init__(self) -> None:
        self.tracer = _Tracer()
        self.processors: list[object] = []
        self.shutdown_called = False

    def add_span_processor(self, processor: object) -> None:
        self.processors.append(processor)

    def get_tracer(self, _name: str) -> _Tracer:
        return self.tracer

    def shutdown(self) -> None:
        self.shutdown_called = True


class _InMemory:
    def get_finished_spans(self) -> list[str]:
        return ["span"]


class _Exporter:
    result = "success"
    instances: ClassVar[list[_Exporter]] = []

    def __init__(self, *, endpoint: str, timeout: float) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.exported: list[object] = []
        self.shutdown_called = False
        type(self).instances.append(self)

    def export(self, spans: list[object]) -> str:
        self.exported.extend(spans)
        return self.result

    def shutdown(self) -> None:
        self.shutdown_called = True


class _RejectingExporter(_Exporter):
    result = "failure"


class _RaisingExporter(_Exporter):
    def export(self, spans: list[object]) -> str:
        del spans
        message = "connection refused"
        raise OSError(message)


def _install(monkeypatch: pytest.MonkeyPatch, exporter_cls: type[_Exporter]) -> _Provider:
    provider = _Provider()
    exporter_cls.instances = []
    otel = _OTel(
        trace=_Trace,
        tracer_provider=lambda: provider,
        span_exporter=exporter_cls,
        span_export_result=SimpleNamespace(SUCCESS="success"),
        simple_span_processor=lambda exporter: ("processor", exporter),
        in_memory_span_exporter=_InMemory,
    )
    monkeypatch.setattr(OTLPExporter, "_load_dependencies", staticmethod(lambda: otel))
    return provider


def _step(number: int = 1, *, total_ms: float = 100.0, error: str | None = None) -> StepMetrics:
    timing = TimingMetrics(dns_ms=10.0, connect_ms=20.0, tls_ms=30.0, ttfb_ms=80.0, total_ms=total_ms)
    timing.calculate_derived()
    return StepMetrics(
        url="https://example.test/private?token=secret",
        step_number=number,
        request_method="GET",
        timing=timing,
        network=NetworkInfo(ip="192.0.2.1", http_version="HTTP/2", tls_version="TLSv1.3"),
        response=ResponseInfo(status=200, bytes=42),
        error=error,
    )


def test_chain_is_one_trace_with_sequential_steps() -> None:
    """Steps are laid out back to back under a single root span."""
    tracer = _Tracer()

    OTLPExporter._record_chain(_Trace, tracer, [_step(1, total_ms=100.0), _step(2, total_ms=50.0)])

    names = [span.name for span in tracer.spans]
    assert names[0] == "httptap.analysis"
    assert names.count("http.request") == 2
    root = tracer.spans[0]
    first, second = (span for span in tracer.spans if span.name == "http.request")
    assert first.kwargs["context"] is root
    assert second.kwargs["context"] is root
    assert first.end_time == second.kwargs["start_time"]
    assert root.kwargs["start_time"] == first.kwargs["start_time"]
    assert root.end_time == second.end_time
    assert second.end_time - first.kwargs["start_time"] == 150_000_000
    assert root.attributes == {"httptap.steps": 2}


def test_request_span_has_phase_children_and_safe_attributes() -> None:
    tracer = _Tracer()

    OTLPExporter._record_chain(_Trace, tracer, [_step(2)])

    request = next(span for span in tracer.spans if span.name == "http.request")
    phases = [span for span in tracer.spans if span.name.startswith("http.") and span is not request]
    assert [span.name for span in phases] == ["http.dns", "http.connect", "http.tls", "http.wait", "http.xfer"]
    assert all(span.kwargs["context"] is request for span in phases)
    assert phases[0].attributes == {"httptap.phase": "dns", "httptap.duration_ms": 10.0}
    assert request.attributes["httptap.step_number"] == 2
    assert request.attributes["http.request.method"] == "GET"
    assert request.attributes["server.address"] == "example.test"
    assert "url.full" not in request.attributes


def test_failed_step_marks_request_and_root_as_errors() -> None:
    tracer = _Tracer()

    OTLPExporter._record_chain(_Trace, tracer, [_step(error="Request failed: connection refused")])

    root, request = tracer.spans[0], tracer.spans[1]
    assert isinstance(root.status, _Trace.Status)
    assert isinstance(request.status, _Trace.Status)
    assert request.status.description == "Request failed: connection refused"


def test_step_without_optional_fields_sets_only_known_attributes() -> None:
    tracer = _Tracer()

    OTLPExporter._record_chain(_Trace, tracer, [StepMetrics(url="not a url")])

    request = tracer.spans[1]
    assert set(request.attributes) == {"httptap.step_number", "http.response.body.size"}


def test_step_with_malformed_url_has_no_server_address() -> None:
    tracer = _Tracer()

    OTLPExporter._record_chain(_Trace, tracer, [StepMetrics(url="http://[::1/next", error="Invalid redirect target")])

    assert "server.address" not in tracer.spans[1].attributes


def test_export_sends_finished_spans_with_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _install(monkeypatch, _Exporter)

    OTLPExporter().export([_step()], "http://collector.test:4318/v1/traces", timeout=3.0)

    exporter = _Exporter.instances[0]
    assert exporter.endpoint == "http://collector.test:4318/v1/traces"
    assert exporter.timeout == 3.0
    assert exporter.exported == ["span"]
    assert provider.processors[0][0] == "processor"
    assert provider.shutdown_called is True
    assert exporter.shutdown_called is True


def test_export_reports_rejected_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _RejectingExporter)

    with pytest.raises(OTLPExportError, match="Failed to export traces"):
        OTLPExporter().export([_step()], "http://collector.test:4318/v1/traces", timeout=3.0)


def test_export_wraps_delivery_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _install(monkeypatch, _RaisingExporter)

    with pytest.raises(OTLPExportError, match="connection refused"):
        OTLPExporter().export([_step()], "http://collector.test:4318/v1/traces", timeout=3.0)

    assert provider.shutdown_called is True


@pytest.mark.parametrize("exporter_cls", [_RejectingExporter, _RaisingExporter])
def test_export_errors_redact_endpoint_credentials(
    exporter_cls: type[_Exporter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, exporter_cls)

    with pytest.raises(OTLPExportError) as exc_info:
        OTLPExporter().export([_step()], "http://bob:otlpsecret@collector.test:4318/v1/traces", timeout=3.0)

    assert "http://bob:****@collector.test:4318/v1/traces" in str(exc_info.value)
    assert "otlpsecret" not in str(exc_info.value)
    assert exporter_cls.instances[0].endpoint == "http://bob:otlpsecret@collector.test:4318/v1/traces"


def test_ensure_otel_available_explains_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_import_error(_name: str) -> None:
        raise ImportError

    monkeypatch.setattr("httptap.otlp.import_module", raise_import_error)

    with pytest.raises(OTLPDependencyError, match=r"httptap\[otel\]"):
        ensure_otel_available()


def test_ensure_otel_available_passes_when_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    imported: list[str] = []
    monkeypatch.setattr("httptap.otlp.import_module", imported.append)

    ensure_otel_available()

    assert imported == ["opentelemetry.exporter.otlp.proto.http.trace_exporter", "opentelemetry.sdk.trace"]


def test_load_dependencies_returns_sdk_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace(
        TracerProvider="provider",
        SpanExportResult="result",
        SimpleSpanProcessor="processor",
        InMemorySpanExporter="memory",
        OTLPSpanExporter="exporter",
    )
    monkeypatch.setattr("httptap.otlp.import_module", lambda _name: module)

    assert OTLPExporter._load_dependencies() == _OTel(
        trace=module,
        tracer_provider="provider",
        span_exporter="exporter",
        span_export_result="result",
        simple_span_processor="processor",
        in_memory_span_exporter="memory",
    )


def test_load_dependencies_explains_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_import_error(_name: str) -> None:
        raise ImportError

    monkeypatch.setattr("httptap.otlp.import_module", raise_import_error)

    with pytest.raises(OTLPDependencyError, match=r"httptap\[otel\]"):
        OTLPExporter._load_dependencies()


class _LoggingExporter(_Exporter):
    def export(self, spans: list[object]) -> str:
        logging.getLogger("opentelemetry.exporter.otlp.proto.http").warning("Transient error, retrying")
        return super().export(spans)


def test_export_holds_back_sdk_warnings(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _install(monkeypatch, _LoggingExporter)
    sdk_logger = logging.getLogger("opentelemetry")
    previous_level = sdk_logger.level

    with caplog.at_level(logging.WARNING):
        OTLPExporter().export([_step()], "http://collector.test:4318/v1/traces", timeout=3.0)

    assert "Transient error" not in caplog.text
    assert sdk_logger.level == previous_level
