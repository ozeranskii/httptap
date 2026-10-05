"""TLS verification, custom CAs, -k, certificate error classes, IDN names and HTTP/1.1 forcing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e import certs as certs_mod
from tests.e2e.harness import EXIT_NETWORK, EXIT_OK, RunCommand, Servers, parse_metrics

if TYPE_CHECKING:
    from tests.e2e.certs import CertSet
    from tests.e2e.servers import HTTPServerV4


def _named(
    servers: Servers, server: HTTPServerV4, name: str = certs_mod.TEST_NAME, path: str = "/ok"
) -> tuple[list[str], str]:
    port = servers.port(server)
    return ["--resolve", f"{name}:{port}:{servers.config.target_ip}"], f"https://{name}:{port}{path}"


def test_valid_cert_with_cacert(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    resolve, url = _named(servers, servers.tls_valid)
    res = run(["--json", "-", "--cacert", str(certs.ca), *resolve, url]).expect(EXIT_OK)
    net = res.json()["steps"][0]["network"]
    assert net["tls_verified"] is True
    assert net["tls_custom_ca"] is True
    assert net["tls_version"] in ("TLSv1.2", "TLSv1.3")
    assert net["cert_cn"] == certs_mod.TEST_NAME
    assert net["cert_issuer"] == "httptap e2e test CA"
    assert certs_mod.TEST_NAME in net["cert_sans"]
    assert 18 <= net["cert_days_left"] <= 20
    assert net["http_version"] == "HTTP/1.1"


def test_ca_bundle_alias(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    resolve, url = _named(servers, servers.tls_valid)
    run(["--metrics-only", "--ca-bundle", str(certs.ca), *resolve, url]).expect(EXIT_OK)


@pytest.mark.usefixtures("need_local")
def test_ip_san(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    url = f"https://127.0.0.1:{servers.port(servers.tls_ip)}/ok"
    res = run(["--metrics-only", "--cacert", str(certs.ca), url]).expect(EXIT_OK)
    assert parse_metrics(res.stdout)[0]["status"] == "200"


def test_unknown_ca_fails(run: RunCommand, servers: Servers) -> None:
    resolve, url = _named(servers, servers.tls_valid)
    res = run(["--metrics-only", *resolve, url]).expect(EXIT_NETWORK)
    assert "certificate" in res.stdout.lower()


def test_self_signed_fails_without_k(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    resolve, url = _named(servers, servers.tls_self)
    res = run(["--metrics-only", "--cacert", str(certs.ca), *resolve, url]).expect(EXIT_NETWORK)
    assert "certificate" in res.stdout.lower()


@pytest.mark.parametrize("flag", ["-k", "--insecure", "--ignore-ssl"])
def test_self_signed_with_insecure(run: RunCommand, servers: Servers, flag: str) -> None:
    resolve, url = _named(servers, servers.tls_self)
    res = run(["--json", "-", flag, *resolve, url]).expect(EXIT_OK)
    net = res.json()["steps"][0]["network"]
    assert net["tls_verified"] is False
    assert net["cert_cn"] == certs_mod.TEST_NAME, "peer certificate details are still reported with -k"


def test_expired_fails(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    resolve, url = _named(servers, servers.tls_expired)
    res = run(["--metrics-only", "--cacert", str(certs.ca), *resolve, url]).expect(EXIT_NETWORK)
    assert "expired" in res.stdout.lower()


def test_expired_with_insecure_reports_negative_days(run: RunCommand, servers: Servers) -> None:
    resolve, url = _named(servers, servers.tls_expired)
    res = run(["--json", "-", "-k", *resolve, url]).expect(EXIT_OK)
    assert res.json()["steps"][0]["network"]["cert_days_left"] < 0


def test_hostname_mismatch_fails(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    resolve, url = _named(servers, servers.tls_wrong)
    res = run(["--metrics-only", "--cacert", str(certs.ca), *resolve, url]).expect(EXIT_NETWORK)
    assert "hostname" in res.stdout.lower() or "match" in res.stdout.lower()


def test_hostname_mismatch_with_insecure(run: RunCommand, servers: Servers) -> None:
    resolve, url = _named(servers, servers.tls_wrong)
    res = run(["--json", "-", "-k", *resolve, url]).expect(EXIT_OK)
    assert res.json()["steps"][0]["network"]["cert_cn"] == certs_mod.WRONG_NAME


def test_tls_error_rich_output(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    resolve, url = _named(servers, servers.tls_expired)
    res = run(["--cacert", str(certs.ca), *resolve, url]).expect(EXIT_NETWORK)
    assert "Error" in res.stdout
    assert "Traceback" not in res.output


def test_plain_http_to_tls_port(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-m", "5", f"http://{servers.host}:{servers.port(servers.tls_valid)}/ok"])
    assert res.code == EXIT_NETWORK, res.describe()


def test_tls_to_plain_http_port(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-k", "-m", "5", f"https://{servers.host}:{servers.port(servers.origin)}/ok"])
    res.expect(EXIT_NETWORK)


@pytest.mark.parametrize("flag", ["--no-http2", "--http1.1"])
def test_force_http11(run: RunCommand, servers: Servers, certs: CertSet, flag: str) -> None:
    resolve, url = _named(servers, servers.tls_valid)
    res = run(["--json", "-", flag, "--cacert", str(certs.ca), *resolve, url]).expect(EXIT_OK)
    assert res.json()["steps"][0]["network"]["http_version"] == "HTTP/1.1"


def test_idn_url_with_unicode_resolve(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    """Host/SNI use the A-label; the cert only has the A-label SAN."""
    port = servers.port(servers.tls_valid)
    token = "idn-unicode-resolve"
    url = f"https://{certs_mod.IDN_ULABEL}:{port}/echo?id={token}"
    res = run(
        [
            "--json",
            "-",
            "--cacert",
            str(certs.ca),
            "--resolve",
            f"{certs_mod.IDN_ULABEL}:{port}:{servers.config.target_ip}",
            url,
        ]
    ).expect(EXIT_OK)
    assert res.json()["steps"][0]["response"]["status"] == 200
    (rec,) = servers.tls_valid.find(token)
    assert rec.header("Host") == f"{certs_mod.IDN_ALABEL}:{port}"


def test_idn_url_with_alabel_resolve(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    port = servers.port(servers.tls_valid)
    url = f"https://{certs_mod.IDN_ULABEL}:{port}/ok"
    run(
        [
            "--metrics-only",
            "--cacert",
            str(certs.ca),
            "--resolve",
            f"{certs_mod.IDN_ALABEL}:{port}:{servers.config.target_ip}",
            url,
        ]
    ).expect(EXIT_OK)


def test_alabel_url_with_unicode_resolve(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    port = servers.port(servers.tls_valid)
    url = f"https://{certs_mod.IDN_ALABEL}:{port}/ok"
    run(
        [
            "--metrics-only",
            "--cacert",
            str(certs.ca),
            "--resolve",
            f"{certs_mod.IDN_ULABEL}:{port}:{servers.config.target_ip}",
            url,
        ]
    ).expect(EXIT_OK)


def test_alabel_url_with_alabel_resolve(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    port = servers.port(servers.tls_valid)
    url = f"https://{certs_mod.IDN_ALABEL}:{port}/ok"
    run(
        [
            "--metrics-only",
            "--cacert",
            str(certs.ca),
            "--resolve",
            f"{certs_mod.IDN_ALABEL}:{port}:{servers.config.target_ip}",
            url,
        ]
    ).expect(EXIT_OK)


def test_resolve_is_case_insensitive(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    port = servers.port(servers.tls_valid)
    run(
        [
            "--metrics-only",
            "--cacert",
            str(certs.ca),
            "--resolve",
            f"E2E.Test:{port}:{servers.config.target_ip}",
            f"https://e2e.TEST:{port}/ok",
        ]
    ).expect(EXIT_OK)
