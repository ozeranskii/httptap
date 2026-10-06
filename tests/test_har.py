from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from rich.console import Console

from httptap._pkgmeta import get_package_info
from httptap.har import HARExporter, build_har
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.utils import sanitize_headers

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Mapping, Sequence

NOW_NS = 1_760_000_000_123_456_789
OPTIONAL_TIMINGS = ("blocked", "dns", "connect", "ssl")
REQUIRED_TIMINGS = ("send", "wait", "receive")


def _require(obj: Mapping[str, Any], fields: Mapping[str, type | tuple[type, ...]], where: str) -> None:
    for name, expected in fields.items():
        assert name in obj, f"{where}.{name} is missing"
        value = obj[name]
        assert isinstance(value, expected), f"{where}.{name} has type {type(value).__name__}"
        if expected in (int, float, (int, float)):
            assert not isinstance(value, bool), f"{where}.{name} must be a number, not a bool"


def _require_name_values(items: Sequence[Mapping[str, Any]], where: str) -> None:
    for index, item in enumerate(items):
        _require(item, {"name": str, "value": str}, f"{where}[{index}]")


def _parse_timestamp(value: str, where: str) -> datetime:
    moment = datetime.fromisoformat(value)
    assert moment.utcoffset() is not None, f"{where} has no timezone: {value}"
    return moment


def assert_valid_har(document: Mapping[str, Any]) -> None:
    """Check a document against the HAR 1.2 required fields, types and timing rules."""
    number = (int, float)
    _require(document, {"log": dict}, "")
    log = document["log"]
    _require(log, {"version": str, "creator": dict, "entries": list}, "log")
    assert log["version"] == "1.2"
    _require(log["creator"], {"name": str, "version": str}, "log.creator")

    page_ids = set()
    for index, page in enumerate(log.get("pages", [])):
        where = f"log.pages[{index}]"
        _require(page, {"startedDateTime": str, "id": str, "title": str, "pageTimings": dict}, where)
        _parse_timestamp(page["startedDateTime"], where)
        for name in ("onContentLoad", "onLoad"):
            value = page["pageTimings"].get(name, -1)
            assert isinstance(value, number), f"{where}.pageTimings.{name}"
            assert value == -1 or value >= 0
        page_ids.add(page["id"])

    starts = [
        _parse_timestamp(entry["startedDateTime"], f"log.entries[{index}]")
        for index, entry in enumerate(log["entries"])
    ]
    for index, entry in enumerate(log["entries"]):
        _check_entry(entry, f"log.entries[{index}]", page_ids)
    assert starts == sorted(starts), "entries must be ordered by startedDateTime"


def _check_entry(entry: Mapping[str, Any], where: str, page_ids: set[str]) -> None:
    number = (int, float)
    _require(
        entry,
        {
            "startedDateTime": str,
            "time": number,
            "request": dict,
            "response": dict,
            "cache": dict,
            "timings": dict,
        },
        where,
    )

    if "pageref" in entry:
        assert entry["pageref"] in page_ids, f"{where}.pageref points to no page"
    if "serverIPAddress" in entry:
        assert isinstance(entry["serverIPAddress"], str)
        assert not entry["serverIPAddress"].startswith("[")

    request = entry["request"]
    _require(
        request,
        {
            "method": str,
            "url": str,
            "httpVersion": str,
            "cookies": list,
            "headers": list,
            "queryString": list,
            "headersSize": int,
            "bodySize": int,
        },
        f"{where}.request",
    )
    _require_name_values(request["headers"], f"{where}.request.headers")
    _require_name_values(request["queryString"], f"{where}.request.queryString")
    if "postData" in request:
        _require(request["postData"], {"mimeType": str}, f"{where}.request.postData")
        assert not ("text" in request["postData"] and "params" in request["postData"])

    response = entry["response"]
    _require(
        response,
        {
            "status": int,
            "statusText": str,
            "httpVersion": str,
            "cookies": list,
            "headers": list,
            "content": dict,
            "redirectURL": str,
            "headersSize": int,
            "bodySize": int,
        },
        f"{where}.response",
    )
    _require_name_values(response["headers"], f"{where}.response.headers")
    _require(response["content"], {"size": int, "mimeType": str}, f"{where}.response.content")
    assert "text" not in response["content"], "response bodies are never exported"

    timings = entry["timings"]
    _require(timings, dict.fromkeys(REQUIRED_TIMINGS, number), f"{where}.timings")
    for name in REQUIRED_TIMINGS:
        assert timings[name] >= 0, f"{where}.timings.{name} is negative"
    for name in OPTIONAL_TIMINGS:
        value = timings.get(name, -1)
        assert isinstance(value, number), f"{where}.timings.{name}"
        assert value == -1 or value >= 0, f"{where}.timings.{name} = {value}"
    if timings.get("ssl", -1) != -1:
        assert timings["connect"] >= timings["ssl"], "connect must include ssl"
    summed = sum(
        timings.get(name, -1)
        for name in ("blocked", "dns", "connect", "send", "wait", "receive")
        if timings.get(name, -1) != -1
    )
    assert entry["time"] == pytest.approx(summed, abs=0.002), f"{where}.time != sum of timings"
    for name in entry:
        assert name in {
            "pageref",
            "startedDateTime",
            "time",
            "request",
            "response",
            "cache",
            "timings",
            "serverIPAddress",
            "connection",
            "comment",
        } or name.startswith("_"), f"{where}.{name} is not a HAR field and lacks the _ prefix"


