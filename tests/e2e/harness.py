"""Black-box runner and assertion helpers. Never imports httptap."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import socketserver
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

    from tests.e2e import servers as srv

EXIT_OK = 0
EXIT_SLO = 4
EXIT_HTTP_FAIL = 22
EXIT_REDIRECTS = 47
EXIT_USAGE = 64
EXIT_INTERNAL = 70
EXIT_CANTCREAT = 73
EXIT_NETWORK = 75

PROXY_USER = "puser"
PROXY_PASSWORD = "pr0xyS3cretPW"
SOCKS_USER = "suser"
SOCKS_PASSWORD = "s0cksS3cretPW"

_PROXY_ENV = {"http_proxy", "https_proxy", "all_proxy", "no_proxy", "ftp_proxy", "socks_proxy"}


@dataclass
class HarnessConfig:
    prefix: list[str]
    target_host: str
    target_ip: str
    bind_host: str
    loopback: bool
    shared_dir: Path
    container: bool
    wall_slack: float


@dataclass
class Result:
    argv: list[str]
    code: int
    stdout_bytes: bytes
    stderr_bytes: bytes
    wall: float
    env: dict[str, str] = field(default_factory=dict)

    # Text streams on Windows end lines with CRLF; the text views use LF on every platform.
    @property
    def stdout(self) -> str:
        return self.stdout_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")

    @property
    def stderr(self) -> str:
        return self.stderr_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")

    @property
    def output(self) -> str:
        return self.stdout + "\n" + self.stderr

    def json(self) -> dict[str, Any]:
        data: dict[str, Any] = json.loads(self.stdout)
        return data

    def describe(self) -> str:
        env = " ".join(f"{k}={v}" for k, v in self.env.items())
        return (
            f"\n$ {env} {' '.join(self.argv)}\nexit={self.code} wall={self.wall:.2f}s\n"
            f"--- stdout ---\n{self.stdout[-4000:]}\n--- stderr ---\n{self.stderr[-4000:]}"
        )

    def expect(self, code: int) -> Result:
        assert self.code == code, f"expected exit {code}, got {self.code}{self.describe()}"
        return self


class RunCommand(Protocol):
    """Signature of the ``run`` fixture (``Runner.run``)."""

    def __call__(
        self,
        args: Sequence[str | bytes],
        *,
        env: Mapping[str, str] | None = None,
        timeout: float = 60.0,
    ) -> Result: ...


class Runner:
    def __init__(self, config: HarnessConfig) -> None:
        self.config = config
        self.startup = 0.0

    @staticmethod
    def _base_env() -> dict[str, str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if k.lower() not in _PROXY_ENV and not k.startswith(("OTEL_", "HTTPTAP_", "SSL_CERT", "REQUESTS_CA"))
        }
        env.update({"COLUMNS": "250", "TERM": "dumb", "PYTHONIOENCODING": "utf-8"})
        return env

    def run(
        self,
        args: Sequence[str | bytes],
        *,
        env: Mapping[str, str] | None = None,
        timeout: float = 60.0,
    ) -> Result:
        prefix = list(self.config.prefix)
        extra_env = {"COLUMNS": "250", **(env or {})}
        full_env = self._base_env()
        full_env.update(env or {})
        if self.config.container:
            # The client's environment does not reach the container: pass it explicitly.
            idx = prefix.index("run") + 1
            for key, value in extra_env.items():
                prefix[idx:idx] = ["-e", f"{key}={value}"]
        argv: list[str | bytes] = [*prefix, *args]
        start = time.monotonic()
        proc = subprocess.run(  # noqa: S603
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=full_env,
            timeout=timeout,
            check=False,
        )
        wall = time.monotonic() - start
        shown = [a.decode("utf-8", "backslashreplace") if isinstance(a, bytes) else a for a in argv]
        return Result(shown, proc.returncode, proc.stdout, proc.stderr, wall, dict(env or {}))

    def spawn(self, args: Sequence[str]) -> subprocess.Popen[bytes]:
        """Start httptap without waiting, for signal tests."""
        return subprocess.Popen(  # noqa: S603
            [*self.config.prefix, *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._base_env(),
        )

    def deadline(self, max_time: float) -> float:
        return max_time + self.config.wall_slack + self.startup


@dataclass
class Servers:
    config: HarnessConfig
    origin: srv.HTTPServerV4
    origin2: srv.HTTPServerV4
    origin_v6: srv.HTTPServerV6 | None
    tls_valid: srv.HTTPServerV4
    tls_self: srv.HTTPServerV4
    tls_expired: srv.HTTPServerV4
    tls_wrong: srv.HTTPServerV4
    tls_ip: srv.HTTPServerV4
    tls_ip_v6: srv.HTTPServerV6 | None
    proxy: srv.ProxyServer
    proxy_auth: srv.ProxyServer
    socks: srv.SocksServer
    socks_auth: srv.SocksServer
    collector: srv.CollectorServer
    collector_fail: srv.CollectorServer
    dead: srv.DeadPort

    @property
    def host(self) -> str:
        h = self.config.target_host
        return f"[{h}]" if ":" in h else h

    @property
    def v6(self) -> srv.HTTPServerV6:
        """The IPv6 twin of ``origin``; only for tests that use the ``need_ipv6`` fixture."""
        assert self.origin_v6 is not None
        return self.origin_v6

    def url(self, server: socketserver.TCPServer, path: str = "/ok", *, host: str | None = None) -> str:
        scheme = "https" if getattr(server, "tls", None) is not None else "http"
        return f"{scheme}://{host or self.host}:{server.server_address[1]}{path}"

    @staticmethod
    def port(server: socketserver.TCPServer) -> int:
        return server.server_address[1]

    def proxy_url(self, server: socketserver.TCPServer, *, scheme: str = "http", userinfo: str = "") -> str:
        return f"{scheme}://{userinfo}{self.host}:{server.server_address[1]}"


_METRIC_LINE = re.compile(r"^Step (\d+): (.*)$")


def parse_metrics(stdout: str) -> list[dict[str, str]]:
    """Parse --metrics-only lines into dicts; every token must be key=value."""
    steps = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        match = _METRIC_LINE.match(line)
        assert match, f"unexpected metrics-only line: {line!r}"
        fields: dict[str, str] = {"step": match.group(1)}
        rest = match.group(2)
        if rest.startswith("ERROR"):
            fields["error"] = rest
        else:
            for token in rest.split(" "):
                assert "=" in token, f"token {token!r} is not key=value in {line!r}"
                key, _, value = token.partition("=")
                assert re.fullmatch(r"[a-z_]+", key), f"bad key in {token!r}"
                fields[key] = value
        steps.append(fields)
    return steps


def assert_absent(secret: str, *texts: str | bytes, where: Iterable[str] = ()) -> None:
    names = list(where) or [f"text#{i}" for i in range(len(texts))]
    for name, text in zip(names, texts, strict=False):
        blob = text.decode("utf-8", errors="replace") if isinstance(text, bytes) else text
        assert secret not in blob, f"secret {secret!r} leaked in {name}:\n{blob[-3000:]}"


def assert_secret_absent(result: Result, secret: str, *files: Path, extra: Iterable[bytes] = ()) -> None:
    assert_absent(secret, result.stdout, result.stderr, where=["stdout", "stderr"])
    for path in files:
        if path.exists():
            assert_absent(secret, path.read_bytes(), where=[str(path)])
    for i, blob in enumerate(extra):
        assert_absent(secret, blob, where=[f"extra#{i}"])


def assert_timing_invariants(step: Mapping[str, Any], wall: float) -> None:
    t = step["timing"]
    phases = ("dns_ms", "connect_ms", "tls_ms", "wait_ms", "xfer_ms", "ttfb_ms", "total_ms")
    for key in phases:
        assert t[key] >= 0, f"{key} negative: {t}"
    summed = t["dns_ms"] + t["connect_ms"] + t["tls_ms"] + t["wait_ms"] + t["xfer_ms"]
    tolerance = max(1.0, 0.02 * t["total_ms"])
    assert abs(summed - t["total_ms"]) <= tolerance, f"phases sum {summed:.3f} != total {t['total_ms']}: {t}"
    assert t["ttfb_ms"] <= t["total_ms"] + 0.01, t
    assert t["total_ms"] <= wall * 1000, f"total_ms {t['total_ms']} > wall {wall * 1000:.1f}ms"
