from __future__ import annotations

import argparse
import json
import signal
import socket
import sys
from argparse import Namespace
from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, cast

import certifi
import pytest

from httptap.analyzer import HTTPTapAnalyzer
from httptap.cli import (
    EXIT_EXPORT_ERROR,
    EXIT_FATAL_ERROR,
    EXIT_HTTP_FAILURE,
    EXIT_NETWORK_ERROR,
    EXIT_SLO_VIOLATION,
    EXIT_SUCCESS,
    EXIT_TOO_MANY_REDIRECTS,
    EXIT_USAGE_ERROR,
    _configure_output_encoding,
    _export_results,
    _merge_headers,
    _parse_headers,
    _parse_http_method,
    _parse_resolve_entries,
    _warn_redirect_limit,
    create_parser,
    determine_exit_code,
    main,
    setup_signal_handlers,
    validate_arguments,
)
from httptap.constants import REDIRECT_LIMIT_NOTE, UNIX_SIGNAL_EXIT_OFFSET, HTTPMethod
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.otlp import OTLPDependencyError, OTLPExportError
from httptap.request_executor import RequestOptions, RequestOutcome
from httptap.slo import SLOResult, SLOViolation

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import TracebackType

    from httptap.render import OutputRenderer


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([], {}),
        (["Accept: application/json"], {"Accept": "application/json"}),
        (
            ["Authorization: Bearer abc", "X-Trace: 123"],
            {"Authorization": "Bearer abc", "X-Trace": "123"},
        ),
        (
            ["Authorization: Bearer abc", "authorization: Bearer def"],
            {"Authorization": "Bearer def"},
        ),
    ],
)
def test_parse_headers_valid(raw: list[str], expected: dict[str, str]) -> None:
    parsed = _parse_headers(raw)
    assert parsed == expected


@pytest.mark.parametrize(
    "raw",
    [
        ["Authorization"],
        [":value"],
        ["Header value"],
        [""],
    ],
)
def test_parse_headers_invalid(raw: list[str]) -> None:
    with pytest.raises(
        ValueError,
        match=r"(header format|Header name cannot be empty)",
    ):
        _parse_headers(raw)


def test_curl_flag_aliases_are_supported() -> None:
    parser = create_parser()
    args = parser.parse_args(
        [
            "-X",
            "POST",
            "-L",
            "-m",
            "5",
            "-k",
            "-x",
            "http://proxy.local:8080",
            "--http1.1",
            "https://example.test",
        ],
    )

    assert args.method == HTTPMethod.POST
    assert args.follow is True
    assert args.timeout == 5
    assert args.ignore_ssl is True
    assert args.proxy == "http://proxy.local:8080"
    assert args.no_http2 is True


def test_cli_parser_supports_address_options() -> None:
    parser = create_parser()
    args = parser.parse_args(["-4", "--resolve", "example.test:443:203.0.113.10", "https://example.test"])

    assert args.address_family is not None
    assert args.resolve == ["example.test:443:203.0.113.10"]


@pytest.mark.parametrize(
    "value",
    [
        "example.test",
        "example.test:not-a-port:203.0.113.10",
        "example.test:0:203.0.113.10",
        "example.test:443:not-an-address",
        "example.test:443:[[203.0.113.10]]",
        "example.test: 443:203.0.113.10",
    ],
)
def test_parse_resolve_entries_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid --resolve"):
        _parse_resolve_entries([value], None)


def test_parse_resolve_entries_accepts_bracketed_ipv6() -> None:
    entries = _parse_resolve_entries(["example.test:443:[2001:db8::10]"], None)

    assert entries == {("example.test", 443): "2001:db8::10"}


def test_parse_resolve_entries_rejects_conflicting_address_family() -> None:
    parser = create_parser()
    args = parser.parse_args(["-4", "https://example.test"])

    with pytest.raises(ValueError, match="does not match"):
        _parse_resolve_entries(["example.test:443:2001:db8::10"], args.address_family)


def test_parser_rejects_ipv4_and_ipv6_together() -> None:
    parser = create_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["-4", "-6", "https://example.test"])

    assert exc_info.value.code == EXIT_USAGE_ERROR


def test_validate_arguments_rejects_invalid_resolve(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        ca_bundle=None,
        slo=None,
        resolve=["example.test:443:not-an-address"],
        address_family=None,
        proxy=None,
    )

    assert validate_arguments(args) is False
    assert "Invalid --resolve address" in capsys.readouterr().err


@pytest.mark.parametrize("proxy", ["http://proxy.test:8080", "socks5h://proxy.test:1080"])
def test_validate_arguments_rejects_address_family_with_remote_dns_proxy(
    proxy: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        ca_bundle=None,
        slo=None,
        resolve=[],
        address_family=socket.AF_INET,
        proxy=proxy,
    )

    assert validate_arguments(args) is False
    assert "cannot be used with a proxy" in capsys.readouterr().err


def test_validate_arguments_rejects_resolve_with_remote_dns_proxy(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        ca_bundle=None,
        slo=None,
        resolve=["example.test:443:203.0.113.10"],
        address_family=None,
        proxy="http://proxy.test:8080",
    )

    assert validate_arguments(args) is False
    assert "cannot be used with a proxy" in capsys.readouterr().err


def test_parse_resolve_entries_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="Duplicate --resolve entry"):
        _parse_resolve_entries(["example.test:443:203.0.113.10", "EXAMPLE.test:443:203.0.113.11"], None)


