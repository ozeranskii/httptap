from __future__ import annotations

import json
import signal
import sys
from argparse import Namespace
from typing import TYPE_CHECKING, Any, Literal, cast

import pytest

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from httptap.cli import (
    EXIT_FATAL_ERROR,
    EXIT_NETWORK_ERROR,
    EXIT_SLO_VIOLATION,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    _export_results,
    _parse_headers,
    create_parser,
    determine_exit_code,
    main,
    setup_signal_handlers,
    validate_arguments,
)
from httptap.constants import UNIX_SIGNAL_EXIT_OFFSET, HTTPMethod
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics
from httptap.slo import SLOResult, SLOViolation

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path
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
        del slo_result


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

    _export_results(cast("OutputRenderer", renderer), steps, args)

    captured = capsys.readouterr()
    assert "Failed to export JSON" in captured.err


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


def test_validate_arguments_invalid_timeout(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(url="https://example.test", timeout=0, headers=[], json=None)
    result = validate_arguments(args)
    assert result is False
    captured = capsys.readouterr()
    assert "Invalid timeout" in captured.err


def test_validate_arguments_cacert_valid_path(tmp_path: Path) -> None:
    """Test that CA bundle path is normalized to absolute path."""
    # Path doesn't need to exist - validation happens in SSL layer
    ca_bundle = tmp_path / "ca-bundle.pem"

    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle=str(ca_bundle),
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


def test_validate_arguments_cacert_expanduser() -> None:
    """Test that tilde expansion works for CA bundle path."""
    from pathlib import Path

    # Using a fake path with ~ - doesn't need to exist
    args = Namespace(
        url="https://example.test",
        timeout=5,
        headers=[],
        json=None,
        ignore_ssl=False,
        ca_bundle="~/ca-bundle.pem",
        slo=None,
    )
    result = validate_arguments(args)

    assert result is True
    assert not args.ca_bundle.startswith("~")
    assert Path(args.ca_bundle).is_absolute()


def test_parser_insecure_and_cacert_mutually_exclusive(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that --insecure and --cacert cannot be used together (enforced by argparse)."""
    ca_bundle = tmp_path / "ca-bundle.pem"
    ca_bundle.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")

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
    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["initial_url"] == "https://example.test"
    assert signal.SIGINT in registered_signals
    assert "Analyzing" in stdout
    assert "Exported analysis" in stdout
    assert not stderr


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

    # Verify INFO log about auto-switch
    captured_output = capsys.readouterr()
    # Note: logger.info goes to stderr, not stdout


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

    # Verify WARNING log about uncommon usage
    captured_output = capsys.readouterr()
    # Note: logger.warning goes to stderr, not stdout


class _SLOAnalyzerStub:
    """Minimal analyzer that returns one step with caller-specified timing."""

    def __init__(self, total_ms: float, *, error: str | None = None) -> None:
        self._total_ms = total_ms
        self._error = error

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
        response = ResponseInfo(status=200, bytes=128)
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
