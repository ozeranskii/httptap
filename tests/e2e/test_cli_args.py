"""Argument handling: --help/--version, usage errors (exit 64) and input validation."""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

import pytest

from tests.e2e.harness import EXIT_OK, EXIT_USAGE, RunCommand, Servers, assert_absent

if TYPE_CHECKING:
    from pathlib import Path


def test_version(run: RunCommand) -> None:
    res = run(["--version"]).expect(EXIT_OK)
    assert re.fullmatch(r"httptap \d+\.\d+\.\d+\S*\s*", res.stdout), res.describe()


def test_help_lists_options_and_exit_codes(run: RunCommand) -> None:
    res = run(["--help"]).expect(EXIT_OK)
    for needle in (
        "--follow",
        "--max-time",
        "--proxy",
        "--json",
        "--prometheus",
        "--otlp",
        "--slo",
        "--slo-file",
        "--resolve",
        "--cacert",
        "--metrics-only",
        "--compact",
        "--no-http2",
        "--fail",
    ):
        assert needle in res.stdout, needle
    for code in ("0", "4", "22", "47", "64", "70", "73", "75"):
        assert re.search(rf"^\s*{code}\b", res.stdout, re.MULTILINE), f"exit code {code} not documented"


def test_help_does_not_print_empty_resolve_default(run: RunCommand) -> None:
    res = run(["--help"]).expect(EXIT_OK)
    assert "(default: [])" not in res.stdout


def test_unknown_flag(run: RunCommand, servers: Servers) -> None:
    res = run(["--definitely-not-a-flag", servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "unrecognized arguments" in res.stderr


def test_missing_url(run: RunCommand) -> None:
    res = run([]).expect(EXIT_USAGE)
    assert "url" in res.stderr


@pytest.mark.parametrize(
    "url",
    [
        "ftp://127.0.0.1/",
        "127.0.0.1/ok",
        "http://",
        "https:///path",
        "http://127.0.0.1:99999/",
        "http://127.0.0.1:0/",
        "http://127.0.0.1:abc/",
        "http://[::1/",
        "http://exa mple.com/",
        "",
        "   ",
        "http://127.0.0.1/\nX",
    ],
    ids=[
        "ftp",
        "no-scheme",
        "no-host",
        "empty-host",
        "port-range",
        "port-zero",
        "port-alpha",
        "ipv6-open",
        "space",
        "empty",
        "whitespace",
        "newline",
    ],
)
def test_invalid_url_is_usage_error(run: RunCommand, url: str) -> None:
    res = run([url]).expect(EXIT_USAGE)
    assert "Traceback" not in res.output


@pytest.mark.posix
@pytest.mark.skipif(sys.platform == "win32", reason="argv bytes are POSIX-only")
@pytest.mark.usefixtures("need_raw_argv")
def test_non_utf8_url_bytes(run: RunCommand, servers: Servers) -> None:
    """Raw non-UTF-8 bytes in the URL are either percent-encoded and sent, or rejected as a usage error."""
    url = servers.url(servers.origin, "/").encode() + b"\xff\xfe"
    res = run(["--metrics-only", url])
    assert res.code in (EXIT_OK, EXIT_USAGE), res.describe()


def test_invalid_url_redacts_credentials(run: RunCommand) -> None:
    res = run(["ftp://user:InvalidUrlPw123@127.0.0.1/"]).expect(EXIT_USAGE)
    assert_absent("InvalidUrlPw123", res.stdout, res.stderr)


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "abc"])
def test_invalid_timeout(run: RunCommand, servers: Servers, value: str) -> None:
    run(["-m", value, servers.url(servers.origin)]).expect(EXIT_USAGE)


