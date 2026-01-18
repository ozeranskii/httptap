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


def test_http_client_executor_with_socks5h_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that socks5h proxy (remote DNS) is properly passed to make_request."""
    captured: dict[str, object] = {}

    def fake_make_request(
        url: str, timeout: float, **kwargs: object
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        captured["url"] = url
        captured["timeout"] = timeout
        captured.update(kwargs)
        return TimingMetrics(total_ms=1.0), NetworkInfo(ip="203.0.113.1", ip_family="IPv4"), ResponseInfo(status=200)

    monkeypatch.setattr("httptap.request_executor.make_request", fake_make_request)

    options = RequestOptions(
        url="https://remote-dns.test",
        timeout=5.0,
        proxy="socks5h://gateway:1080",
    )

    executor = HTTPClientRequestExecutor()
    outcome = executor.execute(options)

    assert outcome.response.status == 200
    assert captured["url"] == "https://remote-dns.test"
    assert captured["proxy"] == "socks5h://gateway:1080"


def test_http_client_executor_with_http_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that HTTP proxy is properly passed to make_request."""
    captured: dict[str, object] = {}

    def fake_make_request(
        url: str, timeout: float, **kwargs: object
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        captured["url"] = url
        captured["timeout"] = timeout
        captured.update(kwargs)
        return TimingMetrics(total_ms=1.0), NetworkInfo(ip="203.0.113.2", ip_family="IPv4"), ResponseInfo(status=200)

    monkeypatch.setattr("httptap.request_executor.make_request", fake_make_request)

    options = RequestOptions(
        url="https://http-proxy.test",
        timeout=5.0,
        proxy="http://proxy.example.com:8080",
    )

    executor = HTTPClientRequestExecutor()
    outcome = executor.execute(options)

    assert outcome.response.status == 200
    assert captured["url"] == "https://http-proxy.test"
    assert captured["proxy"] == "http://proxy.example.com:8080"


def test_http_client_executor_with_https_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that HTTPS proxy is properly passed to make_request."""
    captured: dict[str, object] = {}

    def fake_make_request(
        url: str, timeout: float, **kwargs: object
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        captured["url"] = url
        captured["timeout"] = timeout
        captured.update(kwargs)
        return TimingMetrics(total_ms=1.0), NetworkInfo(ip="203.0.113.3", ip_family="IPv4"), ResponseInfo(status=200)

    monkeypatch.setattr("httptap.request_executor.make_request", fake_make_request)

    options = RequestOptions(
        url="https://https-proxy.test",
        timeout=5.0,
        proxy="https://secure-proxy.example.com:8443",
    )

    executor = HTTPClientRequestExecutor()
    outcome = executor.execute(options)

    assert outcome.response.status == 200
    assert captured["url"] == "https://https-proxy.test"
    assert captured["proxy"] == "https://secure-proxy.example.com:8443"


def test_http_client_executor_with_socks5_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that socks5 proxy (local DNS) is properly passed to make_request."""
    captured: dict[str, object] = {}

    def fake_make_request(
        url: str, timeout: float, **kwargs: object
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        captured["url"] = url
        captured["timeout"] = timeout
        captured.update(kwargs)
        return TimingMetrics(total_ms=1.0), NetworkInfo(ip="203.0.113.4", ip_family="IPv4"), ResponseInfo(status=200)

    monkeypatch.setattr("httptap.request_executor.make_request", fake_make_request)

    options = RequestOptions(
        url="https://local-dns.test",
        timeout=5.0,
        proxy="socks5://gateway:1080",
    )

    executor = HTTPClientRequestExecutor()
    outcome = executor.execute(options)

    assert outcome.response.status == 200
    assert captured["url"] == "https://local-dns.test"
    assert captured["proxy"] == "socks5://gateway:1080"


def test_http_client_executor_with_authenticated_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that proxy with authentication credentials is properly passed."""
    captured: dict[str, object] = {}

    def fake_make_request(
        url: str, timeout: float, **kwargs: object
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        captured["url"] = url
        captured["timeout"] = timeout
        captured.update(kwargs)
        return TimingMetrics(total_ms=1.0), NetworkInfo(ip="203.0.113.5", ip_family="IPv4"), ResponseInfo(status=200)

    monkeypatch.setattr("httptap.request_executor.make_request", fake_make_request)

    options = RequestOptions(
        url="https://auth-proxy.test",
        timeout=5.0,
        proxy="socks5h://user:password@gateway:1080",
    )

    executor = HTTPClientRequestExecutor()
    outcome = executor.execute(options)

    assert outcome.response.status == 200
    assert captured["url"] == "https://auth-proxy.test"
    assert captured["proxy"] == "socks5h://user:password@gateway:1080"


def test_http_client_executor_without_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that requests work correctly without a proxy."""
    captured: dict[str, object] = {}

    def fake_make_request(
        url: str, timeout: float, **kwargs: object
    ) -> tuple[TimingMetrics, NetworkInfo, ResponseInfo]:
        captured["url"] = url
        captured["timeout"] = timeout
        captured.update(kwargs)
        return TimingMetrics(total_ms=1.0), NetworkInfo(ip="203.0.113.6", ip_family="IPv4"), ResponseInfo(status=200)

    monkeypatch.setattr("httptap.request_executor.make_request", fake_make_request)

    options = RequestOptions(
        url="https://no-proxy.test",
        timeout=5.0,
        proxy=None,
    )

    executor = HTTPClientRequestExecutor()
    outcome = executor.execute(options)

    assert outcome.response.status == 200
    assert captured["url"] == "https://no-proxy.test"
    assert captured["proxy"] is None