def test_validate_arguments_rejects_address_family_with_env_proxy(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.test:8443")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        ca_bundle=None,
        slo=None,
        resolve=[],
        address_family=socket.AF_INET,
        proxy=None,
    )

    assert validate_arguments(args) is False
    assert "cannot be used with a proxy" in capsys.readouterr().err


def test_configure_output_encoding_replaces_unencodable_characters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = TextIOWrapper(BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "stderr", output)

    _configure_output_encoding()
    output.write("🔍")
    output.flush()

    assert output.buffer.getvalue() == b"?"


def test_configure_output_encoding_skips_streams_without_reconfigure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "stderr", output)

    _configure_output_encoding()
    output.write("🔍")

    assert output.getvalue() == "🔍"


def test_help_hides_none_and_false_defaults() -> None:
    help_text = create_parser().format_help()

    assert "(default: None)" not in help_text
    assert "(default: False)" not in help_text
    assert "(default: 20.0)" in help_text


def test_request_method_is_case_insensitive() -> None:
    assert _parse_http_method("post") is HTTPMethod.POST


def test_request_method_error_lists_valid_methods() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS"):
        _parse_http_method("trace")


class AnalyzerStub:
    def __init__(self) -> None:
        self.calls: list[Mapping[str, str] | None] = []

    def analyze_url(
        self,
        url: str,
        *,
        method: str = "GET",
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> list[StepMetrics]:
        del method
        del content
        self.calls.append(headers)
        timing = TimingMetrics(total_ms=10.0)
        network = NetworkInfo(ip="203.0.113.1")
        response = ResponseInfo(status=200)
        return [StepMetrics(url=url, timing=timing, network=network, response=response)]


class RendererStub:
    def __init__(self) -> None:
        self.rendered: list[tuple[list[StepMetrics], str]] = []

    def render_analysis(
        self,
        steps: list[StepMetrics],
        initial_url: str,
        slo_result: object | None = None,
    ) -> None:
        del slo_result
        self.rendered.append((steps, initial_url))

    def export_json(
        self,
        _steps: list[StepMetrics],
        _initial_url: str,
        _path: str,
        *,
        slo_result: object | None = None,
    ) -> None:
        """Accept the export without writing a file."""


def test_main_success(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = AnalyzerStub()
    captured_ctor: dict[str, Any] = {}
    renderer = RendererStub()

    def fake_analyzer(*_args: object, **kwargs: object) -> AnalyzerStub:
        captured_ctor["params"] = kwargs
        return analyzer

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", fake_analyzer)
    monkeypatch.setattr(
        "httptap.cli.OutputRenderer",
        lambda *_args, **_kwargs: renderer,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "httptap",
            "https://example.test",
            "-H",
            "X: 1",
            "--proxy",
            "socks5h://proxy.local:1080",
        ],
    )

    exit_code = main()

    assert exit_code == EXIT_SUCCESS
    assert analyzer.calls == [{"X": "1"}]
    assert renderer.rendered[0][1] == "https://example.test"
    assert captured_ctor["params"]["proxy"] == "socks5h://proxy.local:1080"


def test_main_passes_configured_dns_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = AnalyzerStub()
    captured_ctor: dict[str, Any] = {}
    renderer = RendererStub()

    def fake_analyzer(*_args: object, **kwargs: object) -> AnalyzerStub:
        captured_ctor.update(kwargs)
        return analyzer

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", fake_analyzer)
    monkeypatch.setattr("httptap.cli.OutputRenderer", lambda *_args, **_kwargs: renderer)
    monkeypatch.setattr(
        "sys.argv",
        [
            "httptap",
            "-6",
            "--resolve",
            "example.test:443:2001:db8::10",
            "https://example.test",
        ],
    )

    assert main() == EXIT_SUCCESS
    resolver = captured_ctor["dns_resolver"]
    assert resolver is not None
    assert resolver.resolve("example.test", 443, 5.0)[:2] == ("2001:db8::10", "IPv6")


def test_main_header_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.argv", ["httptap", "-H", ":bad", "https://example.test"])
    exit_code = main()
    captured = capsys.readouterr()
    assert exit_code == EXIT_USAGE_ERROR
    assert "Header name cannot be empty" in captured.err


def test_cli_version(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """--version prints version information and exits cleanly."""

    monkeypatch.setattr("sys.argv", ["httptap", "--version"])

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 0
    stdout = capsys.readouterr().out
    assert stdout.startswith("httptap ")


def _make_step(
    *,
    url: str = "https://example.test",
    status: int = 200,
    total_ms: float = 120.0,
    error: str | None = None,
) -> StepMetrics:
    timing = TimingMetrics(
        dns_ms=12.0,
        connect_ms=20.0,
        tls_ms=30.0,
        ttfb_ms=70.0,
        total_ms=total_ms,
    )
    timing.calculate_derived()
    network = NetworkInfo(
        ip="203.0.113.42",
        ip_family="IPv4",
        tls_version="TLSv1.3",
        tls_cipher="TLS_AES_128_GCM_SHA256",
        cert_cn="example.test",
        cert_days_left=365,
    )
    response = ResponseInfo(
        status=status,
        bytes=512,
        content_type="application/json",
        server="mock",
    )
    return StepMetrics(
        url=url,
        step_number=1,
        timing=timing,
        network=network,
        response=response,
        error=error,
    )


def test_export_results_handles_oserror(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FailingRenderer(RendererStub):
        def export_json(self, *_args: object, **_kwargs: object) -> None:
            message = "disk full"
            raise OSError(message)

    renderer = FailingRenderer()
    steps = [_make_step()]
    args = Namespace(url="https://example.test", json="out.json")

    assert _export_results(cast("OutputRenderer", renderer), steps, args) is False

    captured = capsys.readouterr()
    assert "Failed to export JSON" in captured.err


def test_export_results_warns_about_otlp_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """OTLP delivery failures do not hide the rendered request result."""

    def raise_export_error(*_args: object, **_kwargs: object) -> None:
        message = "collector unavailable"
        raise OTLPExportError(message)

    monkeypatch.setattr("httptap.cli.OTLPExporter.export", raise_export_error)
    args = Namespace(
        url="https://example.test",
        json=None,
        prometheus=None,
        otlp="http://collector.test/v1/traces",
        timeout=5.0,
    )

    _export_results(cast("OutputRenderer", RendererStub()), [_make_step()], args)

    assert "Failed to export OTLP traces" in capsys.readouterr().err


def test_export_results_warns_about_prometheus_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_os_error(*_args: object, **_kwargs: object) -> None:
        message = "permission denied"
        raise OSError(message)

    monkeypatch.setattr("httptap.cli.PrometheusExporter.export", raise_os_error)
    args = Namespace(url="https://example.test", json=None, prometheus="/root/httptap.prom", otlp=None)

    _export_results(cast("OutputRenderer", RendererStub()), [_make_step()], args)

    assert "Failed to export Prometheus metrics: permission denied" in capsys.readouterr().err


def test_main_returns_error_when_json_export_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingRenderer(RendererStub):
        def export_json(self, *_args: object, **_kwargs: object) -> None:
            message = "disk full"
            raise OSError(message)

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", lambda *_args, **_kwargs: AnalyzerStub())
    monkeypatch.setattr("httptap.cli.OutputRenderer", lambda *_args, **_kwargs: FailingRenderer())
    monkeypatch.setattr("sys.argv", ["httptap", "--json", "out.json", "https://example.test"])

    assert main() == EXIT_EXPORT_ERROR


class _SingleStepExecutor:
    def execute(self, options: RequestOptions) -> RequestOutcome:
        del options
        return RequestOutcome(
            timing=TimingMetrics(total_ms=10.0),
            network=NetworkInfo(ip="203.0.113.1"),
            response=ResponseInfo(status=200),
        )


@pytest.mark.parametrize("mode_args", [["--compact"], ["--metrics-only"], ["--json", "-"], []])
def test_main_never_prints_url_password(
    mode_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def build_analyzer(*_args: object, **_kwargs: object) -> HTTPTapAnalyzer:
        return HTTPTapAnalyzer(request_executor=_SingleStepExecutor())

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", build_analyzer)
    monkeypatch.setattr("sys.argv", ["httptap", *mode_args, "https://user:s3cret@example.test/"])

    assert main() == EXIT_SUCCESS

    captured = capsys.readouterr()
    assert "s3cret" not in captured.out + captured.err


@pytest.mark.parametrize("mode_args", [["--metrics-only"], []], ids=["metrics-only", "rich"])
def test_main_json_dash_writes_only_json_to_stdout(
    mode_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", lambda *_args, **_kwargs: AnalyzerStub())
    monkeypatch.setattr("sys.argv", ["httptap", *mode_args, "--json", "-", "https://example.test"])

    assert main() == EXIT_SUCCESS

    stdout = capsys.readouterr().out
    assert stdout.startswith("{")
    assert json.loads(stdout)["initial_url"] == "https://example.test"
    assert not (tmp_path / "-").exists()


@pytest.mark.parametrize(
    "url",
    ["invalid", "ftp://example.com"],
)
def test_validate_arguments_invalid_url(
    url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = Namespace(url=url, timeout=5, headers=[], json=None)
    result = validate_arguments(args)
    assert result is False
    captured = capsys.readouterr()
    assert "Invalid URL" in captured.err


@pytest.mark.parametrize("timeout", [0, float("nan"), float("inf"), float("-inf")])
def test_validate_arguments_invalid_timeout(
    timeout: float,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = Namespace(url="https://example.test", timeout=timeout, headers=[], json=None)
    result = validate_arguments(args)
    assert result is False
    captured = capsys.readouterr()
    assert "Invalid timeout" in captured.err


def test_validate_arguments_cacert_valid_path(tmp_path: Path) -> None:
    """Test that an existing CA bundle path is normalized to an absolute path."""
    ca_bundle = tmp_path / "ca-bundle.pem"
    ca_bundle.write_text(Path(certifi.where()).read_text(encoding="ascii"), encoding="ascii")

    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle=str(ca_bundle),
        proxy=None,
        slo=None,
    )
    result = validate_arguments(args)

    assert result is True
    assert args.ca_bundle == str(ca_bundle.absolute())


def test_validate_arguments_cacert_empty_string(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that empty CA bundle string fails validation."""
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle="   ",  # Empty/whitespace only
        slo=None,
    )

    result = validate_arguments(args)
    assert result is False


def test_validate_arguments_cacert_relative_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a relative CA bundle path is normalized to an absolute path."""
    ca_bundle = tmp_path / "ca-bundle.pem"
    ca_bundle.write_text(Path(certifi.where()).read_text(encoding="ascii"), encoding="ascii")
    monkeypatch.chdir(tmp_path)
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle=ca_bundle.name,
        proxy=None,
        slo=None,
    )
    result = validate_arguments(args)

    assert result is True
    assert Path(args.ca_bundle).is_absolute()


def test_validate_arguments_rejects_missing_cacert(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle="missing-ca-bundle.pem",
        proxy=None,
        slo=None,
    )

    assert validate_arguments(args) is False
    assert "CA bundle file does not exist" in capsys.readouterr().err


def test_validate_arguments_rejects_invalid_cacert_contents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ca_bundle = tmp_path / "ca-bundle.pem"
    ca_bundle.write_text("not a certificate\n", encoding="ascii")
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle=str(ca_bundle),
        proxy=None,
        slo=None,
    )

    assert validate_arguments(args) is False
    assert "Failed to load CA bundle" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("proxy", "expected"),
    [
        ("proxy.example.com:8080", "http://proxy.example.com:8080"),
        ("user:pw@127.0.0.1:3128", "http://user:pw@127.0.0.1:3128"),
        ("socks5h://gateway:1080", "socks5h://gateway:1080"),
    ],
)
def test_validate_arguments_defaults_scheme_less_proxy_to_http(proxy: str, expected: str) -> None:
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle=None,
        proxy=proxy,
        slo=None,
    )

    assert validate_arguments(args) is True
    assert args.proxy == expected


@pytest.mark.parametrize("proxy", ["foo://bar", "ftp://proxy.example.com:21"])
def test_validate_arguments_rejects_invalid_proxy_scheme(
    proxy: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle=None,
        proxy=proxy,
        slo=None,
    )

    assert validate_arguments(args) is False
    assert "Proxy URL must use" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("proxy", "reason"),
    [
        ("http://user:s3cret@[::1", "Invalid IPv6 URL"),
        ("http://user:s3cret@127.0.0.1:99999", "Port out of range"),
        ("http://user:s3cret@127.0.0.1:0", "port must be between 1 and 65535"),
        ("user:s3cret@127.0.0.1:abc", "Port could not be cast"),
        ("socks5://user:s3cret@:1080", "missing host"),
    ],
)
def test_validate_arguments_rejects_malformed_proxy_url(
    proxy: str,
    reason: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle=None,
        proxy=proxy,
        slo=None,
    )

    assert validate_arguments(args) is False
    err = capsys.readouterr().err
    assert "Invalid proxy URL" in err
    assert reason in err
    assert "user:****@" in err
    assert "s3cret" not in err


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (["--cacert", "missing-ca-bundle.pem", "https://example.test"], "CA bundle file does not exist"),
        (["--proxy", "foo://bar", "https://example.test"], "Proxy URL must use"),
        (["--proxy", "http://[::1", "https://example.test"], "Invalid proxy URL"),
        (["--proxy", "http://127.0.0.1:99999", "https://example.test"], "Invalid proxy URL"),
        (["--timeout", "nan", "https://example.test"], "Invalid timeout"),
    ],
)
def test_main_returns_usage_error_for_invalid_runtime_arguments(
    argv: list[str],
    error: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["httptap", *argv])

    assert main() == EXIT_USAGE_ERROR
    assert error in capsys.readouterr().err


