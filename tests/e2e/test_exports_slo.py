"""OTLP export, SLO evaluation, exit-code precedence and URL credential redaction across all sinks."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

import pytest

from tests.e2e.harness import (
    EXIT_CANTCREAT,
    EXIT_HTTP_FAIL,
    EXIT_NETWORK,
    EXIT_OK,
    EXIT_REDIRECTS,
    EXIT_SLO,
    RunCommand,
    Runner,
    Servers,
    assert_secret_absent,
    parse_metrics,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.e2e.servers import CollectorServer


def _token() -> str:
    return uuid.uuid4().hex


def _spans_after(collector: CollectorServer, before: int) -> list[dict[str, Any]]:
    return collector.spans[before:]


def test_otlp_export_structure(run: RunCommand, servers: Servers) -> None:
    token = _token()
    before = len(servers.collector.spans)
    otlp = servers.url(servers.collector, "/v1/traces")
    res = run(
        ["--metrics-only", "-L", "--otlp", otlp, servers.url(servers.origin, f"/redirect-to?url=%2Fok%3Fq%3D{token}")]
    ).expect(EXIT_OK)
    assert res.stderr.strip() == ""
    spans = _spans_after(servers.collector, before)
    names = [s["name"] for s in spans]
    assert names.count("httptap.analysis") == 1
    assert names.count("http.request") == 2
    for phase in ("dns", "connect", "tls", "wait", "xfer"):
        assert names.count(f"http.{phase}") == 2, phase
    assert len({s["trace_id"] for s in spans}) == 1
    root = next(s for s in spans if s["name"] == "httptap.analysis")
    requests = sorted(
        (s for s in spans if s["name"] == "http.request"), key=lambda s: s["attributes"]["httptap.step_number"]
    )
    assert all(r["parent_span_id"] == root["span_id"] for r in requests)
    assert requests[0]["end"] <= requests[1]["start"], "steps are laid out sequentially"
    assert requests[0]["attributes"]["http.response.status_code"] == 302
    assert requests[1]["attributes"]["http.response.status_code"] == 200
    assert requests[1]["attributes"]["http.request.method"] == "GET"
    assert requests[1]["attributes"]["server.address"] == servers.config.target_host
    for span in spans:
        assert token.encode() not in span["raw"], "query strings must not be exported"
    (rec,) = [r for r in servers.collector.records if r.method == "POST"][-1:]
    assert rec.path == "/v1/traces"


def test_otlp_error_step_status(run: RunCommand, servers: Servers) -> None:
    before = len(servers.collector.spans)
    otlp = servers.url(servers.collector, "/v1/traces")
    run(["--metrics-only", "--otlp", otlp, f"http://{servers.host}:{servers.dead.port}/"]).expect(EXIT_NETWORK)
    spans = _spans_after(servers.collector, before)
    root = next(s for s in spans if s["name"] == "httptap.analysis")
    assert root["status_code"] == 2  # STATUS_CODE_ERROR
    assert root["status_message"]


def test_otlp_collector_500_is_warning(run: RunCommand, servers: Servers) -> None:
    otlp = servers.url(servers.collector_fail, "/v1/traces")
    res = run(["--metrics-only", "--otlp", otlp, servers.url(servers.origin)]).expect(EXIT_OK)
    assert "Failed to export OTLP traces" in res.stderr
    assert "status=200" in res.stdout


def test_otlp_collector_500_does_not_mask_fail(run: RunCommand, servers: Servers) -> None:
    otlp = servers.url(servers.collector_fail, "/v1/traces")
    run(["--metrics-only", "-f", "--otlp", otlp, servers.url(servers.origin, "/status/503")]).expect(EXIT_HTTP_FAIL)


@pytest.mark.slow
def test_otlp_collector_down_is_warning_and_bounded(run: RunCommand, runner: Runner, servers: Servers) -> None:
    otlp = f"http://bob:OtlpEndpointPw@{servers.host}:{servers.dead.port}/v1/traces"
    res = run(["--metrics-only", "-m", "2", "--otlp", otlp, servers.url(servers.origin)]).expect(EXIT_OK)
    assert "Failed to export OTLP traces" in res.stderr
    assert_secret_absent(res, "OtlpEndpointPw")
    assert res.wall <= runner.deadline(2) + 2, "OTLP delivery is bounded by -m"


def test_otlp_endpoint_credentials_on_500(run: RunCommand, servers: Servers) -> None:
    port = servers.port(servers.collector_fail)
    otlp = f"http://bob:OtlpEndpointPw500@{servers.host}:{port}/v1/traces"
    res = run(["--metrics-only", "--otlp", otlp, servers.url(servers.origin)]).expect(EXIT_OK)
    assert "Failed to export OTLP traces" in res.stderr
    assert_secret_absent(res, "OtlpEndpointPw500")


URL_SECRET = "UrlUserinfoS3cretPw"


@pytest.mark.parametrize("mode", [[], ["--compact"], ["--metrics-only"], ["--json", "-"]])
def test_url_credentials_redacted_success(run: RunCommand, servers: Servers, mode: list[str]) -> None:
    token = _token()
    url = f"http://alice:{URL_SECRET}@{servers.host}:{servers.port(servers.origin)}/echo?id={token}"
    res = run([*mode, url]).expect(EXIT_OK)
    assert_secret_absent(res, URL_SECRET)
    (rec,) = servers.origin.find(token)
    assert (rec.header("Authorization") or "").startswith("Basic "), "URL credentials are still used"


def test_url_credentials_redacted_in_all_sinks(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    jpath, ppath = out_dir / "r.json", out_dir / "r.prom"
    before = len(servers.collector.spans)
    url = f"http://alice:{URL_SECRET}@{servers.host}:{servers.port(servers.origin)}/redirect/1"
    res = run(
        [
            "-L",
            "--json",
            str(jpath),
            "--prometheus",
            str(ppath),
            "--otlp",
            servers.url(servers.collector, "/v1/traces"),
            url,
        ]
    ).expect(EXIT_OK)
    spans = [s["raw"] for s in _spans_after(servers.collector, before)]
    assert spans
    assert_secret_absent(res, URL_SECRET, jpath, ppath, extra=spans)
    assert json.loads(jpath.read_text(encoding="utf-8"))["initial_url"].startswith("http://alice:****@")


@pytest.mark.parametrize("mode", [[], ["--metrics-only"], ["--json", "-"]])
def test_url_credentials_redacted_on_error(run: RunCommand, servers: Servers, mode: list[str]) -> None:
    url = f"http://alice:{URL_SECRET}@{servers.host}:{servers.dead.port}/"
    res = run([*mode, url]).expect(EXIT_NETWORK)
    assert_secret_absent(res, URL_SECRET)


def test_url_token_only_userinfo_redacted(run: RunCommand, servers: Servers) -> None:
    url = f"http://TokenOnlyUserinfo123@{servers.host}:{servers.port(servers.origin)}/ok"
    res = run(["--json", "-", url]).expect(EXIT_OK)
    assert_secret_absent(res, "TokenOnlyUserinfo123")


def test_slo_pass(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "--slo", "total=60000,ttfb=60000", servers.url(servers.origin)]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["slo"] == "pass"


def test_slo_fail(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "--slo", "total=0.0001", servers.url(servers.origin)]).expect(EXIT_SLO)
    step = parse_metrics(res.stdout)[0]
    assert step["slo"] == "fail"
    assert step["slo_violations"] == "total"


def test_slo_fail_rich_still_prints_report(run: RunCommand, servers: Servers) -> None:
    res = run(["--slo", "total=0.0001", servers.url(servers.origin)]).expect(EXIT_SLO)
    assert "Status: 200" in res.stdout
    assert "SLO" in res.stdout


def test_slo_json(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", "--slo", "TOTAL=0.0001, dns=60000", servers.url(servers.origin)]).expect(EXIT_SLO)
    slo = res.json()["summary"]["slo"]
    assert slo["pass"] is False
    assert slo["thresholds_ms"] == {"dns": 60000, "total": 0.0001}
    assert [v["key"] for v in slo["violations"]] == ["total"]


def test_slo_file_pass_and_fail(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    good, bad = out_dir / "good.slo", out_dir / "bad.slo"
    good.write_text("# budgets\n\ntotal=60000\nconnect = 60000\n")
    bad.write_text("total=0.0001\n")
    run(["--metrics-only", "--slo-file", str(good), servers.url(servers.origin)]).expect(EXIT_OK)
    run(["--metrics-only", "--slo-file", str(bad), servers.url(servers.origin)]).expect(EXIT_SLO)


def test_slo_inline_overrides_file(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    bad = out_dir / "bad.slo"
    bad.write_text("total=0.0001\n")
    run(["--metrics-only", "--slo-file", str(bad), "--slo", "total=60000", servers.url(servers.origin)]).expect(EXIT_OK)


def test_slo_evaluates_final_step_of_chain(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", "-L", "--slo", "total=60000", servers.url(servers.origin, "/redirect/2")])
    res.expect(EXIT_OK)
    assert res.json()["summary"]["slo"]["pass"] is True


def test_slo_on_network_error_is_75(run: RunCommand, servers: Servers) -> None:
    run(["--metrics-only", "--slo", "total=0.0001", f"http://{servers.host}:{servers.dead.port}/"]).expect(EXIT_NETWORK)


@pytest.mark.slow
def test_slo_real_violation(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "--slo", "ttfb=300", servers.url(servers.origin, "/slow-headers?s=0.6")])
    res.expect(EXIT_SLO)
    assert parse_metrics(res.stdout)[0]["slo_violations"] == "ttfb"


@pytest.mark.parametrize("flag", ["-f", "--fail"])
@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_fail_flag(run: RunCommand, servers: Servers, flag: str, status: int) -> None:
    res = run(["--metrics-only", flag, servers.url(servers.origin, f"/status/{status}")]).expect(EXIT_HTTP_FAIL)
    assert f"status={status}" in res.stdout, "results are printed before failing"


@pytest.mark.parametrize("status", [404, 500])
def test_http_error_without_fail_is_ok(run: RunCommand, servers: Servers, status: int) -> None:
    run(["--metrics-only", servers.url(servers.origin, f"/status/{status}")]).expect(EXIT_OK)


@pytest.mark.parametrize("status", [200, 204, 302, 399])
def test_fail_flag_ignores_non_errors(run: RunCommand, servers: Servers, status: int) -> None:
    run(["--metrics-only", "-f", servers.url(servers.origin, f"/status/{status}")]).expect(EXIT_OK)


def _blocked_json(out_dir: Path) -> str:
    blocker = out_dir / "blocker"
    blocker.write_text("x")
    return str(blocker / "r.json")


@pytest.mark.parametrize(
    ("args", "path", "expected"),
    [
        (["-f", "--slo", "total=0.0001"], "/status/404", EXIT_HTTP_FAIL),
        (["--slo", "total=0.0001"], "/status/404", EXIT_SLO),
        (["-f", "--slo", "total=0.0001", "--json", "BLOCKED"], "/status/404", EXIT_CANTCREAT),
        (["--slo", "total=0.0001", "--json", "BLOCKED"], "/ok", EXIT_CANTCREAT),
        (["-f", "--json", "BLOCKED"], "DEAD", EXIT_NETWORK),
        (["-L", "-f", "--json", "BLOCKED", "--slo", "total=0.0001"], "/loop", EXIT_REDIRECTS),
        (["-L", "-f"], "/redirect-to?url=DEADURL", EXIT_NETWORK),
        (["-f", "--prometheus", "BLOCKED", "--otlp", "COLLECTOR_FAIL"], "/status/500", EXIT_HTTP_FAIL),
    ],
    ids=["22>4", "4-on-404", "73>22>4", "73>4", "75>73>22", "47>73>22>4", "75>22-chain", "export-warnings<22"],
)
def test_exit_code_precedence(  # noqa: PLR0913, PLR0917
    run: RunCommand, servers: Servers, out_dir: Path, args: list[str], path: str, expected: int
) -> None:
    blocked = _blocked_json(out_dir)
    dead = f"http://{servers.host}:{servers.dead.port}/"
    mapped = []
    for a in args:
        if a == "BLOCKED":
            mapped.append(blocked)
        elif a == "COLLECTOR_FAIL":
            mapped.append(servers.url(servers.collector_fail, "/v1/traces"))
        else:
            mapped.append(a)
    if path == "DEAD":
        url = dead
    else:
        url = servers.url(servers.origin, path.replace("DEADURL", dead.replace(":", "%3A").replace("/", "%2F")))
    run(["--metrics-only", *mapped, url]).expect(expected)