def test_invalid_method(run: RunCommand, servers: Servers) -> None:
    res = run(["-X", "BREW", servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "invalid HTTP method" in res.stderr


def test_method_is_case_insensitive(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-X", "post", servers.url(servers.origin)]).expect(EXIT_OK)
    assert "status=200" in res.stdout


@pytest.mark.parametrize(
    "args",
    [["-4", "-6"], ["-k", "--cacert", "x.pem"]],
    ids=["ipv4-ipv6", "insecure-cacert"],
)
def test_mutually_exclusive(run: RunCommand, servers: Servers, args: list[str]) -> None:
    res = run([*args, servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "not allowed with" in res.stderr


def test_cacert_missing_file(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    res = run(["--cacert", str(out_dir / "missing.pem"), servers.url(servers.tls_valid)]).expect(EXIT_USAGE)
    assert "does not exist" in res.stderr


def test_cacert_empty_path(run: RunCommand, servers: Servers) -> None:
    run(["--cacert", " ", servers.url(servers.tls_valid)]).expect(EXIT_USAGE)


def test_cacert_not_pem(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    bogus = out_dir / "bogus.pem"
    bogus.write_text("not a certificate\n")
    res = run(["--cacert", str(bogus), servers.url(servers.tls_valid)]).expect(EXIT_USAGE)
    assert "Traceback" not in res.output


@pytest.mark.parametrize(
    "value",
    [
        "e2e.test:80",
        "e2e.test::127.0.0.1",
        ":80:127.0.0.1",
        "e2e.test:99999:127.0.0.1",
        "e2e.test:x:127.0.0.1",
        "e2e.test:80:not-an-ip",
        "e2e.test: 80:127.0.0.1",
    ],
)
def test_resolve_invalid(run: RunCommand, servers: Servers, value: str) -> None:
    res = run(["--resolve", value, servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "resolve" in res.stderr.lower()


def test_resolve_duplicate(run: RunCommand, servers: Servers) -> None:
    run(
        ["--resolve", "e2e.test:80:127.0.0.1", "--resolve", "E2E.test:80:127.0.0.2", servers.url(servers.origin)]
    ).expect(EXIT_USAGE)


def test_resolve_family_mismatch(run: RunCommand, servers: Servers) -> None:
    res = run(["-6", "--resolve", "e2e.test:80:127.0.0.1", "http://e2e.test/"]).expect(EXIT_USAGE)
    assert "does not match" in res.stderr


@pytest.mark.parametrize("proxy", ["http", "https", "socks5h"])
def test_resolve_rejected_with_remote_dns_proxy(run: RunCommand, servers: Servers, proxy: str) -> None:
    res = run(
        [
            "--resolve",
            f"e2e.test:{servers.port(servers.origin)}:127.0.0.1",
            "-x",
            f"{proxy}://127.0.0.1:1",
            f"http://e2e.test:{servers.port(servers.origin)}/ok",
        ]
    ).expect(EXIT_USAGE)
    assert "cannot be used with a proxy" in res.stderr


@pytest.mark.parametrize(
    "header",
    ["NoColon", ": value", "Bad Name: v", "X-Name: тест", "X-A: a\nb", "X-A: a\rb", "X-é: v", "X-Tab\tName: v"],
    ids=["no-colon", "empty-name", "space-in-name", "non-ascii-value", "lf", "cr", "non-ascii-name", "tab-in-name"],
)
def test_invalid_header_is_usage_error(run: RunCommand, servers: Servers, header: str) -> None:
    res = run(["-H", header, servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "Traceback" not in res.output


def test_invalid_header_value_not_echoed(run: RunCommand, servers: Servers) -> None:
    res = run(["-H", "Authorization: Bearer s3crétHeaderValue", servers.url(servers.origin)])
    res.expect(EXIT_USAGE)
    assert_absent("s3crétHeaderValue", res.stdout, res.stderr)


@pytest.mark.parametrize(
    "proxy",
    ["ftp://127.0.0.1:21", "http://[::1", "http://127.0.0.1:99999", "http://127.0.0.1:abc", "http://"],
    ids=["ftp", "ipv6-open", "port-range", "port-alpha", "no-host"],
)
def test_malformed_proxy_is_usage_error(run: RunCommand, servers: Servers, proxy: str) -> None:
    res = run(["-x", proxy, servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "Traceback" not in res.output


def test_malformed_proxy_redacts_credentials(run: RunCommand, servers: Servers) -> None:
    res = run(["-x", "http://u:MalformedProxyPw@[::1", servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert_absent("MalformedProxyPw", res.stdout, res.stderr)


@pytest.mark.parametrize("spec", ["bogus=1", "total", "total=abc", "total=-5", "total=nan", "total=1,,", "=5"])
def test_bad_slo_spec(run: RunCommand, servers: Servers, spec: str) -> None:
    res = run(["--slo", spec, servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "SLO" in res.stderr


def test_slo_file_missing(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    res = run(["--slo-file", str(out_dir / "nope.slo"), servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "SLO" in res.stderr


def test_slo_file_unreadable_directory(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    run(["--slo-file", str(out_dir), servers.url(servers.origin)]).expect(EXIT_USAGE)


def test_slo_file_bad_content(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "bad.slo"
    path.write_text("total=100\nwhat=is_this\n")
    run(["--slo-file", str(path), servers.url(servers.origin)]).expect(EXIT_USAGE)


def test_slo_file_empty_path(run: RunCommand, servers: Servers) -> None:
    run(["--slo-file", "", servers.url(servers.origin)]).expect(EXIT_USAGE)


@pytest.mark.parametrize("flag", ["--json", "--prometheus"])
@pytest.mark.parametrize("value", ["", "  "])
def test_empty_export_path(run: RunCommand, servers: Servers, flag: str, value: str) -> None:
    res = run([flag, value, servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "cannot be empty" in res.stderr


@pytest.mark.parametrize("endpoint", ["", "localhost:4318", "ftp://127.0.0.1/v1/traces", "http://"])
def test_invalid_otlp_endpoint(run: RunCommand, servers: Servers, endpoint: str) -> None:
    res = run(["--otlp", endpoint, servers.url(servers.origin)]).expect(EXIT_USAGE)
    assert "OTLP endpoint" in res.stderr


def test_data_file_missing(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    res = run(["-d", f"@{out_dir / 'missing.json'}", servers.url(servers.origin, "/echo")]).expect(EXIT_USAGE)
    assert "Error reading data" in res.stderr


def test_usage_error_makes_no_request(run: RunCommand, servers: Servers) -> None:
    token = "usage-no-request-token"
    run(["--slo", "bogus=1", servers.url(servers.origin, f"/echo?id={token}")]).expect(EXIT_USAGE)
    assert servers.origin.find(token) == []


def test_compact_with_metrics_only_warns(run: RunCommand, servers: Servers) -> None:
    res = run(["--compact", "--metrics-only", servers.url(servers.origin)]).expect(EXIT_OK)
    assert "--compact is ignored" in res.stderr
    assert res.stdout.startswith("Step 1: ")