def test_parser_insecure_and_cacert_mutually_exclusive(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that --insecure and --cacert cannot be used together (enforced by argparse)."""
    ca_bundle = tmp_path / "ca-bundle.pem"
    ca_bundle.write_text(Path(certifi.where()).read_text(encoding="ascii"), encoding="ascii")

    parser = create_parser()

    # argparse will call sys.exit() when mutually exclusive args are provided
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["-k", "--cacert", str(ca_bundle), "https://example.test"])

    # Should exit with usage error code
    assert exc_info.value.code == EXIT_USAGE_ERROR

    # Check error output
    captured = capsys.readouterr()
    assert "mutually exclusive" in captured.err or "not allowed with argument" in captured.err


def test_cli_parser_accepts_cacert_argument() -> None:
    """Test that parser accepts --cacert argument."""
    parser = create_parser()
    args = parser.parse_args(["--cacert", "/path/to/ca.pem", "https://example.test"])

    assert args.ca_bundle == "/path/to/ca.pem"


def test_cli_parser_accepts_ca_bundle_alias() -> None:
    """Test that parser accepts --ca-bundle as alias."""
    parser = create_parser()
    args = parser.parse_args(["--ca-bundle", "/path/to/ca.pem", "https://example.test"])

    assert args.ca_bundle == "/path/to/ca.pem"


def test_cli_parser_accepts_export_options() -> None:
    """Prometheus and OTLP output options accept their destination values."""
    parser = create_parser()
    args = parser.parse_args(
        [
            "--prometheus",
            "metrics.prom",
            "--otlp",
            "http://collector.test:4318/v1/traces",
            "https://example.test",
        ]
    )

    assert args.prometheus == "metrics.prom"
    assert args.otlp == "http://collector.test:4318/v1/traces"


def test_validate_arguments_rejects_invalid_otlp_endpoint(capsys: pytest.CaptureFixture[str]) -> None:
    """OTLP requires an absolute HTTP endpoint before a request is made."""
    args = Namespace(
        proxy=None,
        url="https://example.test",
        timeout=5,
        headers=[],
        ca_bundle=None,
        slo=None,
        prometheus=None,
        otlp="collector.test:4318",
    )

    assert validate_arguments(args) is False
    assert "OTLP endpoint must be" in capsys.readouterr().err


def test_validate_arguments_rejects_empty_prometheus_path(capsys: pytest.CaptureFixture[str]) -> None:
    """An empty Prometheus destination is a usage error."""
    args = Namespace(
        proxy=None,
        url="https://example.test",
        timeout=5,
        headers=[],
        ca_bundle=None,
        slo=None,
        prometheus="",
        otlp=None,
    )

    assert validate_arguments(args) is False
    assert "Prometheus export path cannot be empty." in capsys.readouterr().err


def test_validate_arguments_requires_otel_extra(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """OTLP does not start a request when its optional dependency is absent."""
    args = Namespace(
        proxy=None,
        url="https://example.test",
        timeout=5,
        headers=[],
        ca_bundle=None,
        slo=None,
        prometheus=None,
        otlp="http://collector.test:4318/v1/traces",
    )

    def raise_dependency_error() -> None:
        message = "Install httptap[otel]."
        raise OTLPDependencyError(message)

    monkeypatch.setattr("httptap.cli.ensure_otel_available", raise_dependency_error)

    assert validate_arguments(args) is False
    assert "Install httptap[otel]." in capsys.readouterr().err


class DummyProgress:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        self.updated = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> Literal[False]:
        return False

    def add_task(self, *args: object, **kwargs: object) -> int:
        self.task_args = args
        self.task_kwargs = kwargs
        return 1

    def update(self, *_args: object, **_kwargs: object) -> None:
        self.updated = True


def test_cli_integration_full_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    steps = [_make_step()]
    analyzer_calls: list[Mapping[str, str] | None] = []

    class FakeAnalyzer:
        def analyze_url(
            self,
            url: str,
            *,
            method: str = "GET",
            content: bytes | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> list[StepMetrics]:
            del method
            del content
            analyzer_calls.append(headers)
            assert url == "https://example.test"
            return steps

    registered_signals: dict[int, Callable[[int, object | None], None]] = {}

    def fake_signal(signum: int, handler: Callable[[int, object | None], None]) -> None:
        registered_signals[signum] = handler

    json_path = tmp_path / "reports" / "tap.json"
    prometheus_path = tmp_path / "reports" / "tap.prom"

    def build_analyzer(*_args: object, **_kwargs: object) -> FakeAnalyzer:
        return FakeAnalyzer()

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", build_analyzer)
    monkeypatch.setattr("httptap.cli.Progress", DummyProgress)
    monkeypatch.setattr("httptap.cli.signal.signal", fake_signal)
    monkeypatch.setattr(
        "sys.argv",
        [
            "httptap",
            "--json",
            str(json_path),
            "--prometheus",
            str(prometheus_path),
            "-H",
            "X-Debug: 1",
            "https://example.test",
        ],
    )

    exit_code = main()

    stdout, stderr = capsys.readouterr()

    assert exit_code == EXIT_SUCCESS
    assert analyzer_calls == [{"X-Debug": "1"}]
    assert json_path.exists()
    assert prometheus_path.exists()
    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["initial_url"] == "https://example.test"
    assert "httptap_request_duration_seconds" in prometheus_path.read_text(encoding="utf-8")
    assert signal.SIGINT in registered_signals
    assert "Analyzing" in stdout
    assert "Exported analysis" not in stdout
    assert "Exported Prometheus metrics" not in stdout
    assert "Exported analysis" in stderr
    assert "Exported Prometheus metrics" in stderr

    assert "Exported analysis" not in stdout
    assert "Exported analysis" in stderr


def test_cli_compact_ignored_when_metrics_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--metrics-only wins over --compact and warns on stderr."""
    step = _make_step()

    class FakeAnalyzer:
        def analyze_url(
            self,
            url: str,
            *,
            method: str = "GET",
            content: bytes | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> list[StepMetrics]:
            del method
            del content
            del headers
            assert url == "https://example.test"
            return [step]

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", lambda *_a, **_k: FakeAnalyzer())
    monkeypatch.setattr("httptap.cli.Progress", DummyProgress)
    monkeypatch.setattr("httptap.cli.signal.signal", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--compact", "--metrics-only", "https://example.test"],
    )

    exit_code = main()
    stdout, stderr = capsys.readouterr()

    assert exit_code == EXIT_SUCCESS
    assert "dns=" in stdout
    assert "status=" in stdout
    assert "Warning" in stderr
    assert "--compact is ignored" in stderr
    assert "--metrics-only takes precedence" in stderr


def test_cli_integration_metrics_only_error_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    error_step = _make_step(error="simulated failure")

    class FakeAnalyzer:
        def analyze_url(
            self,
            url: str,
            *,
            method: str = "GET",
            content: bytes | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> list[StepMetrics]:
            del method
            del content
            assert headers == {}
            assert url == "https://example.test"
            return [error_step]

    def build_analyzer(*_args: object, **_kwargs: object) -> FakeAnalyzer:
        return FakeAnalyzer()

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", build_analyzer)
    monkeypatch.setattr("httptap.cli.Progress", DummyProgress)

    def noop_signal(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("httptap.cli.signal.signal", noop_signal)
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--metrics-only", "https://example.test"],
    )

    exit_code = main()
    stdout, stderr = capsys.readouterr()

    assert exit_code == EXIT_NETWORK_ERROR
    assert "Step 1: ERROR - simulated failure" in stdout
    assert stderr == ""


def test_main_handles_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "httptap.cli._execute_analysis",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr("sys.argv", ["httptap", "https://example.test"])

    exit_code = main()

    assert exit_code == UNIX_SIGNAL_EXIT_OFFSET + signal.SIGINT


def test_main_handles_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "httptap.cli._execute_analysis",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr("sys.argv", ["httptap", "https://example.test"])

    exit_code = main()
    stdout, stderr = capsys.readouterr()

    assert exit_code == EXIT_FATAL_ERROR
    assert "Internal Error" in stderr
    assert stdout == ""


def test_main_escapes_markup_in_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "httptap.cli._execute_analysis",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("closing tag [/dim] mismatch")),
    )
    monkeypatch.setattr("sys.argv", ["httptap", "https://example.test"])

    exit_code = main()
    _, stderr = capsys.readouterr()

    assert exit_code == EXIT_FATAL_ERROR
    assert "[/dim]" in stderr


def test_main_handles_data_read_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """File read failures for --data should surface as usage errors."""

    def fake_read_request_data(_path: str) -> tuple[bytes | None, dict[str, str]]:
        message = "missing payload"
        raise FileNotFoundError(message)

    monkeypatch.setattr("httptap.cli.read_request_data", fake_read_request_data)
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--data", "@missing", "https://example.test"],
    )

    exit_code = main()
    _stdout, stderr = capsys.readouterr()

    assert exit_code == EXIT_USAGE_ERROR
    assert "Error reading data" in stderr


