"""Optional OpenTelemetry OTLP trace export."""

from __future__ import annotations

import time
from importlib import import_module
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .models import StepMetrics

_PHASES = ("dns", "connect", "tls", "wait", "xfer")


class OTLPDependencyError(RuntimeError):
    """Raised when OTLP export is requested without the optional extra."""


class OTLPExportError(RuntimeError):
    """Raised when an OTLP collector rejects or cannot receive spans."""


class _SpanCollector:
    """Collect completed spans for one synchronous CLI export."""

    def __init__(self) -> None:
        """Initialize an empty span collection."""
        self.spans: list[Any] = []

    def on_start(self, _span: Any, parent_context: Any | None = None) -> None:  # noqa: ANN401
        """Accept span start notifications required by ``TracerProvider``."""
        del parent_context

    def on_end(self, span: Any) -> None:  # noqa: ANN401
        """Collect a completed readable span."""
        self.spans.append(span)

    def shutdown(self) -> None:
        """Release no resources."""

    def force_flush(self, timeout_millis: int | None = None) -> bool:
        """Report that there is no asynchronous work to flush."""
        del timeout_millis
        return True


def ensure_otel_available() -> None:
    """Raise a clear error unless the optional OpenTelemetry packages exist."""
    try:
        import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        import_module("opentelemetry.sdk.trace")
    except ImportError as exc:
        msg = "OTLP export requires the optional dependency. Install it with 'pip install httptap[otel]'."
        raise OTLPDependencyError(msg) from exc


class OTLPExporter:
    """Export one OpenTelemetry span per request and child spans per phase."""

    def export(self, steps: Sequence[StepMetrics], endpoint: str) -> None:
        """Send request traces to an OTLP/HTTP endpoint.

        Args:
            steps: Request steps to export.
            endpoint: OTLP/HTTP traces endpoint.

        Raises:
            OTLPDependencyError: If the ``otel`` extra is not installed.

        """
        trace, tracer_provider, span_exporter, span_export_result = self._load_dependencies()
        provider = tracer_provider()
        collector = _SpanCollector()
        provider.add_span_processor(collector)
        tracer = provider.get_tracer("httptap")
        exporter = span_exporter(endpoint=endpoint)

        try:
            for step in steps:
                self._record_step(trace, tracer, step)
            result = exporter.export(collector.spans)
        except Exception as exc:
            msg = f"Failed to export traces to OTLP endpoint '{endpoint}': {exc}"
            raise OTLPExportError(msg) from exc
        finally:
            provider.shutdown()
            exporter.shutdown()

        if result != span_export_result.SUCCESS:
            msg = f"Failed to export traces to OTLP endpoint '{endpoint}'."
            raise OTLPExportError(msg)

    @staticmethod
    def _load_dependencies() -> tuple[Any, Any, Any, Any]:
        """Load optional OpenTelemetry modules only when OTLP is requested."""
        try:
            trace = import_module("opentelemetry.trace")
            tracer_provider = import_module("opentelemetry.sdk.trace").TracerProvider
            span_export_result = import_module("opentelemetry.sdk.trace.export").SpanExportResult
            span_exporter = import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter").OTLPSpanExporter
        except ImportError as exc:
            msg = "OTLP export requires the optional dependency. Install it with 'pip install httptap[otel]'."
            raise OTLPDependencyError(msg) from exc
        return trace, tracer_provider, span_exporter, span_export_result

    @staticmethod
    def _record_step(trace: Any, tracer: Any, step: StepMetrics) -> None:  # noqa: ANN401
        """Record one request span and timing-phase child spans."""
        end_time = time.time_ns()
        total_ns = max(0, int(step.timing.total_ms * 1_000_000))
        start_time = end_time - total_ns
        span = tracer.start_span("http.request", start_time=start_time)
        try:
            span.set_attribute("httptap.step_number", step.step_number)
            OTLPExporter._set_attributes(span, step)
            if step.error:
                span.set_status(trace.Status(trace.StatusCode.ERROR, step.error))

            parent_context = trace.set_span_in_context(span)
            phase_start = start_time
            for phase in _PHASES:
                duration_ms = getattr(step.timing, f"{phase}_ms")
                phase_end = min(phase_start + max(0, int(duration_ms * 1_000_000)), end_time)
                phase_span = tracer.start_span(
                    f"http.{phase}",
                    context=parent_context,
                    start_time=phase_start,
                )
                phase_span.set_attribute("httptap.phase", phase)
                phase_span.set_attribute("httptap.duration_ms", duration_ms)
                phase_span.end(end_time=phase_end)
                phase_start = phase_end
        finally:
            span.end(end_time=end_time)

    @staticmethod
    def _set_attributes(span: Any, step: StepMetrics) -> None:  # noqa: ANN401
        """Attach non-sensitive request, response, and network attributes."""
        if step.request_method:
            span.set_attribute("http.request.method", step.request_method)
        if step.response.status is not None:
            span.set_attribute("http.response.status_code", step.response.status)
        span.set_attribute("http.response.body.size", step.response.bytes)
        hostname = urlsplit(step.url).hostname
        if hostname:
            span.set_attribute("server.address", hostname)
        if step.network.ip:
            span.set_attribute("network.peer.address", step.network.ip)
        if step.network.http_version:
            span.set_attribute("network.protocol.version", step.network.http_version)
        if step.network.tls_version:
            span.set_attribute("tls.protocol.version", step.network.tls_version)
