"""HTTP forward/CONNECT and SOCKS5 proxies, proxy auth, environment proxies and NO_PROXY."""

from __future__ import annotations

import json
import socket
import uuid
from typing import TYPE_CHECKING

import pytest

from tests.e2e.harness import (
    EXIT_HTTP_FAIL,
    EXIT_NETWORK,
    EXIT_OK,
    EXIT_USAGE,
    PROXY_PASSWORD,
    PROXY_USER,
    SOCKS_PASSWORD,
    SOCKS_USER,
    RunCommand,
    Servers,
    assert_secret_absent,
    parse_metrics,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.e2e.certs import CertSet


def _token() -> str:
    return uuid.uuid4().hex


def _named_https(servers: Servers, path: str = "/ok") -> str:
    return f"https://e2e.test:{servers.port(servers.tls_valid)}{path}"


def _named_http(servers: Servers, path: str = "/ok") -> str:
    return f"http://e2e.test:{servers.port(servers.origin)}{path}"


def test_http_forward_proxy(run: RunCommand, servers: Servers) -> None:
    token = _token()
    proxy = servers.proxy_url(servers.proxy)
    res = run(["--json", "-", "-x", proxy, _named_http(servers, f"/echo?id={token}")]).expect(EXIT_OK)
    step = res.json()["steps"][0]
    assert step["network"]["proxy_url"] == proxy
    assert step["network"]["proxy_source"] == "--proxy"
    assert step["response"]["status"] == 200
    (prec,) = servers.proxy.find(token)
    assert prec.method == "GET"
    assert prec.path.startswith("http://e2e.test:")
    assert len(servers.origin.find(token)) == 1


def test_connect_proxy_for_https(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    proxy = servers.proxy_url(servers.proxy)
    port = servers.port(servers.tls_valid)
    res = run(["--metrics-only", "-x", proxy, "--cacert", str(certs.ca), _named_https(servers)]).expect(EXIT_OK)
    step = parse_metrics(res.stdout)[0]
    assert step["status"] == "200"
    assert step["proxy_from"] == "arg"
    assert any(r.method == "CONNECT" and r.path == f"e2e.test:{port}" for r in servers.proxy.records)


def test_scheme_less_proxy_arg(run: RunCommand, servers: Servers) -> None:
    proxy = f"{servers.host}:{servers.port(servers.proxy)}"
    res = run(["--metrics-only", "-x", proxy, _named_http(servers)]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["proxy"] == f"http://{proxy}"


def test_proxy_basic_auth_forward(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    token = _token()
    jpath = out_dir / "r.json"
    proxy = servers.proxy_url(servers.proxy_auth, userinfo=f"{PROXY_USER}:{PROXY_PASSWORD}@")
    res = run(["--metrics-only", "--json", str(jpath), "-x", proxy, _named_http(servers, f"/echo?id={token}")])
    res.expect(EXIT_OK)
    (prec,) = servers.proxy_auth.find(token)
    assert prec.extra["auth_ok"] is True
    assert servers.origin.find(token)[0].header("Proxy-Authorization") is None, "proxy creds must not reach origin"
    assert_secret_absent(res, PROXY_PASSWORD, jpath)
    assert json.loads(jpath.read_text(encoding="utf-8"))["steps"][0]["network"]["proxy_url"] == (
        f"http://{PROXY_USER}:****@{servers.host}:{servers.port(servers.proxy_auth)}"
    )


def test_proxy_basic_auth_connect(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    proxy = servers.proxy_url(servers.proxy_auth, userinfo=f"{PROXY_USER}:{PROXY_PASSWORD}@")
    res = run(["--metrics-only", "-x", proxy, "--cacert", str(certs.ca), _named_https(servers)]).expect(EXIT_OK)
    assert_secret_absent(res, PROXY_PASSWORD)


def test_proxy_auth_missing_forward_returns_407(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-x", servers.proxy_url(servers.proxy_auth), _named_http(servers)]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["status"] == "407"


def test_proxy_auth_missing_forward_with_fail(run: RunCommand, servers: Servers) -> None:
    run(["--metrics-only", "-f", "-x", servers.proxy_url(servers.proxy_auth), _named_http(servers)]).expect(
        EXIT_HTTP_FAIL
    )


def test_proxy_auth_wrong_connect(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    proxy = servers.proxy_url(servers.proxy_auth, userinfo=f"{PROXY_USER}:WrongProxyPw999@")
    res = run(["--metrics-only", "-x", proxy, "--cacert", str(certs.ca), _named_https(servers)]).expect(EXIT_NETWORK)
    assert "407" in res.stdout
    assert_secret_absent(res, "WrongProxyPw999")


@pytest.mark.parametrize("scheme", ["http", "socks5", "socks5h"])
def test_dead_proxy(run: RunCommand, servers: Servers, scheme: str) -> None:
    proxy = f"{scheme}://user:DeadProxyPw77@{servers.host}:{servers.dead.port}"
    res = run(["--json", "-", "-x", proxy, _named_http(servers)]).expect(EXIT_NETWORK)
    assert res.json()["steps"][0]["error"]
    assert_secret_absent(res, "DeadProxyPw77")


def test_socks5h_remote_dns(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    proxy = servers.proxy_url(servers.socks, scheme="socks5h")
    port = servers.port(servers.tls_valid)
    res = run(["--metrics-only", "-x", proxy, "--cacert", str(certs.ca), _named_https(servers)]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["status"] == "200"
    assert any(
        r.extra.get("atyp") == "domain" and r.extra.get("host") == "e2e.test" and r.extra.get("port") == port
        for r in servers.socks.records
    )


def test_socks5_ip_target(run: RunCommand, servers: Servers) -> None:
    proxy = servers.proxy_url(servers.socks, scheme="socks5")
    res = run(["--metrics-only", "-x", proxy, servers.url(servers.origin)]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["status"] == "200"


@pytest.mark.parametrize("scheme", ["socks5", "socks5h"])
def test_socks_auth_ok(run: RunCommand, servers: Servers, scheme: str) -> None:
    proxy = servers.proxy_url(servers.socks_auth, scheme=scheme, userinfo=f"{SOCKS_USER}:{SOCKS_PASSWORD}@")
    res = run(["--metrics-only", "-x", proxy, servers.url(servers.origin)]).expect(EXIT_OK)
    assert_secret_absent(res, SOCKS_PASSWORD)
    assert any(r.extra.get("user") == SOCKS_USER and r.extra.get("result") == "ok" for r in servers.socks_auth.records)


def test_socks_auth_wrong(run: RunCommand, servers: Servers) -> None:
    proxy = servers.proxy_url(servers.socks_auth, scheme="socks5h", userinfo=f"{SOCKS_USER}:WrongSocksPw42@")
    res = run(["--json", "-", "-x", proxy, servers.url(servers.origin)]).expect(EXIT_NETWORK)
    assert_secret_absent(res, "WrongSocksPw42")


def test_socks_auth_required_but_not_given(run: RunCommand, servers: Servers) -> None:
    proxy = servers.proxy_url(servers.socks_auth, scheme="socks5h")
    run(["--metrics-only", "-x", proxy, servers.url(servers.origin)]).expect(EXIT_NETWORK)


@pytest.mark.parametrize(
    ("var", "https"),
    [("HTTP_PROXY", False), ("http_proxy", False), ("HTTPS_PROXY", True), ("ALL_PROXY", False), ("all_proxy", True)],
)
def test_env_proxy(run: RunCommand, servers: Servers, certs: CertSet, var: str, https: bool) -> None:  # noqa: FBT001
    proxy = servers.proxy_url(servers.proxy)
    args = ["--cacert", str(certs.ca), _named_https(servers)] if https else [_named_http(servers)]
    res = run(["--metrics-only", *args], env={var: proxy}).expect(EXIT_OK)
    step = parse_metrics(res.stdout)[0]
    assert step["proxy"] == proxy
    assert step["proxy_from"].lower() == f"env:{var}".lower()


def test_env_proxy_lowercase_wins(run: RunCommand, servers: Servers) -> None:
    good = servers.proxy_url(servers.proxy)
    bad = f"http://{servers.host}:{servers.dead.port}"
    res = run(["--metrics-only", _named_http(servers)], env={"http_proxy": good, "HTTP_PROXY": bad})
    res.expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["proxy"] == good


def test_env_proxy_json_source(run: RunCommand, servers: Servers) -> None:
    proxy = servers.proxy_url(servers.proxy)
    res = run(["--json", "-", _named_http(servers)], env={"HTTP_PROXY": proxy}).expect(EXIT_OK)
    net = res.json()["steps"][0]["network"]
    assert net["proxy_url"] == proxy
    assert "HTTP_PROXY" in (net["proxy_source"] or "")


@pytest.mark.parametrize("no_proxy_value", ["{host}", "*", "other.example,{host}", " {host} , other.example"])
def test_no_proxy_bypasses(run: RunCommand, servers: Servers, no_proxy_value: str) -> None:
    dead = f"http://{servers.host}:{servers.dead.port}"
    env = {"HTTP_PROXY": dead, "NO_PROXY": no_proxy_value.format(host=servers.config.target_host)}
    res = run(["--metrics-only", servers.url(servers.origin)], env=env).expect(EXIT_OK)
    step = parse_metrics(res.stdout)[0]
    assert step["proxy"] == "none"
    assert step["proxy_from"].lower() == "env:no_proxy"


@pytest.mark.parametrize("no_proxy_value", [".test", "test", "E2E.TEST"], ids=["dot-suffix", "suffix", "case"])
def test_no_proxy_domain_match(run: RunCommand, servers: Servers, no_proxy_value: str) -> None:
    """Domain entries match the host and its subdomains, case-insensitively.

    Note: unlike curl, a leading-dot entry (".e2e.test") does not match the bare name; that is the
    documented behaviour (docs/usage/advanced.md), so it is not asserted here.
    """
    port = servers.port(servers.origin)
    env = {"HTTP_PROXY": f"http://{servers.host}:{servers.dead.port}", "NO_PROXY": no_proxy_value}
    res = run(
        ["--metrics-only", "--resolve", f"e2e.test:{port}:{servers.config.target_ip}", f"http://e2e.test:{port}/ok"],
        env=env,
    ).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["proxy"] == "none"


def test_no_proxy_lowercase(run: RunCommand, servers: Servers) -> None:
    env = {"HTTP_PROXY": f"http://{servers.host}:{servers.dead.port}", "no_proxy": servers.config.target_host}
    run(["--metrics-only", servers.url(servers.origin)], env=env).expect(EXIT_OK)


def test_no_proxy_non_matching_uses_proxy(run: RunCommand, servers: Servers) -> None:
    env = {"HTTP_PROXY": servers.proxy_url(servers.proxy), "NO_PROXY": "unrelated.example"}
    res = run(["--metrics-only", _named_http(servers)], env=env).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["proxy"] == servers.proxy_url(servers.proxy)


def test_empty_proxy_ignores_env(run: RunCommand, servers: Servers) -> None:
    env = {
        "HTTP_PROXY": f"http://{servers.host}:{servers.dead.port}",
        "ALL_PROXY": f"http://{servers.host}:{servers.dead.port}",
    }
    res = run(["--metrics-only", "--proxy", "", servers.url(servers.origin)], env=env).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["proxy"] in ("direct", "none", "disabled")


def test_arg_proxy_overrides_env(run: RunCommand, servers: Servers) -> None:
    env = {"HTTP_PROXY": f"http://{servers.host}:{servers.dead.port}"}
    proxy = servers.proxy_url(servers.proxy)
    res = run(["--metrics-only", "-x", proxy, _named_http(servers)], env=env).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["proxy_from"] == "arg"


def test_env_proxy_scheme_less_with_credentials(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    jpath = out_dir / "r.json"
    proxy = f"{PROXY_USER}:{PROXY_PASSWORD}@{servers.host}:{servers.port(servers.proxy_auth)}"
    res = run(["--metrics-only", "--json", str(jpath), _named_http(servers)], env={"HTTP_PROXY": proxy})
    assert_secret_absent(res, PROXY_PASSWORD, jpath)
    res.expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["status"] == "200"


def test_env_proxy_scheme_less_without_credentials(run: RunCommand, servers: Servers) -> None:
    proxy = f"{servers.host}:{servers.port(servers.proxy)}"
    run(["--metrics-only", _named_http(servers)], env={"HTTP_PROXY": proxy}).expect(EXIT_OK)


@pytest.mark.parametrize(
    "value",
    ["http://[::1", "http://127.0.0.1:99999"],
)
def test_env_proxy_malformed_is_network_error(run: RunCommand, servers: Servers, value: str) -> None:
    res = run(
        ["--metrics-only", servers.url(servers.origin)],
        env={"HTTP_PROXY": value.replace("http://", "http://u:EnvMalformedPw@")},
    )
    assert_secret_absent(res, "EnvMalformedPw")
    res.expect(EXIT_NETWORK)


def test_env_proxy_credentials_not_leaked_on_failure(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    jpath = out_dir / "r.json"
    proxy = f"http://u:EnvDeadProxyPw@{servers.host}:{servers.dead.port}"
    res = run(["--json", str(jpath), _named_http(servers)], env={"HTTP_PROXY": proxy}).expect(EXIT_NETWORK)
    assert_secret_absent(res, "EnvDeadProxyPw", jpath)


@pytest.mark.parametrize("scheme", ["http", "socks5h"])
def test_family_flag_rejected_with_remote_dns_proxy(run: RunCommand, servers: Servers, scheme: str) -> None:
    proxy = servers.proxy_url(servers.proxy if scheme == "http" else servers.socks, scheme=scheme)
    run(["-4", "-x", proxy, _named_http(servers)]).expect(EXIT_USAGE)


def test_family_flag_rejected_with_env_proxy(run: RunCommand, servers: Servers) -> None:
    run(["-4", _named_http(servers)], env={"HTTP_PROXY": servers.proxy_url(servers.proxy)}).expect(EXIT_USAGE)


def test_family_flag_allowed_with_no_proxy_bypass(run: RunCommand, servers: Servers) -> None:
    env = {"HTTP_PROXY": servers.proxy_url(servers.proxy), "NO_PROXY": servers.config.target_host}
    run(["--metrics-only", "-4", servers.url(servers.origin)], env=env).expect(EXIT_OK)


def test_family_flag_allowed_with_socks5(run: RunCommand, servers: Servers) -> None:
    proxy = servers.proxy_url(servers.socks, scheme="socks5")
    run(["--metrics-only", "-4", "-x", proxy, servers.url(servers.origin)]).expect(EXIT_OK)


@pytest.mark.parametrize("scheme", ["http", "socks5h"])
@pytest.mark.usefixtures("need_ipv6")
def test_ipv6_literal_through_remote_dns_proxy(run: RunCommand, servers: Servers, scheme: str) -> None:
    token = _token()
    proxy = servers.proxy_url(servers.proxy if scheme == "http" else servers.socks, scheme=scheme)
    url = f"http://[::1]:{servers.port(servers.origin)}/echo?id={token}"
    res = run(["--metrics-only", "-x", proxy, url]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["status"] == "200"
    assert len(servers.v6.find(token)) == 1


@pytest.mark.usefixtures("need_ipv6")
def test_ipv6_literal_through_socks5(run: RunCommand, servers: Servers) -> None:
    proxy = servers.proxy_url(servers.socks, scheme="socks5")
    res = run(["--metrics-only", "-x", proxy, f"http://[::1]:{servers.port(servers.origin)}/ok"]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["status"] == "200"


@pytest.mark.usefixtures("need_ipv6")
def test_socks5_falls_back_to_next_address(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    """tls_valid listens on 127.0.0.1 only; localhost resolves to ::1 too. The SOCKS proxy refuses ::1."""
    servers.socks.refuse.add("::1")
    try:
        proxy = servers.proxy_url(servers.socks, scheme="socks5")
        url = f"https://localhost:{servers.port(servers.tls_valid)}/ok"
        res = run(["--metrics-only", "-x", proxy, "--cacert", str(certs.ca), url]).expect(EXIT_OK)
        assert parse_metrics(res.stdout)[0]["status"] == "200"
    finally:
        servers.socks.refuse.discard("::1")


def _need_tls_v6(servers: Servers) -> None:
    if servers.tls_ip_v6 is None:
        pytest.skip("IPv6 TLS twin unavailable")


@pytest.mark.usefixtures("need_ipv6")
def test_ipv6_literal_forward_request_line_is_bracketed(run: RunCommand, servers: Servers) -> None:
    token = _token()
    url = f"http://[::1]:{servers.port(servers.origin)}/echo?id={token}"
    run(["--metrics-only", "-x", servers.proxy_url(servers.proxy), url]).expect(EXIT_OK)
    (record,) = servers.proxy.find(token)
    assert record.path.startswith(f"http://[::1]:{servers.port(servers.origin)}/")


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.usefixtures("need_ipv6")
def test_https_ipv6_literal_through_connect_is_verified(
    run: RunCommand,
    servers: Servers,
    certs: CertSet,
    authenticated: bool,  # noqa: FBT001
) -> None:
    _need_tls_v6(servers)
    port = servers.port(servers.tls_ip)
    proxy_server = servers.proxy_auth if authenticated else servers.proxy
    userinfo = f"{PROXY_USER}:{PROXY_PASSWORD}@" if authenticated else ""
    before = len(proxy_server.records)
    res = run(
        [
            "--json",
            "-",
            "--cacert",
            str(certs.ca),
            "-x",
            servers.proxy_url(proxy_server, userinfo=userinfo),
            f"https://[::1]:{port}/ok",
        ]
    ).expect(EXIT_OK)
    step = json.loads(res.stdout)["steps"][0]
    assert step["response"]["status"] == 200
    assert step["network"]["tls_verified"] is True
    assert any(san.replace("0:0:0:0:0:0:0:1", "::1") == "::1" for san in step["network"]["cert_sans"])
    connects = [r for r in proxy_server.records[before:] if r.method == "CONNECT"]
    assert [r.path for r in connects] == [f"[::1]:{port}"]
    if authenticated:
        assert_secret_absent(res, PROXY_PASSWORD)


@pytest.mark.usefixtures("need_ipv6")
def test_https_ipv6_literal_through_connect_insecure(run: RunCommand, servers: Servers) -> None:
    _need_tls_v6(servers)
    port = servers.port(servers.tls_ip)
    res = run(["--json", "-", "-k", "-x", servers.proxy_url(servers.proxy), f"https://[::1]:{port}/ok"]).expect(EXIT_OK)
    step = json.loads(res.stdout)["steps"][0]
    assert step["response"]["status"] == 200
    assert step["network"]["tls_verified"] is False


def test_strict_proxy_rejects_unbracketed_ipv6_authority(servers: Servers) -> None:
    """Guard for the harness itself: the proxy behaves like Squid."""
    with socket.create_connection(("127.0.0.1", servers.port(servers.proxy)), timeout=5) as sock:
        sock.sendall(b"CONNECT ::1:443 HTTP/1.1\r\nHost: ::1:443\r\n\r\n")
        assert sock.recv(64).startswith(b"HTTP/1.1 400")
