"""End-to-end CLI runs against a local HTTP server."""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import parse_qs, urlsplit

import pytest

from httptap.cli import EXIT_NETWORK_ERROR, main

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@dataclass
class _Received:
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class _Origin:
    url: str
    received: list[_Received] = field(default_factory=list)


class _OriginHandler(BaseHTTPRequestHandler):
    """Answer ``/redirect?to=URL`` with a 302 to URL and everything else with 200.

    ``/credentials`` redirects to ``/ok`` on the same server with ``alice:topsecret``
    userinfo, so the secret never appears in the URL httptap is started with.
    """

    protocol_version = "HTTP/1.1"
    received: ClassVar[list[_Received]]

    def do_GET(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        type(self).received.append(_Received(self.path, dict(self.headers), self.rfile.read(length)))
        target = parse_qs(urlsplit(self.path).query).get("to")
        if self.path == "/credentials":
            target = [f"http://alice:topsecret@127.0.0.1:{self.server.server_address[1]}/ok"]
        if target:
            self.send_response(302)
            self.send_header("Location", target[0])
        else:
            self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        self.do_GET()

    def log_message(self, *_args: object) -> None:
        """Keep the test output free of per-request access logs."""


@pytest.fixture
def origin() -> Iterator[_Origin]:
    handler = type("Origin", (_OriginHandler,), {"received": []})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _Origin(f"http://127.0.0.1:{server.server_address[1]}", handler.received)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _run(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["httptap", *argv])
    return main()


def test_follow_reports_redirect_step_when_target_port_is_invalid(
    origin: _Origin,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = tmp_path / "report.json"
    url = f"{origin.url}/redirect?to=http://127.0.0.1:99999/next"

    exit_code = _run(monkeypatch, "--follow", "--metrics-only", "--json", str(report), url)

    out, err = capsys.readouterr()
    assert exit_code == EXIT_NETWORK_ERROR
    assert "Step 1: dns=" in out
    assert "status=302" in out
    assert "Step 2: ERROR - Invalid redirect target: Port out of range" in out
    assert "Internal Error" not in err
    assert len(origin.received) == 1
    steps = json.loads(report.read_text(encoding="utf-8"))["steps"]
    assert [step["response"]["status"] for step in steps] == [302, None]
    assert steps[1]["url"] == "http://127.0.0.1:99999/next"
    assert steps[1]["error"].startswith("Invalid redirect target")


def test_location_credentials_are_redacted_but_followed(
    origin: _Origin,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = _run(monkeypatch, "--follow", "--json", "-", f"{origin.url}/credentials")

    out, err = capsys.readouterr()
    assert exit_code == 0
    steps = json.loads(out)["steps"]
    assert steps[0]["response"]["location"].startswith("http://alice:****@127.0.0.1:")
    assert steps[0]["response"]["headers"]["location"] == steps[0]["response"]["location"]
    assert steps[1]["response"]["status"] == 200
    assert origin.received[1].headers["Authorization"] == "Basic YWxpY2U6dG9wc2VjcmV0"
    assert "topsecret" not in out
    assert "topsecret" not in err


def test_rich_output_redacts_location_credentials(
    origin: _Origin,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = _run(monkeypatch, f"{origin.url}/credentials")

    out, err = capsys.readouterr()
    assert exit_code == 0
    assert f"http://alice:****@{origin.url.removeprefix('http://')}/ok" in out
    assert "topsecret" not in out + err


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows argv is Unicode; undecodable bytes only exist on POSIX",
)
def test_data_sends_raw_argument_bytes(
    origin: _Origin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = b"\xff\xfe raw".decode(sys.getfilesystemencoding(), "surrogateescape")

    exit_code = _run(monkeypatch, "--metrics-only", "-d", data, f"{origin.url}/echo")

    assert exit_code == 0
    assert origin.received[0].body == b"\xff\xfe raw"