def _success_step(url: str = "https://example.test/", *, step_number: int = 1, **timing: float) -> StepMetrics:
    timing_metrics = TimingMetrics(
        dns_ms=timing.get("dns_ms", 10.0),
        connect_ms=timing.get("connect_ms", 20.0),
        tls_ms=timing.get("tls_ms", 30.0),
        ttfb_ms=timing.get("ttfb_ms", 100.0),
        total_ms=timing.get("total_ms", 150.0),
    )
    timing_metrics.calculate_derived()
    return StepMetrics(
        url=url,
        step_number=step_number,
        timing=timing_metrics,
        network=NetworkInfo(ip="192.0.2.1", http_version="HTTP/2.0"),
        response=ResponseInfo(
            status=200,
            bytes=512,
            content_type="application/json",
            headers={"content-type": "application/json"},
        ),
        request_method="GET",
    )


def _entries(steps: Sequence[StepMetrics], initial_url: str = "https://example.test/") -> list[dict[str, Any]]:
    document = build_har(steps, initial_url, now_ns=NOW_NS)
    assert_valid_har(document)
    entries: list[dict[str, Any]] = document["log"]["entries"]
    return entries


def test_document_has_log_creator_and_one_page() -> None:
    document = build_har([_success_step()], "https://user:****@example.test/", now_ns=NOW_NS)

    assert_valid_har(document)
    log = document["log"]
    assert log["creator"] == {"name": "httptap", "version": get_package_info().version}
    assert "browser" not in log
    (page,) = log["pages"]
    assert page["id"] == "page_1"
    assert page["title"] == "https://user:****@example.test/"
    assert page["pageTimings"] == {"onContentLoad": -1, "onLoad": -1}
    assert page["startedDateTime"] == log["entries"][0]["startedDateTime"]
    assert log["entries"][0]["pageref"] == "page_1"


def test_https_timings_put_tls_inside_connect_and_ssl() -> None:
    (entry,) = _entries([_success_step()])

    assert entry["timings"] == {
        "blocked": -1,
        "dns": 10.0,
        "connect": 50.0,
        "send": 0,
        "wait": 40.0,
        "receive": 50.0,
        "ssl": 30.0,
    }
    assert entry["time"] == 150.0


def test_http_timings_mark_ssl_not_applicable() -> None:
    step = _success_step("http://example.test/", tls_ms=0.0)

    (entry,) = _entries([step])

    assert entry["timings"]["ssl"] == -1
    assert entry["timings"]["connect"] == 20.0
    assert entry["time"] == 150.0


def test_timings_are_rounded_to_microseconds() -> None:
    step = _success_step(dns_ms=1.23456789, connect_ms=2.0004, tls_ms=0.0001, ttfb_ms=10.0, total_ms=12.0)

    (entry,) = _entries([step])

    assert entry["timings"]["dns"] == 1.235
    assert entry["timings"]["connect"] == 2.001
    assert entry["timings"]["ssl"] == 0.0


def test_estimated_timing_is_flagged_inside_timings() -> None:
    step = _success_step()
    step.timing.is_estimated = True

    (entry,) = _entries([step])

    assert entry["timings"]["_estimated"] is True
    assert "_estimated" not in _entries([_success_step()])[0]["timings"]


