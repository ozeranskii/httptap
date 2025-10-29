from __future__ import annotations

import json
import signal
from argparse import Namespace
from typing import TYPE_CHECKING, Literal, cast

import pytest
from typing_extensions import Self

from httptap.cli import (
    EXIT_FATAL_ERROR,
    EXIT_NETWORK_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    _export_results,
    _parse_headers,
    determine_exit_code,
    main,
    setup_signal_handlers,
    validate_arguments,
)
from httptap.constants import UNIX_SIGNAL_EXIT_OFFSET
from httptap.models import NetworkInfo, ResponseInfo, StepMetrics, TimingMetrics

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


class AnalyzerStub:
    def __init__(self) -> None:
        self.calls: list[Mapping[str, str] | None] = []

    def analyze_url(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[StepMetrics]:
        self.calls.append(headers)
        timing = TimingMetrics(total_ms=10.0)
        network = NetworkInfo(ip="203.0.113.1")
        response = ResponseInfo(status=200)
        return [StepMetrics(url=url, timing=timing, network=network, response=response)]


class RendererStub:
    def __init__(self) -> None:
        self.rendered: list[tuple[list[StepMetrics], str]] = []

    def render_analysis(self, steps: list[StepMetrics], initial_url: str) -> None:
        self.rendered.append((steps, initial_url))

    def export_json(
        self,
        _steps: list[StepMetrics],
        _initial_url: str,
        _path: str,
    ) -> None:
        return None


def test_main_success(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = AnalyzerStub()
    captured_ctor: dict[str, object] = {}
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
    with pytest.raises(ValueError, match="Invalid URL"):
        validate_arguments(args)
    captured = capsys.readouterr()
    assert "Invalid URL" in captured.err


def test_validate_arguments_invalid_timeout(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(url="https://example.test", timeout=0, headers=[], json=None)
    with pytest.raises(ValueError, match="Invalid timeout"):
        validate_arguments(args)
    captured = capsys.readouterr()
    assert "Invalid timeout" in captured.err


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
            headers: Mapping[str, str] | None = None,
        ) -> list[StepMetrics]:
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
            headers: Mapping[str, str] | None = None,
        ) -> list[StepMetrics]:
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
