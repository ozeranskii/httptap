"""Adapters and data structures for executing HTTP requests.

This module provides a clean separation between high-level analysis logic and
low-level request execution. It exposes a declarative RequestOptions object,
an outcome wrapper, and an adapter that bridges legacy callables to the new
RequestExecutor protocol.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from httpx._types import ProxyTypes
else:  # pragma: no cover - typing helper
    ProxyTypes = object  # type: ignore[assignment]

from .constants import HTTPMethod
from .models import NetworkInfo, ResponseInfo, TimingMetrics

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


LegacyExecutorType = Callable[
    ...,
    tuple[TimingMetrics, NetworkInfo, ResponseInfo],
]


def _supports_verify_flag(func: Callable[..., object]) -> bool:
    """Return True when callable defines a keyword argument named verify_ssl."""
    try:
        params = signature(func).parameters
    except (TypeError, ValueError):
        return False

    param = params.get("verify_ssl")
    if param is None:
        return False
    return param.kind in {Parameter.KEYWORD_ONLY, Parameter.POSITIONAL_OR_KEYWORD}


class CallableRequestExecutor:
    """Adapter that wraps legacy callables into the RequestExecutor protocol."""

    __slots__ = ("_func", "_supports_verify")

    def __init__(self, func: LegacyExecutorType) -> None:
        """Initialize adapter by storing callable and probing verify support."""
        self._func = func
        self._supports_verify = _supports_verify_flag(func)

    def execute(self, options: RequestOptions) -> RequestOutcome:
        """Execute wrapped callable using normalized request options."""
        kwargs: dict[str, object] = {
            "method": options.method,
            "content": options.content,
            "http2": options.http2,
            "dns_resolver": options.dns_resolver,
            "tls_inspector": options.tls_inspector,
            "timing_collector": options.timing_collector,
            "force_new_connection": options.force_new_connection,
            "headers": options.headers,
        }
        if self._supports_verify:
            kwargs["verify_ssl"] = options.verify_ssl
        if options.proxy is not None:
            kwargs["proxy"] = options.proxy

        try:
            timing, network, response = self._func(
                options.url,
                options.timeout,
                **kwargs,
            )
        except TypeError as exc:
            if self._supports_verify and "verify_ssl" in str(exc):
                self._supports_verify = False
                kwargs.pop("verify_ssl", None)
                warnings.warn(
                    "Request executor does not accept 'verify_ssl'; ignoring flag. "
                    "Support for callables without this keyword will be removed in a future release.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                timing, network, response = self._func(
                    options.url,
                    options.timeout,
                    **kwargs,
                )
            else:
                raise

        return RequestOutcome(timing=timing, network=network, response=response)
