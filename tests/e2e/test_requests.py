"""Request construction: methods, bodies, headers, and what reaches the origin."""

from __future__ import annotations

import json
import sys
import uuid
from typing import TYPE_CHECKING

import pytest

from tests.e2e.harness import EXIT_OK, RunCommand, Servers, assert_secret_absent

if TYPE_CHECKING:
    from pathlib import Path

    from tests.e2e.servers import HTTPServerV4, Recorded


def _token() -> str:
    return uuid.uuid4().hex


def _one(server: HTTPServerV4, token: str) -> Recorded:
    found = server.find(token)
    assert len(found) == 1, f"expected exactly one request with {token}, got {len(found)}"
    return found[0]


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
def test_methods(run: RunCommand, servers: Servers, method: str) -> None:
    token = _token()
    res = run(["--metrics-only", "-X", method, servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_OK)
    assert "status=200" in res.stdout
    assert _one(servers.origin, token).method == method


def test_data_inline_defaults_to_post(run: RunCommand, servers: Servers) -> None:
    token = _token()
    run(["--metrics-only", "-d", '{"k": "v"}', servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_OK)
    rec = _one(servers.origin, token)
    assert rec.method == "POST"
    assert rec.body == b'{"k": "v"}'
    assert rec.header("Content-Length") == str(len(rec.body))


def test_data_put(run: RunCommand, servers: Servers) -> None:
    token = _token()
    run(["--metrics-only", "-X", "PUT", "-d", "x=1", servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_OK)
    rec = _one(servers.origin, token)
    assert (rec.method, rec.body) == ("PUT", b"x=1")


def test_data_from_file(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    token = _token()
    payload = out_dir / "payload.json"
    payload.write_bytes(b'{"from": "file", "bin": "\\u00ff"}\n')
    run(["--metrics-only", "-d", f"@{payload}", servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_OK)
    rec = _one(servers.origin, token)
    assert rec.method == "POST"
    assert rec.body == payload.read_bytes()
    assert (rec.header("Content-Type") or "").startswith("application/json")


def test_data_from_binary_file_exact(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    token = _token()
    payload = out_dir / "blob.bin"
    blob = bytes(range(256)) * 4
    payload.write_bytes(blob)
    run(["--metrics-only", "-d", f"@{payload}", servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_OK)
    assert _one(servers.origin, token).body == blob


def test_explicit_content_type_overrides_detected(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    token = _token()
    payload = out_dir / "p.json"
    payload.write_text("{}")
    run(
        [
            "--metrics-only",
            "-d",
            f"@{payload}",
            "-H",
            "content-type: text/x-custom",
            servers.url(servers.origin, f"/echo?id={token}"),
        ]
    ).expect(EXIT_OK)
    rec = _one(servers.origin, token)
    values = [v for k, v in rec.headers if k.lower() == "content-type"]
    assert values == ["text/x-custom"], rec.headers


@pytest.mark.posix
@pytest.mark.skipif(sys.platform == "win32", reason="argv bytes are POSIX-only")
@pytest.mark.usefixtures("need_raw_argv")
def test_data_non_utf8_bytes_sent_exactly(run: RunCommand, servers: Servers) -> None:
    token = _token()
    raw = b"\xff\xfe\x80raw\xc3"
    res = run(["--metrics-only", "-d", raw, servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_OK)
    assert "Traceback" not in res.output
    assert _one(servers.origin, token).body == raw


def test_get_with_body_warns(run: RunCommand, servers: Servers) -> None:
    token = _token()
    res = run(["--metrics-only", "-X", "GET", "-d", "abc", servers.url(servers.origin, f"/echo?id={token}")])
    res.expect(EXIT_OK)
    assert "uncommon" in res.stderr
    rec = _one(servers.origin, token)
    assert (rec.method, rec.body) == ("GET", b"abc")


def test_custom_headers_reach_origin(run: RunCommand, servers: Servers) -> None:
    token = _token()
    run(
        [
            "--metrics-only",
            "-H",
            "X-One: 1",
            "-H",
            "X-Two:two words ",
            "-H",
            "x-one: override",
            servers.url(servers.origin, f"/echo?id={token}"),
        ]
    ).expect(EXIT_OK)
    rec = _one(servers.origin, token)
    assert [v for k, v in rec.headers if k.lower() == "x-one"] == ["override"]
    assert rec.header("X-Two") == "two words"


def test_host_header_override(run: RunCommand, servers: Servers) -> None:
    token = _token()
    res = run(["--json", "-", "-H", "Host: virtual.example", servers.url(servers.origin, f"/echo?id={token}")])
    res.expect(EXIT_OK)
    assert _one(servers.origin, token).header("Host") == "virtual.example"
    assert res.json()["steps"][0]["request"]["headers"]["Host"] == "virtual.example"


def test_default_host_header(run: RunCommand, servers: Servers) -> None:
    token = _token()
    run(["--metrics-only", servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_OK)
    assert _one(servers.origin, token).header("Host") == f"{servers.host}:{servers.port(servers.origin)}"


SECRET_AUTH = "Bearer AAAAauthMIDDLEsecretZZZZ"
SECRET_COOKIE = "session=cookieMIDDLEsecretvalue"
SECRET_PROXY_AUTH = "Basic ppppPROXYmiddleSECRETqqqq"
SECRET_API_KEY = "kkkkAPIkeyMIDDLEsecretjjjj"


def test_sensitive_request_headers_masked_everywhere(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    token = _token()
    jpath, ppath = out_dir / "r.json", out_dir / "r.prom"
    res = run(
        [
            "--json",
            str(jpath),
            "--prometheus",
            str(ppath),
            "-H",
            f"Authorization: {SECRET_AUTH}",
            "-H",
            f"Cookie: {SECRET_COOKIE}",
            "-H",
            f"Proxy-Authorization: {SECRET_PROXY_AUTH}",
            "-H",
            f"X-Api-Key: {SECRET_API_KEY}",
            servers.url(servers.origin, f"/echo?id={token}"),
        ]
    ).expect(EXIT_OK)
    rec = _one(servers.origin, token)
    assert rec.header("Authorization") == SECRET_AUTH, "the real value is sent"
    for secret in ("authMIDDLEsecret", "cookieMIDDLEsecret", "PROXYmiddleSECRET", "APIkeyMIDDLEsecret"):
        assert_secret_absent(res, secret, jpath, ppath)
    headers = json.loads(jpath.read_text(encoding="utf-8"))["steps"][0]["request"]["headers"]
    assert "****" in headers["Authorization"]
    assert "****" in headers["Cookie"]


def test_echo_body_round_trip_reported_bytes(run: RunCommand, servers: Servers) -> None:
    token = _token()
    body = "x" * 1000
    res = run(["--json", "-", "-d", body, servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_OK)
    step = res.json()["steps"][0]
    assert step["request"]["method"] == "POST"
    assert step["request"]["body_bytes"] == 1000
    assert _one(servers.origin, token).body == body.encode()