def test_determine_exit_code_empty_steps() -> None:
    assert determine_exit_code([]) == EXIT_FATAL_ERROR


def test_determine_exit_code_error_without_partial_data_is_network_error() -> None:
    step = StepMetrics(
        url="https://invalid.test",
        error="DNS resolution failed",
        error_kind="network",
    )

    assert determine_exit_code([step]) == EXIT_NETWORK_ERROR


def test_determine_exit_code_internal_error_is_fatal() -> None:
    step = StepMetrics(
        url="https://example.test",
        error="Unexpected failure",
        error_kind="internal",
    )

    assert determine_exit_code([step]) == EXIT_FATAL_ERROR


def test_determine_exit_code_redirect_limit_exceeded() -> None:
    step = StepMetrics(
        url="https://example.test/redirect",
        response=ResponseInfo(status=302),
        note=f"{REDIRECT_LIMIT_NOTE} (10)",
        redirect_limit_reached=True,
    )

    assert determine_exit_code([step]) == EXIT_TOO_MANY_REDIRECTS


def test_warn_redirect_limit(capsys: pytest.CaptureFixture[str]) -> None:
    step = StepMetrics(note=f"{REDIRECT_LIMIT_NOTE} (10)", redirect_limit_reached=True)

    _warn_redirect_limit([step])

    stderr = capsys.readouterr().err
    assert "Warning:" in stderr
    assert "Maximum redirects followed (10)" in stderr


