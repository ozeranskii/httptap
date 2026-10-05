"""Options and session fixtures for the black-box end-to-end suite."""

from __future__ import annotations

import ipaddress
import os
import shlex
import shutil
import socket
import statistics
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.e2e import certs as certs_mod
from tests.e2e import servers as srv
from tests.e2e.harness import (
    PROXY_PASSWORD,
    PROXY_USER,
    SOCKS_PASSWORD,
    SOCKS_USER,
    HarnessConfig,
    RunCommand,
    Runner,
    Servers,
)

if TYPE_CHECKING:
    import socketserver
    from collections.abc import Callable, Iterator

_HTTPTAP_PREFIX = pytest.StashKey[list[str]]()
_CONTAINER_CLIENTS = frozenset({"docker", "podman"})


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("httptap-e2e")
    group.addoption(
        "--httptap",
        default=None,
        help="Command prefix used to run httptap (shell-split), e.g. '/venv/bin/httptap' or "
        "'docker run --rm -v DIR:DIR IMAGE'. Env: HTTPTAP_CMD. Default: the httptap script next to "
        "the running Python interpreter, then httptap on PATH.",
    )
    group.addoption(
        "--target-host",
        default="127.0.0.1",
        help="Host name/IP httptap uses to reach the test servers (e.g. host.docker.internal).",
    )
    group.addoption(
        "--target-ip",
        default=None,
        help="IP of --target-host as seen by httptap, used for --resolve tests (default: resolve locally).",
    )
    group.addoption(
        "--bind-host",
        default=None,
        help="Address the servers bind to (default 127.0.0.1, or 0.0.0.0 if --target-host is not loopback).",
    )
    group.addoption(
        "--shared-dir",
        default=None,
        help="Directory for certificates and output files; must be visible to httptap at the same path "
        "(mount it into the container when using Docker).",
    )
    group.addoption(
        "--wall-slack",
        type=float,
        default=0.75,
        help="Allowed seconds over -m/--max-time, on top of the measured process start-up time.",
    )


def _httptap_prefix(config: pytest.Config) -> list[str] | None:
    command = config.getoption("--httptap") or os.environ.get("HTTPTAP_CMD")
    if command:
        # An existing file is one argv item, so Windows paths and paths with spaces need no quoting.
        return [command] if Path(command).is_file() else shlex.split(command)
    # A discovered path is used as one argv item: shlex would mangle Windows paths and paths with spaces.
    script = Path(sys.executable).parent / ("httptap.exe" if sys.platform == "win32" else "httptap")
    if script.is_file():
        return [str(script)]
    found = shutil.which("httptap")
    return [found] if found else None


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "posix: needs POSIX argv byte semantics")
    config.addinivalue_line("markers", "slow: takes several seconds of wall time")
    if config.option.help:
        return
    prefix = _httptap_prefix(config)
    if prefix is None:
        msg = (
            "httptap executable not found next to the Python interpreter or on PATH; "
            "pass --httptap COMMAND or set HTTPTAP_CMD"
        )
        raise pytest.UsageError(msg)
    config.stash[_HTTPTAP_PREFIX] = prefix


def pytest_report_header(config: pytest.Config) -> list[str]:
    prefix: list[str] = config.stash[_HTTPTAP_PREFIX]
    return [
        f"httptap command: {shlex.join(prefix)}",
        f"target host: {config.getoption('--target-host')}",
    ]


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


