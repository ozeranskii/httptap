"""Optional OpenTelemetry OTLP trace export."""

from __future__ import annotations

import time
from importlib import import_module
from typing import TYPE_CHECKING, Any, NamedTuple

from .utils import redact_url_credentials, url_hostname

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .models import StepMetrics

_PHASES = ("dns", "connect", "tls", "wait", "xfer")


class OTLPDependencyError(RuntimeError):
    """Raised when OTLP export is requested without the optional extra."""


class OTLPExportError(RuntimeError):
    """Raised when an OTLP collector rejects or cannot receive spans."""


def ensure_otel_available() -> None:
    """Raise a clear error unless the optional OpenTelemetry packages exist."""
    try:
        import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        import_module("opentelemetry.sdk.trace")
    except ImportError as exc:
        msg = "OTLP export requires the optional dependency. Install it with 'pip install httptap[otel]'."
        raise OTLPDependencyError(msg) from exc


class _OTel(NamedTuple):
    """OpenTelemetry entry points, imported only when OTLP export is requested."""

    trace: Any
    tracer_provider: Any
    span_exporter: Any
    span_export_result: Any
    simple_span_processor: Any
    in_memory_span_exporter: Any


class OTLPExporter:
    """Export a redirect chain as one trace: a root span, one span per request and child spans per phase."""

    def export(self, steps: Sequence[StepMetrics], endpoint: str, *, timeout: float) -> None:
        """Send request traces to an OTLP/HTTP endpoint.

        Args:
            steps: Request steps to export.
            endpoint: OTLP/HTTP traces endpoint.
            timeout: Upper bound in seconds for delivering the spans, including
                the exporter's own retries.

        Raises:
            OTLPDependencyError: If the ``otel`` extra is not installed.
            OTLPExportError: If the collector rejects or cannot receive the spans.

        """
        otel = self._load_dependencies()
        finished_spans = otel.in_memory_span_exporter()
        provider = otel.tracer_provider()
        provider.add_span_processor(otel.simple_span_processor(finished_spans))
        exporter = otel.span_exporter(endpoint=endpoint, timeout=timeout)
        shown_endpoint = redact_url_credentials(endpoint)

        try:
            self._record_chain(otel.trace, provider.get_tracer("httptap"), steps)
            result = exporter.export(finished_spans.get_finished_spans())
        except Exception as exc:
            reason = str(exc).replace(endpoint, shown_endpoint)
            msg = f"Failed to export traces to OTLP endpoint '{shown_endpoint}': {reason}"
            raise OTLPExportError(msg) from exc
        finally:
            provider.shutdown()
            exporter.shutdown()

        if result != otel.span_export_result.SUCCESS:
            msg = f"Failed to export traces to OTLP endpoint '{shown_endpoint}'."
            raise OTLPExportError(msg)

    @staticmethod
    def _load_dependencies() -> _OTel:
        """Load optional OpenTelemetry modules only when OTLP is requested."""
        try:
            trace = import_module("opentelemetry.trace")
            sdk_trace = import_module("opentelemetry.sdk.trace")
            sdk_export = import_module("opentelemetry.sdk.trace.export")
            in_memory = import_module("opentelemetry.sdk.trace.export.in_memory_span_exporter")
            otlp_http = import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        except ImportError as exc:
            msg = "OTLP export requires the optional dependency. Install it with 'pip install httptap[otel]'."
            raise OTLPDependencyError(msg) from exc
        return _OTel(
            trace=trace,
            tracer_provider=sdk_trace.TracerProvider,
            span_exporter=otlp_http.OTLPSpanExporter,
            span_export_result=sdk_export.SpanExportResult,
            simple_span_processor=sdk_export.SimpleSpanProcessor,
            in_memory_span_exporter=in_memory.InMemorySpanExporter,
        )

    @staticmethod
    def _record_chain(trace: Any, tracer: Any, steps: Sequence[StepMetrics]) -> None:  # noqa: ANN401
        """Lay the steps out back to back under one root span ending at export time.

        httptap measures durations, not wall-clock start times, so the chain is
        reconstructed backwards from the moment of export, which follows the
        requests immediately in the CLI flow.
        """
        chain_end = time.time_ns()
        chain_start = chain_end - sum(_ns(step.timing.total_ms) for step in steps)
        root = tracer.start_span("httptap.analysis", start_time=chain_start)
        try:
            root.set_attribute("httptap.steps", len(steps))
            if steps and any(step.error for step in steps):
                root.set_status(trace.Status(trace.StatusCode.ERROR, steps[-1].error or "request failed"))
            context = trace.set_span_in_context(root)
            step_start = chain_start
            for step in steps:
                step_start = OTLPExporter._record_step(trace, tracer, step, step_start, context)
        finally:
            root.end(end_time=chain_end)

    @staticmethod
    def _record_step(trace: Any, tracer: Any, step: StepMetrics, start_time: int, context: Any) -> int:  # noqa: ANN401
        """Record one request span with timing-phase children; return its end time."""
        end_time = start_time + _ns(step.timing.total_ms)
        span = tracer.start_span("http.request", context=context, start_time=start_time)
        try:
            span.set_attribute("httptap.step_number", step.step_number)
            OTLPExporter._set_attributes(span, step)
            if step.error:
                span.set_status(trace.Status(trace.StatusCode.ERROR, step.error))

            phase_context = trace.set_span_in_context(span)
            phase_start = start_time
            for phase in _PHASES:
                duration_ms = getattr(step.timing, f"{phase}_ms")
                phase_end = min(phase_start + _ns(duration_ms), end_time)
                phase_span = tracer.start_span(f"http.{phase}", context=phase_context, start_time=phase_start)
                phase_span.set_attribute("httptap.phase", phase)
                phase_span.set_attribute("httptap.duration_ms", duration_ms)
                phase_span.end(end_time=phase_end)
                phase_start = phase_end
        finally:
            span.end(end_time=end_time)
        return end_time

    @staticmethod
    def _set_attributes(span: Any, step: StepMetrics) -> None:  # noqa: ANN401
        """Attach non-sensitive request, response, and network attributes."""
        if step.request_method:
            span.set_attribute("http.request.method", step.request_method)
        if step.response.status is not None:
            span.set_attribute("http.response.status_code", step.response.status)
        span.set_attribute("http.response.body.size", step.response.bytes)
        hostname = url_hostname(step.url)
        if hostname:
            span.set_attribute("server.address", hostname)
        if step.network.ip:
            span.set_attribute("network.peer.address", step.network.ip)
        if step.network.http_version:
            span.set_attribute("network.protocol.version", step.network.http_version)
        if step.network.tls_version:
            span.set_attribute("tls.protocol.version", step.network.tls_version)


def _ns(milliseconds: float) -> int:
    """Convert a non-negative duration in milliseconds to nanoseconds."""
    return max(0, int(milliseconds * 1_000_000))