def test_entries_are_laid_out_back_to_back_ending_at_export_time() -> None:
    steps = [
        _success_step("https://example.test/a", step_number=1),
        _success_step("https://example.test/b", step_number=2, total_ms=250.0),
    ]

    first, second = _entries(steps)

    first_start = datetime.fromisoformat(first["startedDateTime"])
    second_start = datetime.fromisoformat(second["startedDateTime"])
    assert second_start - first_start == timedelta(milliseconds=150)
    chain_end = datetime.fromisoformat("2025-10-09T08:53:20.123+00:00")
    assert chain_end - second_start == timedelta(milliseconds=250)
    assert first["startedDateTime"] == "2025-10-09T08:53:19.723+00:00"


def test_redirect_chain_keeps_order_status_and_redirect_url() -> None:
    redirect = _success_step("http://example.test/old", step_number=1, tls_ms=0.0)
    redirect.response = ResponseInfo(status=301, location="https://example.test/new", headers={"location": "x"})
    final = _success_step("https://example.test/new", step_number=2)

    first, second = _entries([redirect, final])

    assert [first["response"]["status"], second["response"]["status"]] == [301, 200]
    assert first["response"]["redirectURL"] == "https://example.test/new"
    assert second["response"]["redirectURL"] == ""
    assert first["request"]["url"] == "http://example.test/old"
    assert {first["pageref"], second["pageref"]} == {"page_1"}


def test_request_fields_and_query_string() -> None:
    step = _success_step("https://example.test/search?q=a%20b&empty=&flag&q=2#frag")
    step.request_method = "POST"
    step.request_headers = {"Content-Type": "application/json", "X-Trace": "1"}
    step.request_body_bytes = 17

    (entry,) = _entries([step])

    request = entry["request"]
    assert request["method"] == "POST"
    assert request["httpVersion"] == "HTTP/2.0"
    assert request["headers"] == [
        {"name": "Content-Type", "value": "application/json"},
        {"name": "X-Trace", "value": "1"},
    ]
    assert request["queryString"] == [
        {"name": "q", "value": "a b"},
        {"name": "empty", "value": ""},
        {"name": "flag", "value": ""},
        {"name": "q", "value": "2"},
    ]
    assert request["bodySize"] == 17
    assert request["headersSize"] == -1
    assert request["cookies"] == []
    assert "postData" not in request, "request bodies are never exported"


def test_response_fields() -> None:
    (entry,) = _entries([_success_step()])

    response = entry["response"]
    assert response["status"] == 200
    assert response["statusText"] == ""
    assert response["httpVersion"] == "HTTP/2.0"
    assert response["content"] == {"size": 512, "mimeType": "application/json"}
    assert response["bodySize"] == 512
    assert response["_transferSize"] == 512
    assert response["headers"] == [{"name": "content-type", "value": "application/json"}]
    assert entry["serverIPAddress"] == "192.0.2.1"
    assert entry["cache"] == {}
    assert "_error" not in response
    assert "connection" not in entry


def test_unknown_content_type_and_ip_are_handled() -> None:
    step = _success_step()
    step.response.content_type = None
    step.network.ip = None

    (entry,) = _entries([step])

    assert entry["response"]["content"]["mimeType"] == "x-unknown"
    assert "serverIPAddress" not in entry


def test_failed_step_without_response() -> None:
    step = StepMetrics(
        url="https://down.example.test/",
        error="Connection refused",
        error_kind="network",
        request_method="GET",
    )

    (entry,) = _entries([step])

    response = entry["response"]
    assert response["status"] == 0
    assert response["httpVersion"] == ""
    assert response["bodySize"] == -1
    assert response["_transferSize"] == -1
    assert response["content"] == {"size": 0, "mimeType": "x-unknown"}
    assert response["_error"] == "Connection refused"
    assert response["_errorKind"] == "network"
    assert "_error" not in entry
    assert entry["timings"] == {
        "blocked": -1,
        "dns": -1,
        "connect": -1,
        "send": 0,
        "wait": 0,
        "receive": 0,
        "ssl": -1,
    }
    assert entry["time"] == 0


def test_failed_step_with_partial_response_keeps_status_and_bytes() -> None:
    step = StepMetrics(
        url="https://example.test/slow-body",
        error="Total deadline exceeded",
        error_kind="network",
        request_method="GET",
        network=NetworkInfo(ip="192.0.2.1", http_version="HTTP/1.1"),
        response=ResponseInfo(status=200, bytes=100, content_type="text/plain"),
    )

    (entry,) = _entries([step])

    assert entry["response"]["status"] == 200
    assert entry["response"]["bodySize"] == 100
    assert entry["response"]["_error"] == "Total deadline exceeded"
    assert entry["request"]["httpVersion"] == "HTTP/1.1"


