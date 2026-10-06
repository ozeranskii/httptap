"""HAR 1.2 (HTTP Archive) export of the analysed request chain.

The document follows http://www.softwareishard.com/blog/har-12-spec/ so that
browser DevTools and HAR viewers can open an httptap run. httptap-specific data
is stored in ``_``-prefixed fields, which the specification reserves for
custom extensions.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl

from rich.markup import escape

from ._pkgmeta import get_package_info
from .utils import UTC, write_text_atomically

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from rich.console import Console

    from .models import StepMetrics

HAR_VERSION = "1.2"
PAGE_ID = "page_1"
UNKNOWN_MIME_TYPE = "x-unknown"
NOT_AVAILABLE = -1

_NS_PER_MS = 1_000_000
_NS_PER_SECOND = 1_000_000_000


class HARExporter:
    """Export a request chain as a HAR 1.2 document."""

    __slots__ = ("console",)

    def __init__(self, console: Console) -> None:
        """Initialize the exporter.

        Args:
            console: Console used for export status messages.

        """
        self.console = console

    def export(self, steps: Sequence[StepMetrics], initial_url: str, output_path: str) -> None:
        """Write the HAR document to ``output_path``, or to stdout for ``-``.

        Files are written atomically, so a viewer never opens a truncated
        archive.

        Args:
            steps: Request steps to export, in chain order.
            initial_url: Redacted URL the analysis started from.
            output_path: Destination path, or ``-`` for standard output.

        Raises:
            OSError: If the destination cannot be written.

        """
        document = build_har(steps, initial_url)
        if output_path == "-":
            json.dump(document, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
            return
        write_text_atomically(json.dumps(document, indent=2, ensure_ascii=False) + "\n", Path(output_path))
        self.console.print(f"\n[green]✓ Exported HAR to {escape(output_path)}[/green]")


def build_har(steps: Sequence[StepMetrics], initial_url: str, *, now_ns: int | None = None) -> dict[str, Any]:
    """Build a HAR 1.2 document with one page for the run and one entry per step.

    httptap measures durations, not wall-clock start times, so the entries are
    laid out back to back ending at ``now_ns`` (the moment of export by
    default), which follows the requests immediately in the CLI flow.

    Args:
        steps: Request steps, in chain order. Their URLs and headers are
            already redacted by the analyzer.
        initial_url: Redacted URL the analysis started from, used as the
            page title.
        now_ns: End of the chain in nanoseconds since the epoch.

    Returns:
        The HAR document as a JSON-serializable dictionary.

    """
    chain_end = time.time_ns() if now_ns is None else now_ns
    timings = [_timings(step) for step in steps]
    durations = [_entry_time(step_timings) for step_timings in timings]
    chain_start = chain_end - sum(_ns(duration) for duration in durations)

    entries = []
    entry_start = chain_start
    for step, step_timings, duration in zip(steps, timings, durations, strict=True):
        entries.append(_entry(step, step_timings, duration, entry_start))
        entry_start += _ns(duration)

    return {
        "log": {
            "version": HAR_VERSION,
            "creator": {"name": "httptap", "version": get_package_info().version},
            "pages": [
                {
                    "startedDateTime": _iso_timestamp(chain_start),
                    "id": PAGE_ID,
                    "title": initial_url,
                    "pageTimings": {"onContentLoad": NOT_AVAILABLE, "onLoad": NOT_AVAILABLE},
                }
            ],
            "entries": entries,
        }
    }


def _entry(step: StepMetrics, timings: dict[str, Any], duration: float, start_ns: int) -> dict[str, Any]:
    """Build one HAR entry, adding httptap's custom fields only when they apply."""
    entry: dict[str, Any] = {
        "pageref": PAGE_ID,
        "startedDateTime": _iso_timestamp(start_ns),
        "time": duration,
        "request": _request(step),
        "response": _response(step),
        "cache": {},
        "timings": timings,
    }
    if step.network.ip:
        entry["serverIPAddress"] = step.network.ip
    if step.network.tls_version:
        entry["_tls"] = {
            "version": step.network.tls_version,
            "cipher": step.network.tls_cipher,
            "certCN": step.network.cert_cn,
            "certIssuer": step.network.cert_issuer,
            "certDaysLeft": step.network.cert_days_left,
            "verified": step.network.tls_verified,
        }
    if step.proxied_via:
        entry["_proxy"] = {"url": step.proxied_via, "source": step.network.proxy_source}
    if step.redirect_limit_reached:
        entry["_redirectLimitReached"] = True
    return entry