def test_setup_signal_handlers_invokes_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    handlers: dict[int, Callable[[int, object | None], None]] = {}

    def fake_signal(signum: int, handler: Callable[[int, object | None], None]) -> None:
        handlers[signum] = handler

    monkeypatch.setattr("httptap.cli.signal.signal", fake_signal)
    monkeypatch.setattr(
        "httptap.cli.console.print",
        lambda message: captured.append(str(message)),
    )

    setup_signal_handlers()
    handler = handlers[signal.SIGINT]

    with pytest.raises(SystemExit) as excinfo:
        handler(signal.SIGINT, None)

    assert excinfo.value.code == UNIX_SIGNAL_EXIT_OFFSET + signal.SIGINT
    assert any("Interrupted by user" in msg for msg in captured)


def test_auto_post_when_data_provided_without_explicit_method(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that --data auto-switches to POST when --method is not specified."""
    from httptap.constants import HTTPMethod

    captured_method: list[HTTPMethod] = []

    class FakeAnalyzer:
        def analyze_url(
            self,
            url: str,
            *,
            method: HTTPMethod = HTTPMethod.GET,
            content: bytes | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> list[StepMetrics]:
            del url, content, headers
            captured_method.append(method)
            return [_make_step()]

    def build_analyzer(*_args: object, **_kwargs: object) -> FakeAnalyzer:
        return FakeAnalyzer()

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", build_analyzer)
    monkeypatch.setattr("httptap.cli.Progress", DummyProgress)

    def noop_signal(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("httptap.cli.signal.signal", noop_signal)

    # Create test data file
    data_file = tmp_path / "data.json"
    data_file.write_text('{"test": "data"}')

    # Run without --method (should auto-switch to POST)
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "https://example.test", "--data", f"@{data_file}"],
    )

    exit_code = main()
    assert exit_code == EXIT_SUCCESS
    assert len(captured_method) == 1
    assert captured_method[0] == HTTPMethod.POST


def test_no_auto_post_when_method_explicitly_specified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that explicit --method GET with --data respects user choice and warns."""
    from httptap.constants import HTTPMethod

    captured_method: list[HTTPMethod] = []

    class FakeAnalyzer:
        def analyze_url(
            self,
            url: str,
            *,
            method: HTTPMethod = HTTPMethod.GET,
            content: bytes | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> list[StepMetrics]:
            del url, content, headers
            captured_method.append(method)
            return [_make_step()]

    def build_analyzer(*_args: object, **_kwargs: object) -> FakeAnalyzer:
        return FakeAnalyzer()

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", build_analyzer)
    monkeypatch.setattr("httptap.cli.Progress", DummyProgress)

    def noop_signal(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("httptap.cli.signal.signal", noop_signal)

    # Create test data file
    data_file = tmp_path / "data.json"
    data_file.write_text('{"test": "data"}')

    # Run with explicit --method GET (should NOT auto-switch, should warn)
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "https://example.test", "--method", "GET", "--data", f"@{data_file}"],
    )

    exit_code = main()
    assert exit_code == EXIT_SUCCESS
    assert len(captured_method) == 1
    assert captured_method[0] == HTTPMethod.GET  # Should respect explicit GET


class _SLOAnalyzerStub:
    """Minimal analyzer that returns one step with caller-specified timing."""

    def __init__(self, total_ms: float, *, error: str | None = None, status: int = 200) -> None:
        self._total_ms = total_ms
        self._error = error
        self._status = status

    def analyze_url(
        self,
        url: str,
        *,
        method: HTTPMethod = HTTPMethod.GET,
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> list[StepMetrics]:
        del method, content, headers
        timing = TimingMetrics(
            dns_ms=5.0,
            connect_ms=10.0,
            tls_ms=20.0,
            ttfb_ms=50.0,
            total_ms=self._total_ms,
        )
        timing.calculate_derived()
        network = NetworkInfo(ip="203.0.113.1", ip_family="IPv4")
        response = ResponseInfo(status=self._status, bytes=128)
        return [
            StepMetrics(
                url=url,
                step_number=1,
                timing=timing,
                network=network,
                response=response,
                error=self._error,
            )
        ]


def _install_slo_analyzer_stub(
    monkeypatch: pytest.MonkeyPatch,
    analyzer: _SLOAnalyzerStub,
) -> None:
    monkeypatch.setattr(
        "httptap.cli.HTTPTapAnalyzer",
        lambda *_args, **_kwargs: analyzer,
    )


def test_main_slo_pass_returns_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=120.0))
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--metrics-only", "--slo", "total=500", "https://example.test"],
    )

    exit_code = main()
    stdout = capsys.readouterr().out

    assert exit_code == EXIT_SUCCESS
    assert "slo=pass" in stdout
    assert "slo=fail" not in stdout


