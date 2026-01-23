"""Adapters and data structures for executing HTTP requests.

This module provides a clean separation between high-level analysis logic and
low-level request execution. It exposes a declarative RequestOptions object,
an outcome wrapper, and a default RequestExecutor implementation that uses
the built-in HTTP client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from httpx._types import ProxyTypes

    from .models import NetworkInfo, ResponseInfo, TimingMetrics
else:  # pragma: no cover - typing helper
    ProxyTypes = object  # type: ignore[assignment]

from .constants import HTTPMethod
from .http_client import make_request

if TYPE_CHECKING:
    from .interfaces import DNSResolver, TimingCollector, TLSInspector


@dataclass(slots=True)
class RequestOptions:
    """Aggregates all parameters required to perform a single HTTP request."""

    url: str
    timeout: float
    method: HTTPMethod = HTTPMethod.GET
    content: bytes | None = None
    http2: bool = True
    verify_ssl: bool = True
    ca_bundle_path: str | None = None
    dns_resolver: DNSResolver | None = None
    tls_inspector: TLSInspector | None = None
    timing_collector: TimingCollector | None = None
    force_new_connection: bool = True
    headers: Mapping[str, str] | None = None
    proxy: ProxyTypes | None = None


@dataclass(slots=True)
class RequestOutcome:
    """Wraps the collected timing, network, and response objects."""

    timing: TimingMetrics
    network: NetworkInfo
    response: ResponseInfo


@runtime_checkable
class RequestExecutor(Protocol):
    """Protocol describing modern request executors used by the analyzer."""

    def execute(self, options: RequestOptions) -> RequestOutcome:
        """Perform an HTTP request based on provided options."""


class HTTPClientRequestExecutor:
    """RequestExecutor that delegates to the built-in http client."""

    __slots__ = ()

    def execute(self, options: RequestOptions) -> RequestOutcome:
        """Perform an HTTP request using the default client."""
        timing, network, response = make_request(
            options.url,
            options.timeout,
            method=options.method,
            content=options.content,
            http2=options.http2,
            verify_ssl=options.verify_ssl,
            ca_bundle_path=options.ca_bundle_path,
            proxy=options.proxy,
            dns_resolver=options.dns_resolver,
            tls_inspector=options.tls_inspector,
            timing_collector=options.timing_collector,
            force_new_connection=options.force_new_connection,
            headers=options.headers,
        )
        return RequestOutcome(timing=timing, network=network, response=response)