def _request(step: StepMetrics) -> dict[str, Any]:
    """Describe the request; the body itself is never exported, only its size."""
    return {
        "method": step.request_method or "",
        "url": step.url,
        "httpVersion": step.network.http_version or "",
        "cookies": [],
        "headers": _name_value_pairs(step.request_headers),
        "queryString": _query_string(step.url),
        "headersSize": NOT_AVAILABLE,
        "bodySize": step.request_body_bytes,
    }


def _status_text(status: int | None) -> str:
    """Return the standard reason phrase for ``status``; httptap does not record the one sent."""
    if status is None:
        return ""
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return ""


def _response(step: StepMetrics) -> dict[str, Any]:
    """Describe the response, or an empty one (status 0) when none arrived.

    A failure is reported in ``_error`` inside the response, where Chrome
    DevTools looks for it when importing a HAR.
    """
    response = step.response
    received = response.status is not None
    har_response: dict[str, Any] = {
        "status": response.status if received else 0,
        "statusText": _status_text(response.status),
        "httpVersion": step.network.http_version or "",
        "cookies": [],
        "headers": _name_value_pairs(response.headers),
        "content": {
            # httptap counts the body as transferred and never decodes it, so
            # the encoded size is the best available value.
            "size": response.bytes if received else 0,
            "mimeType": response.content_type or UNKNOWN_MIME_TYPE,
        },
        "redirectURL": response.location or "",
        "headersSize": NOT_AVAILABLE,
        "bodySize": response.bytes if received else NOT_AVAILABLE,
        "_transferSize": response.bytes if received else NOT_AVAILABLE,
    }
    if step.error is not None:
        har_response["_error"] = step.error
        har_response["_errorKind"] = step.error_kind
    return har_response


def _timings(step: StepMetrics) -> dict[str, Any]:
    """Map httptap's phases onto HAR timings.

    HAR's ``connect`` includes the TLS handshake, which is also reported on its
    own as ``ssl``; ``ssl`` must therefore not be added again to ``time``.
    A failed step has no measured phases, so its optional timings are marked
    as not available rather than exported as a misleading zero.
    """
    if step.has_error:
        return {
            "blocked": NOT_AVAILABLE,
            "dns": NOT_AVAILABLE,
            "connect": NOT_AVAILABLE,
            "send": 0,
            "wait": 0,
            "receive": 0,
            "ssl": NOT_AVAILABLE,
        }
    timing = step.timing
    timings: dict[str, Any] = {
        "blocked": NOT_AVAILABLE,
        "dns": _round_ms(timing.dns_ms),
        "connect": _round_ms(timing.connect_ms + timing.tls_ms),
        "send": 0,
        "wait": _round_ms(timing.wait_ms),
        "receive": _round_ms(timing.xfer_ms),
        "ssl": _round_ms(timing.tls_ms) if step.url.lower().startswith("https:") else NOT_AVAILABLE,
    }
    if timing.is_estimated:
        timings["_estimated"] = True
    return timings


def _entry_time(timings: Mapping[str, Any]) -> float:
    """Return the entry duration: the sum of the available timings, excluding ``ssl``."""
    phases = ("blocked", "dns", "connect", "send", "wait", "receive")
    return _round_ms(sum(timings[phase] for phase in phases if timings[phase] != NOT_AVAILABLE))


def _name_value_pairs(headers: Mapping[str, str]) -> list[dict[str, str]]:
    return [{"name": name, "value": value} for name, value in headers.items()]


def _query_string(url: str) -> list[dict[str, str]]:
    """Parse the query of ``url`` textually, so a malformed URL never raises."""
    query = url.partition("#")[0].partition("?")[2]
    return [{"name": name, "value": value} for name, value in parse_qsl(query, keep_blank_values=True)]


def _round_ms(value: float) -> float:
    return round(max(0.0, value), 3)


def _ns(milliseconds: float) -> int:
    return round(milliseconds * _NS_PER_MS)


def _iso_timestamp(epoch_ns: int) -> str:
    """Format nanoseconds since the epoch as ISO 8601 UTC with millisecond precision."""
    seconds, remainder = divmod(epoch_ns, _NS_PER_SECOND)
    moment = datetime.fromtimestamp(seconds, UTC) + timedelta(microseconds=remainder // 1000)
    return moment.isoformat(timespec="milliseconds")
