from __future__ import annotations

from typing import TYPE_CHECKING

from httptap.constants import HTTPMethod
from httptap.models import NetworkInfo, ResponseInfo, TimingMetrics
from httptap.request_executor import HTTPClientRequestExecutor, RequestOptions

if TYPE_CHECKING:
    import pytest


def test_http_client_executor_delegates_to_make_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_make_request(
        url: str, timeout: float, **kwargs: object
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        captured["url"] = url
        captured["timeout"] = timeout
        captured.update(kwargs)
        return TimingMetrics(total_ms=1.0), NetworkInfo(ip="127.0.0.1", ip_family="IPv4"), ResponseInfo(status=204)

    # Patch make_request inside the executor module
    monkeypatch.setattr("httptap.request_executor.make_request", fake_make_request)

    options = RequestOptions(
        url="https://example.test",
        timeout=2.5,
        method=HTTPMethod.POST,
        content=b"data",
        http2=False,
        verify_ssl=False,
        ca_bundle_path="/dev/null",
        proxy="http://proxy",
        dns_resolver=None,
        tls_inspector=None,
        timing_collector=None,
        force_new_connection=False,
        headers={"X-Test": "1"},
    )

    executor = HTTPClientRequestExecutor()
    outcome = executor.execute(options)

    assert outcome.response.status == 204
    assert captured["url"] == "https://example.test"
    assert captured["timeout"] == 2.5
    assert captured["method"] == "POST"
    assert captured["content"] == b"data"
    assert captured["http2"] is False
    assert captured["verify_ssl"] is False
    assert captured["ca_bundle_path"] == "/dev/null"
    assert captured["proxy"] == "http://proxy"
    assert captured["force_new_connection"] is False
    assert captured["headers"] == {"X-Test": "1"}