def test_main_slo_fail_returns_slo_violation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=900.0))
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--metrics-only", "--slo", "total=500", "https://example.test"],
    )

    exit_code = main()
    stdout = capsys.readouterr().out

    assert exit_code == EXIT_SLO_VIOLATION
    assert "slo=fail" in stdout
    assert "slo_violations=total" in stdout


def test_main_slo_multiple_violations_are_comma_joined(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=900.0))
    monkeypatch.setattr(
        "sys.argv",
        [
            "httptap",
            "--metrics-only",
            "--slo",
            "total=500,ttfb=10",
            "https://example.test",
        ],
    )

    exit_code = main()
    stdout = capsys.readouterr().out

    assert exit_code == EXIT_SLO_VIOLATION
    # Violations sorted alphabetically.
    assert "slo_violations=total,ttfb" in stdout


def test_main_slo_invalid_spec_returns_usage_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=100.0))
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--slo", "bogus", "https://example.test"],
    )

    exit_code = main()
    stderr = capsys.readouterr().err

    assert exit_code == EXIT_USAGE_ERROR
    assert "SLO Error" in stderr


def test_main_slo_file_uses_thresholds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    slo_file = tmp_path / "slo.txt"
    slo_file.write_text("total=500\nttfb=200\n", encoding="utf-8")
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=900.0))
    monkeypatch.setattr("sys.argv", ["httptap", "--slo-file", str(slo_file), "https://example.test"])

    assert main() == EXIT_SLO_VIOLATION


