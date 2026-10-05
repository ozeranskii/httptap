"""Redirect following, method rewriting, credential handling and redirect failures."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest

from tests.e2e import servers as srv
from tests.e2e.harness import (
    EXIT_HTTP_FAIL,
    EXIT_NETWORK,
    EXIT_OK,
    EXIT_REDIRECTS,
    RunCommand,
    Runner,
    Servers,
    assert_secret_absent,
    parse_metrics,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.e2e.servers import HTTPServerV4


def _token() -> str:
    return uuid.uuid4().hex


def _redirect_to(servers: Servers, target: str, code: int = 302, server: HTTPServerV4 | None = None) -> str:
    return servers.url(server or servers.origin, f"/redirect-to?code={code}&url={quote(target, safe='')}")


def test_no_follow_reports_redirect(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", servers.url(servers.origin, "/redirect/1")]).expect(EXIT_OK)
    data = res.json()
    assert data["total_steps"] == 1
    assert data["steps"][0]["response"]["status"] == 302
    assert data["steps"][0]["response"]["location"] == "/ok"


@pytest.mark.parametrize("flag", ["-L", "--location", "--follow"])
def test_follow_chain(run: RunCommand, servers: Servers, flag: str) -> None:
    res = run(["--json", "-", flag, servers.url(servers.origin, "/redirect/3")]).expect(EXIT_OK)
    data = res.json()
    assert [s["response"]["status"] for s in data["steps"]] == [302, 302, 302, 200]
    assert [s["step_number"] for s in data["steps"]] == [1, 2, 3, 4]
    assert data["summary"]["final_url"].endswith("/ok")
    assert data["summary"]["final_status"] == 200


def test_relative_location(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-L", servers.url(servers.origin, "/relative-redirect")]).expect(EXIT_OK)
    assert [s["status"] for s in parse_metrics(res.stdout)] == ["302", "200"]


def test_redirect_loop_hits_limit(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", "-L", servers.url(servers.origin, "/loop")]).expect(EXIT_REDIRECTS)
    data = res.json()
    assert data["steps"][-1]["redirect_limit_reached"] is True
    assert 10 <= len(data["steps"]) <= 11
    assert data["summary"]["errors"] >= 1
    assert "Maximum redirects" in res.stderr


def test_redirect_limit_with_fail_and_slo_is_still_47(run: RunCommand, servers: Servers) -> None:
    run(["--metrics-only", "-L", "-f", "--slo", "total=0.0001", servers.url(servers.origin, "/loop")]).expect(
        EXIT_REDIRECTS
    )


def test_ten_redirects_is_allowed(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-L", servers.url(servers.origin, "/redirect/10")]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[-1]["status"] == "200"


def test_cross_origin_drops_authorization(run: RunCommand, servers: Servers) -> None:
    token = _token()
    res = run(
        [
            "--json",
            "-",
            "-L",
            "-H",
            "Authorization: Bearer cross-origin-secret-value",
            servers.url(servers.origin, f"/cross-origin?id={token}"),
        ]
    ).expect(EXIT_OK)
    found = servers.origin2.find(token)
    assert len(found) == 1, res.describe()
    rec = found[0]
    assert rec.header("Authorization") is None, rec.headers


def test_same_origin_keeps_authorization(run: RunCommand, servers: Servers) -> None:
    token = _token()
    run(
        [
            "--metrics-only",
            "-L",
            "-H",
            "Authorization: Bearer same-origin-value",
            _redirect_to(servers, f"/echo?id={token}"),
        ]
    ).expect(EXIT_OK)
    recs = [r for r in servers.origin.find(token) if r.path.startswith("/echo")]
    assert len(recs) == 1
    assert recs[0].header("Authorization") == "Bearer same-origin-value"


@pytest.mark.parametrize(
    ("code", "method", "expected_method", "body_kept"),
    [
        (301, "POST", "GET", False),
        (302, "POST", "GET", False),
        (303, "POST", "GET", False),
        (303, "PUT", "GET", False),
        (307, "POST", "POST", True),
        (308, "PUT", "PUT", True),
        (307, "DELETE", "DELETE", True),
    ],
)
def test_redirect_method_semantics(  # noqa: PLR0913, PLR0917
    run: RunCommand,
    servers: Servers,
    code: int,
    method: str,
    expected_method: str,
    body_kept: bool,  # noqa: FBT001
) -> None:
    token = _token()
    res = run(
        ["--json", "-", "-L", "-X", method, "-d", "payload=1", _redirect_to(servers, f"/echo?id={token}", code)]
    ).expect(EXIT_OK)
    recs = [r for r in servers.origin.find(token) if r.path.startswith("/echo")]
    assert len(recs) == 1
    assert recs[0].method == expected_method
    assert recs[0].body == (b"payload=1" if body_kept else b"")
    assert res.json()["steps"][1]["request"]["method"] == expected_method


def test_location_credentials_redacted_everywhere(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    token = _token()
    jpath, ppath = out_dir / "r.json", out_dir / "r.prom"
    before = len(servers.collector.spans)
    url = servers.url(servers.origin, f"/location-cred?id={token}")
    otlp = servers.url(servers.collector, "/v1/traces")
    res = run(["-L", "--json", str(jpath), "--prometheus", str(ppath), "--otlp", otlp, url]).expect(EXIT_OK)
    data = json.loads(jpath.read_text(encoding="utf-8"))
    assert [s["response"]["status"] for s in data["steps"]] == [302, 200]
    loc = data["steps"][0]["response"]["location"]
    assert "alice:****@" in loc, loc
    spans = [s["raw"] for s in servers.collector.spans[before:]]
    assert_secret_absent(res, srv.LOCATION_CRED_PASSWORD, jpath, ppath, extra=spans)


@pytest.mark.parametrize("mode", [[], ["--compact"], ["--metrics-only"], ["--json", "-"]])
def test_location_credentials_redacted_without_follow(run: RunCommand, servers: Servers, mode: list[str]) -> None:
    res = run([*mode, servers.url(servers.origin, "/location-cred")]).expect(EXIT_OK)
    assert_secret_absent(res, srv.LOCATION_CRED_PASSWORD)


def test_invalid_redirect_port_range(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", "-L", servers.url(servers.origin, "/bad-location?kind=bigport")])
    res.expect(EXIT_NETWORK)
    steps = res.json()["steps"]
    assert steps[0]["response"]["status"] == 302
    assert steps[0]["error"] is None
    assert len(steps) == 2
    assert steps[1]["error"]


@pytest.mark.parametrize("kind", ["port", "ipv6"])
def test_invalid_redirect_target_unparsable(run: RunCommand, servers: Servers, kind: str) -> None:
    """A Location httpx cannot parse (non-numeric port, open IPv6 bracket) adds an error step after the 302."""
    res = run(["--json", "-", "-L", servers.url(servers.origin, f"/bad-location?kind={kind}")])
    res.expect(EXIT_NETWORK)
    steps = res.json()["steps"]
    assert steps[0]["response"]["status"] == 302, "the completed 302 step must be reported"
    assert len(steps) == 2
    assert steps[1]["error"]


@pytest.mark.parametrize("kind", ["port", "ipv6", "bigport"])
def test_invalid_location_without_follow_is_not_an_error(run: RunCommand, servers: Servers, kind: str) -> None:
    """Without -L the Location value is only displayed; it must not turn a 302 into a failed step."""
    res = run(["--json", "-", servers.url(servers.origin, f"/bad-location?kind={kind}")]).expect(EXIT_OK)
    step = res.json()["steps"][0]
    assert step["response"]["status"] == 302
    assert step["error"] is None


def test_redirect_to_refused_port(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", "-L", _redirect_to(servers, f"http://{servers.host}:{servers.dead.port}/")])
    res.expect(EXIT_NETWORK)
    steps = res.json()["steps"]
    assert steps[0]["response"]["status"] == 302
    assert steps[1]["error"]


def test_fail_on_final_404_after_redirect(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-L", "-f", _redirect_to(servers, "/status/404")]).expect(EXIT_HTTP_FAIL)
    assert [s["status"] for s in parse_metrics(res.stdout)] == ["302", "404"]


@pytest.mark.slow
def test_deadline_spans_redirect_chain(run: RunCommand, runner: Runner, servers: Servers) -> None:
    """-m bounds the whole chain: the redirect hop consumes budget and the next hop times out."""
    res = run(["--json", "-", "-L", "-m", "1.5", _redirect_to(servers, "/slow-headers?s=6")])
    res.expect(EXIT_NETWORK)
    steps = res.json()["steps"]
    assert steps[0]["response"]["status"] == 302
    assert steps[-1]["error"]
    assert res.wall <= runner.deadline(1.5), res.describe()
