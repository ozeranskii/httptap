"""HAR 1.2 export: structure, timings, failed steps, stdout mode, redaction and write failures."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from tests.e2e import servers as srv
from tests.e2e.harness import (
    EXIT_CANTCREAT,
    EXIT_NETWORK,
    EXIT_OK,
    EXIT_USAGE,
    PROXY_PASSWORD,
    PROXY_USER,
    RunCommand,
    Servers,
    assert_secret_absent,
    parse_metrics,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.e2e.certs import CertSet

URL_SECRET = "HarUserinfoS3cretPw"
BEARER_SECRET = "HarBearerS3cretToken"


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _check_entry_timings(entry: dict[str, Any]) -> None:
    timings = entry["timings"]
    for name in ("send", "wait", "receive"):
        assert timings[name] >= 0, timings
    for name in ("blocked", "dns", "connect", "ssl"):
        assert timings[name] == -1 or timings[name] >= 0, timings
    summed = sum(timings[n] for n in ("blocked", "dns", "connect", "send", "wait", "receive") if timings[n] != -1)
    assert abs(entry["time"] - summed) <= 0.002, f"time {entry['time']} != sum {summed}: {timings}"


def _check_document(data: dict[str, Any]) -> list[dict[str, Any]]:
    log = data["log"]
    assert log["version"] == "1.2"
    assert log["creator"]["name"] == "httptap"
    (page,) = log["pages"]
    entries: list[dict[str, Any]] = log["entries"]
    starts = [datetime.fromisoformat(e["startedDateTime"]) for e in entries]
    assert all(s.utcoffset() is not None for s in starts)
    assert starts == sorted(starts)
    for entry in entries:
        assert entry["pageref"] == page["id"]
        assert entry["cache"] == {}
        for key in ("method", "url", "httpVersion", "cookies", "headers", "queryString", "headersSize", "bodySize"):
            assert key in entry["request"], key
        for key in ("status", "statusText", "httpVersion", "cookies", "headers", "content", "redirectURL"):
            assert key in entry["response"], key
        assert "text" not in entry["response"]["content"]
        _check_entry_timings(entry)
    return entries


def test_har_file_for_redirect_chain(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "run.har"
    url = f"http://alice:{URL_SECRET}@{servers.host}:{servers.port(servers.origin)}/redirect/2?x=1"
    res = run(
        ["-L", "-H", f"Authorization: Bearer {BEARER_SECRET}", "--har", str(path), url],
    ).expect(EXIT_OK)
    assert "HTTP Tap Analysis" in res.stdout, "the Rich report is still printed with --har FILE"
    assert "Exported HAR to" in res.stderr

    data = _load(path)
    entries = _check_document(data)
    assert [e["response"]["status"] for e in entries] == [302, 302, 200]
    assert [e["response"]["redirectURL"] for e in entries] == ["/redirect/1", "/ok", ""]
    assert entries[0]["request"]["queryString"] == [{"name": "x", "value": "1"}]
    assert data["log"]["pages"][0]["title"].startswith("http://alice:****@")
    assert entries[-1]["response"]["content"] == {"size": 3, "mimeType": "text/plain; charset=utf-8"}
    for entry in entries:
        assert entry["request"]["method"] == "GET"
        assert entry["timings"]["ssl"] == -1, "plain HTTP has no TLS phase"
        if servers.config.target_host == servers.config.target_ip:
            assert entry["serverIPAddress"] == servers.config.target_ip
    assert_secret_absent(res, URL_SECRET, path)
    assert_secret_absent(res, BEARER_SECRET, path)


def test_har_https_connect_includes_ssl(run: RunCommand, servers: Servers, certs: CertSet, out_dir: Path) -> None:
    path = out_dir / "tls.har"
    port = servers.port(servers.tls_valid)
    res = run(
        [
            "--metrics-only",
            "-L",
            "--resolve",
            f"e2e.test:{port}:{servers.config.target_ip}",
            "--cacert",
            str(certs.ca),
            "--har",
            str(path),
            f"https://e2e.test:{port}/redirect/1",
        ]
    ).expect(EXIT_OK)
    metrics = parse_metrics(res.stdout)
    entries = _check_document(_load(path))
    assert [e["response"]["status"] for e in entries] == [302, 200]
    first = entries[0]
    assert first["timings"]["ssl"] > 0
    assert first["timings"]["connect"] >= first["timings"]["ssl"]
    assert abs(first["timings"]["ssl"] - float(metrics[0]["tls"].removesuffix("ms"))) <= 1.0
    assert first["_tls"]["version"].startswith("TLS")
    assert first["_tls"]["verified"] is True
    assert first["_tls"]["certCN"]


def test_har_location_credentials_redacted(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "loc.har"
    res = run(["--metrics-only", "--har", str(path), servers.url(servers.origin, "/location-cred")]).expect(EXIT_OK)
    (entry,) = _check_document(_load(path))
    assert entry["response"]["redirectURL"].startswith("http://alice:****@")
    assert_secret_absent(res, srv.LOCATION_CRED_PASSWORD, path)


def test_har_proxy_credentials_redacted(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "proxy.har"
    proxy = servers.proxy_url(servers.proxy_auth, userinfo=f"{PROXY_USER}:{PROXY_PASSWORD}@")
    res = run(["--metrics-only", "-x", proxy, "--har", str(path), servers.url(servers.origin)]).expect(EXIT_OK)
    (entry,) = _check_document(_load(path))
    assert entry["_proxy"]["url"] == f"http://{PROXY_USER}:****@{servers.host}:{servers.port(servers.proxy_auth)}"
    assert_secret_absent(res, PROXY_PASSWORD, path)


def test_har_stdout_only_har(run: RunCommand, servers: Servers) -> None:
    res = run(["--har", "-", servers.url(servers.origin)]).expect(EXIT_OK)
    (entry,) = _check_document(res.json())
    assert entry["response"]["status"] == 200
    assert "HTTP Tap Analysis" not in res.stdout
    assert "\x1b[" not in res.stdout


def test_har_stdout_with_json_file(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "report.json"
    res = run(["--metrics-only", "--har", "-", "--json", str(path), servers.url(servers.origin)]).expect(EXIT_OK)
    _check_document(res.json())
    assert _load(path)["schema_version"] == 1


def test_har_and_json_both_on_stdout_is_usage_error(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", "--har", "-", servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "cannot both write to stdout" in res.stderr
    assert res.stdout == ""


def test_har_empty_path_is_usage_error(run: RunCommand, servers: Servers) -> None:
    res = run(["--har", "", servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "HAR export path cannot be empty" in res.stderr


def test_har_failed_step(run: RunCommand, servers: Servers) -> None:
    res = run(["--har", "-", f"http://{servers.host}:{servers.dead.port}/"]).expect(EXIT_NETWORK)
    (entry,) = _check_document(res.json())
    assert entry["response"]["status"] == 0
    assert entry["response"]["_error"]
    assert entry["time"] == 0


def test_har_unwritable_path(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    blocker = out_dir / "file"
    blocker.write_text("x")
    res = run(["--metrics-only", "--har", str(blocker / "run.har"), servers.url(servers.origin)]).expect(EXIT_CANTCREAT)
    assert "Failed to export HAR" in res.stderr
    assert "status=200" in res.stdout, "results are still printed"


def test_har_unwritable_path_loses_to_network_error(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    blocker = out_dir / "file"
    blocker.write_text("x")
    run(["--metrics-only", "--har", str(blocker / "run.har"), f"http://{servers.host}:{servers.dead.port}/"]).expect(
        EXIT_NETWORK
    )