def test_main_slo_cli_values_override_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    slo_file = tmp_path / "slo.txt"
    slo_file.write_text("total=500\nttfb=200\n", encoding="utf-8")
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=900.0))
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--slo-file", str(slo_file), "--slo", "total=1000", "https://example.test"],
    )

    assert main() == EXIT_SUCCESS


def test_main_slo_file_missing_returns_usage_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=100.0))
    monkeypatch.setattr("sys.argv", ["httptap", "--slo-file", str(tmp_path / "missing.txt"), "https://example.test"])

    assert main() == EXIT_USAGE_ERROR


def test_main_slo_file_empty_path_returns_usage_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.argv", ["httptap", "--slo-file", "", "https://example.test"])

    exit_code = main()
    stderr = capsys.readouterr().err

    assert exit_code == EXIT_USAGE_ERROR
    assert "SLO file path cannot be empty." in stderr


def test_main_slo_file_invalid_encoding_returns_usage_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    slo_file = tmp_path / "slo.txt"
    slo_file.write_bytes(b"\xff")
    monkeypatch.setattr("sys.argv", ["httptap", "--slo-file", str(slo_file), "https://example.test"])

    exit_code = main()
    stderr = capsys.readouterr().err

    assert exit_code == EXIT_USAGE_ERROR
    assert "Failed to read SLO file" in stderr


