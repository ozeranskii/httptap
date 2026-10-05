"""Connectivity, address families, --resolve, deadlines and broken responses."""

from __future__ import annotations

import signal
import sys
import time

import pytest

from tests.e2e.harness import EXIT_NETWORK, EXIT_OK, Result, RunCommand, Runner, Servers, parse_metrics


def test_connection_refused(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", f"http://{servers.host}:{servers.dead.port}/"]).expect(EXIT_NETWORK)
    assert "refused" in res.stdout.lower()


def test_connection_refused_rich(run: RunCommand, servers: Servers) -> None:
    res = run([f"http://{servers.host}:{servers.dead.port}/"]).expect(EXIT_NETWORK)
    assert "Error" in res.stdout
    assert "Traceback" not in res.output


@pytest.mark.usefixtures("need_local")
def test_connection_refused_keeps_network_info(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", f"http://127.0.0.1:{servers.dead.port}/"]).expect(EXIT_NETWORK)
    step = res.json()["steps"][0]
    assert step["network"]["ip"] == "127.0.0.1"
    assert step["response"]["status"] is None


def test_unresolvable_name(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-m", "10", "http://does-not-exist.invalid/"]).expect(EXIT_NETWORK)
    assert "ERROR" in res.stdout


@pytest.mark.parametrize("flag", ["-4", "--ipv4"])
@pytest.mark.usefixtures("need_ipv6")
def test_ipv4_only(run: RunCommand, servers: Servers, flag: str) -> None:
    res = run(["--metrics-only", flag, f"http://localhost:{servers.port(servers.origin)}/ok"]).expect(EXIT_OK)
    step = parse_metrics(res.stdout)[0]
    assert (step["ip"], step["family"]) == ("127.0.0.1", "IPv4")


@pytest.mark.parametrize("flag", ["-6", "--ipv6"])
@pytest.mark.usefixtures("need_ipv6")
def test_ipv6_only(run: RunCommand, servers: Servers, flag: str) -> None:
    res = run(["--metrics-only", flag, f"http://localhost:{servers.port(servers.origin)}/ok"]).expect(EXIT_OK)
    step = parse_metrics(res.stdout)[0]
    assert (step["ip"], step["family"]) == ("::1", "IPv6")


@pytest.mark.usefixtures("need_ipv6")
def test_ipv6_only_without_v6_listener(run: RunCommand, servers: Servers) -> None:
    """origin2 listens on IPv4 only, so -6 must fail rather than silently using IPv4."""
    run(["--metrics-only", "-6", f"http://localhost:{servers.port(servers.origin2)}/ok"]).expect(EXIT_NETWORK)


@pytest.mark.usefixtures("need_ipv6")
def test_ipv6_literal_url(run: RunCommand, servers: Servers) -> None:
    token = "ipv6-literal"
    port = servers.port(servers.origin)
    res = run(["--json", "-", f"http://[::1]:{port}/echo?id={token}"]).expect(EXIT_OK)
    net = res.json()["steps"][0]["network"]
    assert (net["ip"], net["ip_family"]) == ("::1", "IPv6")
    (rec,) = servers.v6.find(token)
    assert rec.header("Host") == f"[::1]:{port}"


@pytest.mark.usefixtures("need_ipv6")
def test_ipv6_literal_with_ipv4_flag(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-4", f"http://[::1]:{servers.port(servers.origin)}/ok"])
    assert res.code in (EXIT_NETWORK, 64), res.describe()


def test_resolve_ipv4(run: RunCommand, servers: Servers) -> None:
    port = servers.port(servers.origin)
    token = "resolve-v4"
    res = run(
        [
            "--metrics-only",
            "--resolve",
            f"e2e.test:{port}:{servers.config.target_ip}",
            f"http://e2e.test:{port}/echo?id={token}",
        ]
    ).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["ip"] == servers.config.target_ip
    (rec,) = servers.origin.find(token)
    assert rec.header("Host") == f"e2e.test:{port}"


@pytest.mark.parametrize("addr", ["[::1]", "::1"])
@pytest.mark.usefixtures("need_ipv6")
def test_resolve_ipv6(run: RunCommand, servers: Servers, addr: str) -> None:
    port = servers.port(servers.origin)
    res = run(["--metrics-only", "--resolve", f"e2e.test:{port}:{addr}", f"http://e2e.test:{port}/ok"])
    res.expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["ip"] == "::1"


def test_resolve_other_port_not_applied(run: RunCommand, servers: Servers) -> None:
    port = servers.port(servers.origin)
    res = run(
        [
            "--metrics-only",
            "-m",
            "5",
            "--resolve",
            f"e2e.test:{port + 1}:{servers.config.target_ip}",
            f"http://e2e.test:{port}/ok",
        ]
    )
    res.expect(EXIT_NETWORK)


def test_resolve_with_socks5_local_dns_allowed(run: RunCommand, servers: Servers) -> None:
    port = servers.port(servers.origin)
    res = run(
        [
            "--metrics-only",
            "--resolve",
            f"e2e.test:{port}:{servers.config.target_ip}",
            "-x",
            servers.proxy_url(servers.socks, scheme="socks5"),
            f"http://e2e.test:{port}/ok",
        ]
    ).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["status"] == "200"
    rec = servers.socks.records[-1]
    assert rec.extra["atyp"] == "ipv4"
    assert rec.extra["host"] == servers.config.target_ip


@pytest.mark.usefixtures("need_ipv6")
def test_localhost_falls_back_to_ipv4(run: RunCommand, servers: Servers) -> None:
    """origin2 listens only on 127.0.0.1; if ::1 is tried first the IPv4 address must be used next."""
    res = run(["--json", "-", f"http://localhost:{servers.port(servers.origin2)}/ok"]).expect(EXIT_OK)
    step = res.json()["steps"][0]
    assert step["network"]["ip"] == "127.0.0.1"
    assert step["timing"]["total_ms"] <= res.wall * 1000


def _assert_deadline(res: Result, runner: Runner, max_time: float) -> None:
    assert res.wall <= runner.deadline(max_time), f"wall {res.wall:.2f}s > {runner.deadline(max_time):.2f}s" + (
        res.describe()
    )


@pytest.mark.slow
@pytest.mark.parametrize("flag", ["-m", "--max-time", "--timeout"])
def test_timeout_slow_headers(run: RunCommand, runner: Runner, servers: Servers, flag: str) -> None:
    res = run(["--metrics-only", flag, "1", servers.url(servers.origin, "/slow-headers?s=8")]).expect(EXIT_NETWORK)
    assert "timeout" in res.stdout.lower() or "deadline" in res.stdout.lower()
    _assert_deadline(res, runner, 1)


@pytest.mark.slow
def test_timeout_late_headers_then_stall(run: RunCommand, runner: Runner, servers: Servers) -> None:
    res = run(["--json", "-", "-m", "2", servers.url(servers.origin, "/slow-body?h=1.5")]).expect(EXIT_NETWORK)
    _assert_deadline(res, runner, 2)
    step = res.json()["steps"][0]
    assert step["network"]["ip"], "network info is kept when the deadline hits during the body"
    assert "deadline" in (step["error"] or "")


@pytest.mark.slow
def test_timeout_stall_after_headers(run: RunCommand, runner: Runner, servers: Servers) -> None:
    res = run(["--metrics-only", "-m", "1.5", servers.url(servers.origin, "/slow-body")]).expect(EXIT_NETWORK)
    _assert_deadline(res, runner, 1.5)


@pytest.mark.slow
def test_timeout_trickle(run: RunCommand, runner: Runner, servers: Servers) -> None:
    res = run(["--metrics-only", "-m", "1.5", servers.url(servers.origin, "/trickle")]).expect(EXIT_NETWORK)
    _assert_deadline(res, runner, 1.5)


@pytest.mark.slow
def test_trickle_within_deadline_succeeds(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-m", "10", servers.url(servers.origin, "/trickle?n=5&i=0.1")]).expect(EXIT_OK)
    step = parse_metrics(res.stdout)[0]
    assert step["bytes"] == "5"
    assert float(step["total"]) >= 400


@pytest.mark.slow
def test_timeout_json_has_error_and_partial_info(run: RunCommand, runner: Runner, servers: Servers) -> None:
    res = run(["--json", "-", "-m", "1", servers.url(servers.origin, "/slow-headers?s=8")]).expect(EXIT_NETWORK)
    data = res.json()
    assert data["summary"]["errors"] == 1
    assert data["steps"][0]["error"]
    _assert_deadline(res, runner, 1)


def test_close_mid_body(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", servers.url(servers.origin, "/close-mid-body")]).expect(EXIT_NETWORK)
    step = res.json()["steps"][0]
    assert step["error"]
    assert "Traceback" not in res.stderr


def test_close_mid_body_rich(run: RunCommand, servers: Servers) -> None:
    res = run([servers.url(servers.origin, "/close-mid-body")]).expect(EXIT_NETWORK)
    assert "Traceback" not in res.output


@pytest.mark.posix
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize(("sig", "code"), [(signal.SIGINT, 130), (signal.SIGTERM, 143)])
def test_signal_exit_code(runner: Runner, servers: Servers, sig: signal.Signals, code: int) -> None:
    proc = runner.spawn(["--metrics-only", servers.url(servers.origin, "/slow-headers?s=10")])
    try:
        time.sleep(runner.startup + 0.7)
        proc.send_signal(sig)
        out, err = proc.communicate(timeout=10)
    finally:
        proc.kill()
    assert proc.returncode == code, (proc.returncode, out, err)
    assert b"Traceback" not in err