def test_invalid_redirect_target_step_with_malformed_url() -> None:
    step = StepMetrics(url="http://[::1/next?x=1", error="Invalid redirect target", error_kind="network")

    (entry,) = _entries([step])

    assert entry["request"]["method"] == ""
    assert entry["request"]["queryString"] == [{"name": "x", "value": "1"}]


def test_tls_proxy_and_redirect_limit_custom_fields() -> None:
    step = _success_step()
    step.network.tls_version = "TLSv1.3"
    step.network.tls_cipher = "TLS_AES_128_GCM_SHA256"
    step.network.cert_cn = "example.test"
    step.network.cert_issuer = "Test CA"
    step.network.cert_days_left = 42
    step.network.tls_verified = True
    step.network.proxy_source = "cli"
    step.proxied_via = "http://puser:****@proxy.test:3128"
    step.redirect_limit_reached = True

    (entry,) = _entries([step])

    assert entry["_tls"] == {
        "version": "TLSv1.3",
        "cipher": "TLS_AES_128_GCM_SHA256",
        "certCN": "example.test",
        "certIssuer": "Test CA",
        "certDaysLeft": 42,
        "verified": True,
    }
    assert entry["_proxy"] == {"url": "http://puser:****@proxy.test:3128", "source": "cli"}
    assert entry["_redirectLimitReached"] is True


def test_optional_custom_fields_are_omitted_by_default() -> None:
    (entry,) = _entries([_success_step()])

    assert not [name for name in entry if name.startswith("_")]


def test_redacted_step_data_carries_no_secrets() -> None:
    step = _success_step("https://alice:****@example.test/")
    step.request_headers = sanitize_headers({"Authorization": "Bearer topsecrettoken", "Cookie": "sid=cookiesecret"})
    step.response.headers = sanitize_headers(
        {"Set-Cookie": "sid=setcookiesecret; HttpOnly", "Location": "https://bob:locsecret@example.test/"}
    )
    step.response.location = "https://bob:****@example.test/"

    document = build_har([step], "https://alice:****@example.test/", now_ns=NOW_NS)

    text = json.dumps(document)
    for secret in ("topsecrettoken", "cookiesecret", "setcookiesecret", "locsecret"):
        assert secret not in text
    assert "https://bob:****@example.test/" in text


def test_build_without_steps_has_page_and_no_entries() -> None:
    document = build_har([], "https://example.test/", now_ns=NOW_NS)

    assert_valid_har(document)
    assert document["log"]["entries"] == []
    assert document["log"]["pages"][0]["startedDateTime"] == "2025-10-09T08:53:20.123+00:00"


def test_build_uses_current_time_by_default() -> None:
    before = datetime.now().astimezone()

    document = build_har([_success_step()], "https://example.test/")

    started = datetime.fromisoformat(document["log"]["entries"][0]["startedDateTime"])
    assert started <= datetime.now().astimezone()
    assert started >= before - timedelta(milliseconds=151)


def test_exporter_writes_file_atomically(tmp_path: pathlib.Path) -> None:
    console = Console(record=True)
    output_path = tmp_path / "nested" / "run.har"

    HARExporter(console).export([_success_step()], "https://example.test/", str(output_path))

    document = json.loads(output_path.read_text(encoding="utf-8"))
    assert_valid_har(document)
    assert [path.name for path in output_path.parent.iterdir()] == ["run.har"]
    assert "Exported HAR to" in console.export_text()


def test_exporter_writes_utf8_without_escaping(tmp_path: pathlib.Path) -> None:
    output_path = tmp_path / "run.har"
    step = _success_step("https://example.test/café")

    HARExporter(Console(record=True)).export([step], "https://example.test/café", str(output_path))

    assert "café" in output_path.read_text(encoding="utf-8")


def test_exporter_writes_stdout_for_dash(capsys: pytest.CaptureFixture[str]) -> None:
    console = Console(record=True)

    HARExporter(console).export([_success_step()], "https://example.test/", "-")

    out = capsys.readouterr().out
    assert_valid_har(json.loads(out))
    assert out.endswith("}\n")
    assert console.export_text() == ""


def test_exporter_propagates_write_errors(tmp_path: pathlib.Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")

    with pytest.raises(OSError, match=r".+"):
        HARExporter(Console(record=True)).export([_success_step()], "https://example.test/", str(blocker / "run.har"))