def test_main_slo_network_error_beats_slo_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A network failure takes precedence over an SLO failure."""
    analyzer = _SLOAnalyzerStub(total_ms=900.0, error="connection refused")
    _install_slo_analyzer_stub(monkeypatch, analyzer)
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--slo", "total=500", "https://example.test"],
    )

    exit_code = main()

    assert exit_code == EXIT_NETWORK_ERROR


@pytest.mark.parametrize("flag", ["-f", "--fail"])
@pytest.mark.parametrize("status", [400, 500])
def test_main_fail_returns_http_failure_for_error_response(
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    status: int,
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=100.0, status=status))
    monkeypatch.setattr("sys.argv", ["httptap", flag, "https://example.test"])

    assert main() == EXIT_HTTP_FAILURE


def test_main_without_fail_keeps_success_for_error_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=100.0, status=500))
    monkeypatch.setattr("sys.argv", ["httptap", "https://example.test"])

    assert main() == EXIT_SUCCESS


def test_main_fail_keeps_success_below_error_range(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=100.0, status=399))
    monkeypatch.setattr("sys.argv", ["httptap", "--fail", "https://example.test"])

    assert main() == EXIT_SUCCESS


def test_main_fail_renders_metrics_before_http_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=100.0, status=500))
    monkeypatch.setattr("sys.argv", ["httptap", "--metrics-only", "--fail", "https://example.test"])

    assert main() == EXIT_HTTP_FAILURE
    assert "status=500" in capsys.readouterr().out


def test_main_fail_network_error_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=100.0, error="connection refused", status=500))
    monkeypatch.setattr("sys.argv", ["httptap", "--fail", "https://example.test"])

    assert main() == EXIT_NETWORK_ERROR


def test_main_fail_takes_precedence_over_slo(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=900.0, status=500))
    monkeypatch.setattr("sys.argv", ["httptap", "--fail", "--slo", "total=500", "https://example.test"])

    assert main() == EXIT_HTTP_FAILURE


def test_main_slo_json_export_contains_slo_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=900.0))
    output_path = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "httptap",
            "--metrics-only",
            "--slo",
            "total=500",
            "--json",
            str(output_path),
            "https://example.test",
        ],
    )

    exit_code = main()

    assert exit_code == EXIT_SLO_VIOLATION
    payload = json.loads(output_path.read_text())
    slo_block = payload["summary"]["slo"]
    assert slo_block["pass"] is False
    assert slo_block["thresholds_ms"] == {"total": 500.0}
    assert slo_block["violations"] == [
        {
            "key": "total",
            "threshold_ms": 500.0,
            "actual_ms": 900.0,
            "delta_ms": 400.0,
        }
    ]


def test_main_without_slo_flag_has_no_slo_in_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_slo_analyzer_stub(monkeypatch, _SLOAnalyzerStub(total_ms=100.0))
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--metrics-only", "https://example.test"],
    )

    exit_code = main()
    stdout = capsys.readouterr().out

    assert exit_code == EXIT_SUCCESS
    assert "slo=" not in stdout


def test_determine_exit_code_slo_pass_returns_success() -> None:
    step = StepMetrics(
        url="https://example.test",
        timing=TimingMetrics(total_ms=100.0),
        network=NetworkInfo(ip="203.0.113.1"),
        response=ResponseInfo(status=200),
    )
    result = SLOResult(thresholds_ms={"total": 500.0}, violations=())
    assert determine_exit_code([step], slo_result=result) == EXIT_SUCCESS


def test_determine_exit_code_slo_fail_returns_slo_violation() -> None:
    step = StepMetrics(
        url="https://example.test",
        timing=TimingMetrics(total_ms=900.0),
        network=NetworkInfo(ip="203.0.113.1"),
        response=ResponseInfo(status=200),
    )
    violation = SLOViolation(key="total", threshold_ms=500.0, actual_ms=900.0)
    result = SLOResult(thresholds_ms={"total": 500.0}, violations=(violation,))
    assert determine_exit_code([step], slo_result=result) == EXIT_SLO_VIOLATION


def test_determine_exit_code_network_error_overrides_slo() -> None:
    step = StepMetrics(
        url="https://example.test",
        timing=TimingMetrics(total_ms=900.0),
        network=NetworkInfo(ip="203.0.113.1"),
        response=ResponseInfo(status=None),
        error="connection refused",
    )
    violation = SLOViolation(key="total", threshold_ms=500.0, actual_ms=900.0)
    result = SLOResult(thresholds_ms={"total": 500.0}, violations=(violation,))
    assert determine_exit_code([step], slo_result=result) == EXIT_NETWORK_ERROR


def test_main_rejects_out_of_range_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["httptap", "http://127.0.0.1:99999/"])

    assert main() == EXIT_USAGE_ERROR


@pytest.mark.parametrize(
    ("step", "fail_on_http_error", "expected"),
    [
        (StepMetrics(error="boom", error_kind="internal"), False, EXIT_FATAL_ERROR),
        (StepMetrics(response=ResponseInfo(status=302), redirect_limit_reached=True), False, EXIT_TOO_MANY_REDIRECTS),
        (StepMetrics(error="refused", error_kind="network"), False, EXIT_NETWORK_ERROR),
        (StepMetrics(response=ResponseInfo(status=500)), True, EXIT_EXPORT_ERROR),
        (StepMetrics(response=ResponseInfo(status=200)), False, EXIT_EXPORT_ERROR),
    ],
    ids=["internal-wins", "redirect-limit-wins", "network-wins", "export-beats-fail", "export-alone"],
)
def test_determine_exit_code_ranks_export_failure(
    step: StepMetrics,
    *,
    fail_on_http_error: bool,
    expected: int,
) -> None:
    assert determine_exit_code([step], fail_on_http_error=fail_on_http_error, export_failed=True) == expected


def test_merge_headers_lets_user_header_replace_default_case_insensitively() -> None:
    merged = _merge_headers({"Content-Type": "application/json"}, {"content-type": "text/plain", "X-Trace": "1"})

    assert merged == {"content-type": "text/plain", "X-Trace": "1"}


def test_main_exports_single_content_type_when_user_overrides_it(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def build_analyzer(*_args: object, **_kwargs: object) -> HTTPTapAnalyzer:
        return HTTPTapAnalyzer(request_executor=_SingleStepExecutor())

    monkeypatch.setattr("httptap.cli.HTTPTapAnalyzer", build_analyzer)
    monkeypatch.setattr(
        "sys.argv",
        ["httptap", "--json", "-", "-H", "content-type: text/plain", "--data", '{"a": 1}', "https://example.test/"],
    )

    assert main() == EXIT_SUCCESS

    headers = json.loads(capsys.readouterr().out)["steps"][0]["request"]["headers"]
    assert {name.lower() for name in headers} == {"content-type"}
    assert next(iter(headers.values())) == "text/plain"


def test_main_rejects_empty_json_path(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["httptap", "--json", "", "https://example.test/"])

    assert main() == EXIT_USAGE_ERROR
    assert "JSON export path cannot be empty" in capsys.readouterr().err
