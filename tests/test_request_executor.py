from __future__ import annotations

from typing import NoReturn

import pytest

from httptap.models import NetworkInfo, ResponseInfo, TimingMetrics
from httptap.request_executor import CallableRequestExecutor, RequestOptions


class SignatureFailsExecutor:
    """Callable whose signature introspection fails."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    @property
    def __signature__(self) -> None:  # type: ignore[override]
        msg = "signature unavailable"
        raise ValueError(msg)

    def __call__(self, *_: object, **kwargs: object) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        self.calls.append(kwargs)
        return TimingMetrics(), NetworkInfo(), ResponseInfo(status=200)


def _build_options(**overrides: object) -> RequestOptions:
    base = {
        "url": "https://example.test",
        "timeout": 1.0,
        "http2": True,
        "verify_ssl": False,
        "dns_resolver": None,
        "tls_inspector": None,
        "timing_collector": None,
        "force_new_connection": True,
        "headers": None,
    }
    base.update(overrides)
    return RequestOptions(**base)  # type: ignore[arg-type]


def test_callable_executor_handles_signature_failure() -> None:
    executor = SignatureFailsExecutor()
    adapter = CallableRequestExecutor(executor)

    outcome = adapter.execute(_build_options())

    assert outcome.response.status == 200
    assert executor.calls
    assert "verify_ssl" not in executor.calls[0]


def test_callable_executor_reraises_unrelated_typeerror() -> None:
    def legacy(url: str, timeout: float, **kwargs: object) -> NoReturn:
        msg = "unexpected failure"
        raise TypeError(msg)

    adapter = CallableRequestExecutor(legacy)

    with pytest.raises(TypeError, match="unexpected failure"):
        adapter.execute(_build_options())