@pytest.fixture(scope="session")
def config(request: pytest.FixtureRequest) -> Iterator[HarnessConfig]:
    opt = request.config.getoption
    target_host = opt("--target-host")
    loopback = _is_loopback(target_host)
    bind_host = opt("--bind-host") or ("127.0.0.1" if loopback else "0.0.0.0")  # noqa: S104
    target_ip = opt("--target-ip")
    if target_ip is None:
        target_ip = target_host if target_host != "localhost" else "127.0.0.1"
        try:
            ipaddress.ip_address(target_ip)
        except ValueError:
            target_ip = socket.gethostbyname(target_host)
    shared = opt("--shared-dir")
    if shared:
        Path(shared).mkdir(parents=True, exist_ok=True)
    # One private directory per session (and per xdist worker) so parallel workers never share certificates.
    shared_dir = Path(tempfile.mkdtemp(prefix="httptap-e2e-", dir=shared or None))
    prefix = request.config.stash[_HTTPTAP_PREFIX]
    yield HarnessConfig(
        prefix=prefix,
        target_host=target_host,
        target_ip=target_ip,
        bind_host=bind_host,
        loopback=loopback,
        shared_dir=shared_dir,
        container=Path(prefix[0]).stem in _CONTAINER_CLIENTS and "run" in prefix,
        wall_slack=opt("--wall-slack"),
    )
    shutil.rmtree(shared_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def certs(config: HarnessConfig) -> certs_mod.CertSet:
    extra = [] if config.target_host in {"127.0.0.1", "localhost"} else [config.target_host]
    if config.target_ip != "127.0.0.1":
        extra.append(config.target_ip)
    return certs_mod.generate(config.shared_dir / "certs", extra)


def _v6_twin(
    primary: srv.HTTPServerV4,
    factory: Callable[[tuple[str, int]], srv.HTTPServerV6],
    started: list[socketserver.BaseServer],
) -> srv.HTTPServerV6 | None:
    """Listen on ``::1`` with the port of ``primary`` and share its request log."""
    twin = srv.bind_v6_same_port(primary.server_address[1], factory)
    if twin is not None:
        primary.twins.append(twin)
        twin.twins.append(primary)
        started.append(srv.start(twin))
    return twin


@pytest.fixture(scope="session")
def servers(config: HarnessConfig, certs: certs_mod.CertSet) -> Iterator[Servers]:
    bind = config.bind_host
    started: list[socketserver.BaseServer] = []

    def http(tls_pair: certs_mod.CertPair | None = None) -> srv.HTTPServerV4:
        ctx = srv.tls_context(str(tls_pair.cert), str(tls_pair.key)) if tls_pair else None
        server = srv.HTTPServerV4((bind, 0), srv.OriginHandler, tls=ctx)
        started.append(srv.start(server))
        return server

    host_map = {
        config.target_host.lower(): "127.0.0.1",
        config.target_ip: "127.0.0.1",
        certs_mod.TEST_NAME: "127.0.0.1",
        certs_mod.IDN_ALABEL: "127.0.0.1",
        "localhost": "127.0.0.1",
    }

    def proxy(auth: tuple[str, str] | None) -> srv.ProxyServer:
        server = srv.ProxyServer((bind, 0), auth=auth, host_map=host_map)
        started.append(srv.start(server))
        return server

    def socks(auth: tuple[str, str] | None) -> srv.SocksServer:
        server = srv.SocksServer((bind, 0), auth=auth, host_map=host_map)
        started.append(srv.start(server))
        return server

    def collector(fail: int | None) -> srv.CollectorServer:
        server = srv.CollectorServer((bind, 0), fail_status=fail)
        started.append(srv.start(server))
        return server

    origin = http()
    origin2 = http()
    tls_ip = http(certs.ip_only)
    origin_v6 = tls_ip_v6 = None
    if config.loopback:
        origin_v6 = _v6_twin(origin, lambda addr: srv.HTTPServerV6(addr, srv.OriginHandler), started)
        ip_only_ctx = srv.tls_context(str(certs.ip_only.cert), str(certs.ip_only.key))
        tls_ip_v6 = _v6_twin(tls_ip, lambda addr: srv.HTTPServerV6(addr, srv.OriginHandler, tls=ip_only_ctx), started)
    host = f"[{config.target_host}]" if ":" in config.target_host else config.target_host
    origin.peer_base = f"http://{host}:{origin2.server_address[1]}"
    origin2.peer_base = f"http://{host}:{origin.server_address[1]}"
    if origin_v6 is not None:
        origin_v6.peer_base = origin.peer_base

    bundle = Servers(
        config=config,
        origin=origin,
        origin2=origin2,
        origin_v6=origin_v6,
        tls_valid=http(certs.valid),
        tls_self=http(certs.self_signed),
        tls_expired=http(certs.expired),
        tls_wrong=http(certs.wrong_host),
        tls_ip=tls_ip,
        tls_ip_v6=tls_ip_v6,
        proxy=proxy(None),
        proxy_auth=proxy((PROXY_USER, PROXY_PASSWORD)),
        socks=socks(None),
        socks_auth=socks((SOCKS_USER, SOCKS_PASSWORD)),
        collector=collector(None),
        collector_fail=collector(500),
        dead=srv.DeadPort(),
    )
    yield bundle
    for server in started:
        srv.stop(server)


@pytest.fixture(scope="session")
def runner(config: HarnessConfig) -> Runner:
    r = Runner(config)
    r.startup = statistics.median(r.run(["--version"]).wall for _ in range(2))
    return r


@pytest.fixture(scope="session")
def preflight(runner: Runner, servers: Servers) -> None:
    """Fail fast when httptap cannot reach the servers (wrong --target-host, firewall, container networking)."""
    res = runner.run(["--metrics-only", "-m", "5", servers.url(servers.origin)], timeout=30)
    if res.code != 0:
        pytest.exit(
            "preflight failed: httptap could not reach the test origin. Check --httptap, --target-host and "
            f"--bind-host (and the firewall).{res.describe()}",
            returncode=3,
        )


@pytest.fixture
def run(runner: Runner, preflight: None) -> RunCommand:
    return runner.run


@pytest.fixture
def out_dir(config: HarnessConfig, request: pytest.FixtureRequest) -> Iterator[Path]:
    """Per-test directory inside the shared dir (visible to a containerised httptap)."""
    safe = "".join(c if c.isalnum() else "_" for c in request.node.name)[:80]
    path = Path(tempfile.mkdtemp(prefix=f"{safe}-", dir=config.shared_dir))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def need_ipv6(config: HarnessConfig, servers: Servers) -> None:
    if not config.loopback or servers.origin_v6 is None:
        pytest.skip("IPv6 loopback twin unavailable or target host is not loopback")


@pytest.fixture
def need_local(config: HarnessConfig) -> None:
    if not config.loopback:
        pytest.skip("needs httptap on the same loopback as the servers")


@pytest.fixture
def need_raw_argv(config: HarnessConfig) -> None:
    if config.container:
        pytest.skip("container clients send argv as JSON strings, so non-UTF-8 bytes do not reach httptap")
