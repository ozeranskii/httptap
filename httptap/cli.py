"""Command-line interface for httptap.

This module provides the CLI entry point and argument parsing for the httptap tool.
Follows CLI best practices for error handling, exit codes, and user feedback.
"""
# PYTHON_ARGCOMPLETE_OK

import argparse
import ipaddress
import logging
import math
import re
import signal
import socket
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from types import ModuleType

from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from . import __version__
from .analyzer import HTTPTapAnalyzer
from .constants import (
    DEFAULT_TIMEOUT_SECONDS,
    EXIT_CODE_CANTCREAT,
    EXIT_CODE_HTTP_FAILURE,
    EXIT_CODE_OK,
    EXIT_CODE_SLO_VIOLATION,
    EXIT_CODE_SOFTWARE,
    EXIT_CODE_TEMPFAIL,
    EXIT_CODE_TOO_MANY_REDIRECTS,
    EXIT_CODE_USAGE,
    HTTP_FAILURE_MIN,
    REDIRECT_LIMIT_NOTE,
    UNIX_SIGNAL_EXIT_OFFSET,
    HTTPMethod,
)
from .http_client import proxy_resolves_remotely
from .implementations.dns import OverrideDNSResolver
from .models import StepMetrics
from .otlp import OTLPDependencyError, OTLPExporter, OTLPExportError, ensure_otel_available
from .prometheus import PrometheusExporter
from .render import OutputRenderer
from .slo import (
    SLO_KEYS,
    SLOResult,
    SLOSpecError,
    evaluate_slo,
    parse_slo_file,
    parse_slo_spec,
    select_step_for_evaluation,
)
from .utils import create_ssl_context, read_request_data, redact_url_credentials, url_validation_error, validate_url

# Exit codes (aligned with sysexits.h conventions where possible)
# Fall back to canonical numeric equivalents when running on platforms
# that do not expose the EX_* constants (e.g., Windows).
EXIT_SUCCESS = EXIT_CODE_OK
EXIT_USAGE_ERROR = EXIT_CODE_USAGE
EXIT_NETWORK_ERROR = EXIT_CODE_TEMPFAIL
EXIT_FATAL_ERROR = EXIT_CODE_SOFTWARE
EXIT_SLO_VIOLATION = EXIT_CODE_SLO_VIOLATION
EXIT_HTTP_FAILURE = EXIT_CODE_HTTP_FAILURE
MAX_PORT = 65535
EXIT_TOO_MANY_REDIRECTS = EXIT_CODE_TOO_MANY_REDIRECTS
EXIT_EXPORT_ERROR = EXIT_CODE_CANTCREAT
PROXY_SCHEMES = frozenset({"http", "https", "socks5", "socks5h"})


# Global console for error messages
console = Console(stderr=True)

# Configure logging with Rich
logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_time=False, show_path=False)],
)
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    argcomplete: ModuleType | None
else:
    try:
        import argcomplete  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover
        argcomplete = None
        logger.debug("argcomplete is not installed, skipping autocomplete")


def _configure_output_encoding() -> None:
    """Replace characters unsupported by the active output encodings."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


class RichArgumentParser(argparse.ArgumentParser):
    """ArgumentParser with Rich error formatting."""

    def error(self, message: str) -> NoReturn:
        """Override error to provide Rich formatted error messages."""
        console.print(
            Panel(
                f"[red]{escape(message)}[/red]",
                title="[bold red]❌ Argument Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        self.print_usage(sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)


class RichHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    """Show meaningful defaults while keeping raw layout."""

    def _get_help_string(self, action: argparse.Action) -> str:
        """Suppress unset and false defaults from the help text."""
        if action.default is None or action.default is False:
            return action.help or ""
        return super()._get_help_string(action) or ""


def _parse_http_method(value: str) -> HTTPMethod:
    """Parse an HTTP method case-insensitively with an actionable error."""
    try:
        return HTTPMethod(value.upper())
    except ValueError as exc:
        methods = ", ".join(method.value for method in HTTPMethod)
        msg = f"invalid HTTP method {value!r}; choose from {methods}"
        raise argparse.ArgumentTypeError(msg) from exc


# RFC 9110 section 5.6.2 token characters.
_HEADER_NAME_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
# Visible ASCII, space and tab. obs-text (0x80-0xFF) is excluded because httpx
# encodes str header values as ASCII.
_HEADER_VALUE_RE = re.compile(r"[\t\x20-\x7e]*")
_HEADER_CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


def _validate_header(name: str, value: str) -> None:
    """Reject header names and values that cannot be sent as given.

    The value itself is never echoed: it may carry a credential.
    """
    if not _HEADER_NAME_RE.fullmatch(name):
        msg = f"Invalid header name {name!r}: must be an HTTP token (letters, digits and !#$%&'*+-.^_`|~)"
        raise ValueError(msg)
    if _HEADER_VALUE_RE.fullmatch(value):
        return
    if _HEADER_CONTROL_RE.search(value):
        msg = f"Invalid value for header {name!r}: control characters such as CR, LF or NUL are not allowed"
    else:
        msg = f"Invalid value for header {name!r}: only ASCII characters are supported"
    raise ValueError(msg)


def _parse_headers(values: Sequence[str] | None) -> dict[str, str]:
    """Convert --header inputs into a case-preserving mapping."""
    if not values:
        return {}

    headers: dict[str, str] = {}
    canonical: dict[str, str] = {}
    for item in values:
        if ":" not in item:
            msg = f"Invalid header format: '{item}' (expected NAME:VALUE)"
            raise ValueError(msg)
        name, value = item.split(":", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            msg = f"Header name cannot be empty: '{item}'"
            raise ValueError(msg)
        _validate_header(name, value)
        lower = name.lower()
        key = canonical.get(lower, name)
        canonical.setdefault(lower, key)
        headers[key] = value
    return headers


def create_parser() -> RichArgumentParser:
    """Create and configure argument parser.

    Returns:
        Configured RichArgumentParser instance.

    """
    parser = RichArgumentParser(
        prog="httptap",
        description="HTTP request visualizer (DNS → TCP → TLS → HTTP)",
        formatter_class=RichHelpFormatter,
        epilog=f"""
Examples:
  - Basic timing waterfall (GET request):
      httptap https://httpbin.io/get
  - POST request with JSON data:
      httptap https://httpbin.io/post --method POST --data '{{"key": "value"}}'
  - POST with data from file:
      httptap https://httpbin.io/post --data @payload.json
  - PUT request with custom headers:
      httptap https://httpbin.io/put --method PUT --data '{{"status": "active"}}' -H "Authorization: Bearer token"
  - Follow redirect chains (up to 10 hops):
      httptap --follow https://httpbin.io/redirect/3
  - Compact view with shorter timeout:
      httptap --compact --timeout 10 https://httpbin.io/delay/2
  - Metrics-only output and JSON export:
      httptap --metrics-only --json out/report.json https://httpbin.io/get
  - Route through a proxy:
      httptap -x http://proxy:3128 https://httpbin.io/get
  - Ignore proxy environment variables and connect directly:
      httptap --proxy "" https://httpbin.io/get

Exit codes:
  {EXIT_SUCCESS:>3} (EX_OK)       : Success
  {EXIT_SLO_VIOLATION:>3}              : SLO threshold violation (request succeeded but too slow)
  {EXIT_HTTP_FAILURE:>3}              : HTTP 4xx/5xx response with --fail
  {EXIT_TOO_MANY_REDIRECTS:>3}              : Maximum redirects followed
  {EXIT_USAGE_ERROR:>3} (EX_USAGE)    : Invalid arguments
  {EXIT_FATAL_ERROR:>3} (EX_SOFTWARE) : Internal error
  {EXIT_EXPORT_ERROR:>3} (EX_CANTCREAT): --json output could not be written
  {EXIT_NETWORK_ERROR:>3} (EX_TEMPFAIL) : Network/TLS error (partial output available)
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the httptap version and exit.",
    )

    url_arg = parser.add_argument(
        "url",
        help="Target URL to analyze (must start with http:// or https://).",
    )
    # Disable file completion for URL argument since we expect URLs, not file paths
    if argcomplete:  # pragma: no cover
        url_arg.completer = argcomplete.completers.SuppressCompleter()  # type: ignore[attr-defined]

    request_group = parser.add_argument_group("Request options")
    request_group.add_argument(
        "-X",
        "--request",
        "--method",
        dest="method",
        type=_parse_http_method,
        default=None,
        choices=list(HTTPMethod),
        metavar="METHOD",
        help="HTTP method to use. Defaults to POST if --data is provided, otherwise GET.",
    )
    request_group.add_argument(
        "-d",
        "--data",
        metavar="DATA",
        help="Request body data (use @filename to read from file).",
    )
    request_group.add_argument(
        "-L",
        "--location",
        "--follow",
        dest="follow",
        action="store_true",
        help="Follow redirects until a non-3xx response is reached (max 10).",
    )
    request_group.add_argument(
        "-m",
        "--max-time",
        "--timeout",
        dest="timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help="Abort the request chain if total elapsed time exceeds SECONDS.",
    )
    request_group.add_argument(
        "--no-http2",
        "--http1.1",
        dest="no_http2",
        action="store_true",
        help="Disable HTTP/2 negotiation and force HTTP/1.1 connections.",
    )
    request_group.add_argument(
        "-f",
        "--fail",
        dest="fail_on_http_error",
        action="store_true",
        help=f"Exit with code {EXIT_HTTP_FAILURE} for HTTP 4xx/5xx responses after printing results.",
    )
    address_family_group = request_group.add_mutually_exclusive_group()
    address_family_group.add_argument(
        "-4",
        "--ipv4",
        dest="address_family",
        action="store_const",
        const=socket.AF_INET,
        help="Resolve and connect using IPv4 addresses only.",
    )
    address_family_group.add_argument(
        "-6",
        "--ipv6",
        dest="address_family",
        action="store_const",
        const=socket.AF_INET6,
        help="Resolve and connect using IPv6 addresses only.",
    )
    request_group.add_argument(
        "--resolve",
        action="append",
        default=[],
        metavar="HOST:PORT:ADDR",
        help="Connect HOST:PORT to ADDR while preserving the original Host header and TLS SNI.",
    )

    # SSL/TLS options (mutually exclusive)
    ssl_group = request_group.add_mutually_exclusive_group()
    ssl_group.add_argument(
        "-k",
        "--insecure",
        "--ignore-ssl",
        dest="ignore_ssl",
        action="store_true",
        help="Disable TLS certificate verification (useful for debugging self-signed hosts).",
    )
    ssl_group.add_argument(
        "--cacert",
        "--ca-bundle",
        dest="ca_bundle",
        metavar="FILE",
        help="Path to custom CA certificate bundle (PEM format). Use for internal APIs with custom CAs.",
    )
    request_group.add_argument(
        "-x",
        "--proxy",
        metavar="URL",
        help=(
            "Route requests through the given proxy (http://, https://, socks5://, socks5h://). "
            'Use --proxy "" to ignore proxy environment variables and connect directly.'
        ),
    )
    request_group.add_argument(
        "-H",
        "--header",
        action="append",
        dest="headers",
        metavar="NAME:VALUE",
        help="Add a request header (repeatable).",
    )

    output_group = parser.add_argument_group("Output options")
    output_group.add_argument(
        "--compact",
        action="store_true",
        help=(
            "Print one summary line per step instead of the waterfall view. Ignored when --metrics-only is also set."
        ),
    )
    output_group.add_argument(
        "--metrics-only",
        action="store_true",
        help="Emit key=value metrics without Rich visuals or progress spinners. Takes precedence over --compact.",
    )
    output_group.add_argument(
        "--json",
        metavar="PATH",
        help="Export the collected metrics, network, and response details to PATH. Use - for stdout.",
    )
    output_group.add_argument(
        "--prometheus",
        metavar="PATH",
        help="Export timing metrics in Prometheus textfile collector format to PATH.",
    )
    output_group.add_argument(
        "--otlp",
        metavar="ENDPOINT",
        help="Export request traces to an OTLP/HTTP endpoint (requires httptap[otel]).",
    )
    slo_keys_hint = ", ".join(sorted(SLO_KEYS))
    output_group.add_argument(
        "--slo",
        metavar="KEY=MS[,KEY=MS...]",
        default=None,
        help=(
            "Check the final successful step against per-phase latency budgets "
            "in milliseconds. On violation httptap still prints the full report "
            f"but exits with code {EXIT_SLO_VIOLATION}. Valid keys: {slo_keys_hint}."
        ),
    )
    output_group.add_argument(
        "--slo-file",
        metavar="PATH",
        default=None,
        help="Read newline-delimited KEY=MS SLO thresholds from PATH. Values from --slo take precedence.",
    )

    return parser


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""

    def signal_handler(signum: int, _frame: object) -> NoReturn:
        """Handle interrupt signals gracefully.

        Args:
            signum: Signal number.
            _frame: Current stack frame (unused).

        """
        console.print("\n[yellow]⚠ Interrupted by user[/yellow]")
        sys.exit(UNIX_SIGNAL_EXIT_OFFSET + signum)  # Standard Unix convention

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def _execute_analysis(
    analyzer: HTTPTapAnalyzer,
    args: argparse.Namespace,
    method: HTTPMethod,
    content: bytes | None,
    headers: Mapping[str, str],
) -> list[StepMetrics]:
    """Execute HTTP analysis with optional progress reporting."""
    # The spinner draws on stdout, which must stay machine-readable.
    if args.metrics_only or args.json == "-":
        return analyzer.analyze_url(args.url, method=method, content=content, headers=headers)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Analyzing {task.fields[url]}..."),
        console=Console(),
        transient=True,
    ) as progress:
        task = progress.add_task("analyze", url=escape(redact_url_credentials(args.url)), total=None)
        steps = analyzer.analyze_url(args.url, method=method, content=content, headers=headers)
        progress.update(task, completed=True)
        return steps


def _export_results(
    renderer: OutputRenderer,
    steps: list[StepMetrics],
    args: argparse.Namespace,
    *,
    slo_result: SLOResult | None = None,
) -> bool:
    """Export analysis results for each requested output format.

    Returns ``False`` only when the JSON report could not be written;
    Prometheus and OTLP delivery problems are reported as warnings.
    """
    exported = True
    if args.json:
        try:
            renderer.export_json(steps, redact_url_credentials(args.url), args.json, slo_result=slo_result)
        except OSError as export_error:
            console.print(
                f"[yellow]⚠ Warning:[/yellow] Failed to export JSON: {escape(str(export_error))}",
            )
            exported = False

    if getattr(args, "prometheus", None):
        try:
            PrometheusExporter(Console(stderr=True)).export(steps, args.prometheus)
        except OSError as export_error:
            console.print(
                f"[yellow]⚠ Warning:[/yellow] Failed to export Prometheus metrics: {escape(str(export_error))}",
            )

    if getattr(args, "otlp", None):
        try:
            OTLPExporter().export(steps, args.otlp, timeout=args.timeout)
        except OTLPExportError as export_error:
            console.print(
                f"[yellow]⚠ Warning:[/yellow] Failed to export OTLP traces: {escape(str(export_error))}",
            )

    return exported


def _render_results(
    renderer: OutputRenderer,
    steps: list[StepMetrics],
    args: argparse.Namespace,
    *,
    slo_result: SLOResult | None = None,
) -> None:
    """Render analysis output unless JSON is directed to stdout."""
    if args.json != "-":
        renderer.render_analysis(steps, redact_url_credentials(args.url), slo_result=slo_result)


def _complete_analysis(
    renderer: OutputRenderer,
    steps: list[StepMetrics],
    args: argparse.Namespace,
    *,
    slo_result: SLOResult | None = None,
) -> int:
    """Render, export, and return the final exit code."""
    _render_results(renderer, steps, args, slo_result=slo_result)
    _warn_redirect_limit(steps)
    exported = _export_results(renderer, steps, args, slo_result=slo_result)
    return determine_exit_code(
        steps,
        slo_result=slo_result,
        fail_on_http_error=args.fail_on_http_error,
        export_failed=not exported,
    )


def _evaluate_slo(
    steps: list[StepMetrics],
    thresholds: Mapping[str, float],
) -> SLOResult | None:
    """Evaluate SLO thresholds against the final successful step.

    Args:
        steps: Analysis steps.
        thresholds: Parsed ``--slo`` specification produced by
            :func:`parse_slo_spec`. An empty mapping disables
            evaluation.

    Returns:
        :class:`SLOResult` when thresholds were supplied and there is
        at least one successful step to evaluate; ``None`` otherwise.

    Raises:
        SLOSpecError: Propagated from :func:`evaluate_slo` if
            ``thresholds`` contains a key outside :data:`SLO_KEYS`.
            The CLI pipeline validates input via
            :func:`parse_slo_spec` earlier, so this should not happen
            in practice.

    """
    if not thresholds:
        return None
    step = select_step_for_evaluation(steps)
    if step is None:
        return None
    return evaluate_slo(step, thresholds)


def _merge_headers(defaults: Mapping[str, str], overrides: Mapping[str, str]) -> dict[str, str]:
    """Overlay user headers on derived defaults, matching names case-insensitively."""
    overridden = {name.lower() for name in overrides}
    merged = {name: value for name, value in defaults.items() if name.lower() not in overridden}
    merged.update(overrides)
    return merged


def _normalize_export_arguments(args: argparse.Namespace) -> None:
    """Validate and normalize ``--json``, ``--prometheus`` and ``--otlp`` in place."""
    json_path = getattr(args, "json", None)
    if json_path != "-":
        args.json = _validate_output_path(json_path, "JSON export")
    args.prometheus = _validate_output_path(getattr(args, "prometheus", None), "Prometheus export")
    args.otlp = _validate_otlp_endpoint(getattr(args, "otlp", None))
    if args.otlp is not None:
        ensure_otel_available()


def _validate_output_path(path: str | None, option: str) -> str | None:
    """Normalize an optional export path or reject an empty value."""
    if path is None:
        return None
    normalized_path = str(path).strip()
    if not normalized_path:
        msg = f"{option} path cannot be empty."
        raise ValueError(msg)
    return normalized_path


def _validate_otlp_endpoint(endpoint: str | None) -> str | None:
    """Normalize and validate an optional OTLP/HTTP endpoint."""
    if endpoint is None:
        return None
    normalized_endpoint = str(endpoint).strip()
    parsed = urlsplit(normalized_endpoint)
    if not normalized_endpoint or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        msg = "OTLP endpoint must be an absolute http:// or https:// URL."
        raise ValueError(msg)
    return normalized_endpoint


def _parse_slo_thresholds(args: argparse.Namespace) -> dict[str, float]:
    """Load file thresholds and apply inline ``--slo`` overrides."""
    file_thresholds: dict[str, float] = {}
    slo_file_arg = getattr(args, "slo_file", None)
    if slo_file_arg is not None:
        slo_file = str(slo_file_arg).strip()
        if not slo_file:
            msg = "SLO file path cannot be empty."
            raise SLOSpecError(msg)
        file_thresholds = parse_slo_file(Path(slo_file).expanduser())

    cli_thresholds = parse_slo_spec(args.slo) if args.slo is not None else {}
    return {**file_thresholds, **cli_thresholds}


def _parse_resolve_entries(
    values: list[str],
    address_family: int | None,
) -> dict[tuple[str, int], str]:
    """Parse curl-compatible ``--resolve HOST:PORT:ADDR`` values."""
    entries: dict[tuple[str, int], str] = {}
    for value in values:
        host, separator, remainder = value.partition(":")
        port_text, separator, address = remainder.partition(":")
        if (
            not separator
            or not host
            or not port_text
            or not address
            or any(part != part.strip() for part in (host, port_text, address))
        ):
            msg = f"Invalid --resolve value {value!r}; expected HOST:PORT:ADDR"
            raise ValueError(msg)

        if not port_text.isascii() or not port_text.isdecimal():
            msg = f"Invalid --resolve port {port_text!r}; expected 1-65535"
            raise ValueError(msg)
        port = int(port_text)
        if not 1 <= port <= MAX_PORT:
            msg = f"Invalid --resolve port {port_text!r}; expected 1-65535"
            raise ValueError(msg)

        if address.startswith("[") and address.endswith("]"):
            address = address[1:-1]
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as exc:
            msg = f"Invalid --resolve address {address!r}; expected an IPv4 or IPv6 address"
            raise ValueError(msg) from exc

        expected_family = socket.AF_INET6 if isinstance(parsed_address, ipaddress.IPv6Address) else socket.AF_INET
        if address_family is not None and address_family != expected_family:
            version = "IPv6" if address_family == socket.AF_INET6 else "IPv4"
            msg = f"--resolve address {address!r} does not match --{version.lower()}"
            raise ValueError(msg)

        key = (host.lower(), port)
        if key in entries:
            msg = f"Duplicate --resolve entry for {host}:{port}"
            raise ValueError(msg)
        entries[key] = str(parsed_address)

    return entries


def _validate_local_dns_overrides(args: argparse.Namespace) -> None:
    """Reject local DNS overrides when the proxy resolves the target remotely."""
    if getattr(args, "address_family", None) is None and not args.resolve_entries:
        return
    proxy = getattr(args, "proxy", None)
    if proxy_resolves_remotely(proxy, args.url, noproxy=proxy == ""):
        msg = "-4/-6 and --resolve cannot be used with a proxy that resolves hostnames remotely (http, https, socks5h)"
        raise ValueError(msg)


def validate_arguments(args: argparse.Namespace) -> bool:  # noqa: PLR0911
    """Validate command-line arguments with Rich formatting.

    Args:
        args: Parsed arguments.

    Returns:
        False if validation fails (error already printed), True if valid.

    """
    if not validate_url(args.url):
        error_text = Text()
        error_text.append("Invalid URL: ", style="bold red")
        error_text.append(f"'{redact_url_credentials(args.url)}'", style="yellow")
        error_text.append("\n\nURLs must start with ", style="red")
        error_text.append("http://", style="cyan")
        error_text.append(" or ", style="red")
        error_text.append("https://", style="cyan")

        console.print(
            Panel(
                error_text,
                title="[bold red]❌ Validation Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return False

    if not math.isfinite(args.timeout) or args.timeout <= 0:
        error_text = Text()
        error_text.append("Invalid timeout: ", style="bold red")
        error_text.append(f"{args.timeout}", style="yellow")
        error_text.append(" seconds\n\n", style="red")
        error_text.append("Timeout must be a positive number", style="red")

        console.print(
            Panel(
                error_text,
                title="[bold red]❌ Validation Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return False

    try:
        args.headers = _parse_headers(getattr(args, "headers", None))
    except ValueError as exc:
        console.print(
            Panel(
                escape(str(exc)),
                title="[bold red]❌ Header Error[/bold red]",
                border_style="red",
            )
        )
        return False

    if not _validate_connection_arguments(args):
        return False

    try:
        args.resolve_entries = _parse_resolve_entries(
            getattr(args, "resolve", []),
            getattr(args, "address_family", None),
        )
    except ValueError as exc:
        console.print(
            Panel(
                escape(str(exc)),
                title="[bold red]❌ Resolve Error[/bold red]",
                border_style="red",
            )
        )
        return False

    try:
        _validate_local_dns_overrides(args)
    except ValueError as exc:
        console.print(
            Panel(
                escape(str(exc)),
                title="[bold red]❌ Validation Error[/bold red]",
                border_style="red",
            )
        )
        return False

    try:
        _normalize_export_arguments(args)
    except (OTLPDependencyError, ValueError) as exc:
        console.print(
            Panel(
                f"[red]{escape(str(exc))}[/red]",
                title="[bold red]❌ Export Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return False

    try:
        args.slo_thresholds = _parse_slo_thresholds(args)
    except SLOSpecError as exc:
        console.print(
            Panel(
                f"[red]{escape(str(exc))}[/red]",
                title="[bold red]❌ SLO Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return False

    return True


def _validate_connection_arguments(args: argparse.Namespace) -> bool:
    """Validate TLS and proxy arguments and normalize the CA bundle path."""
    if args.ca_bundle is not None:
        ca_bundle_str = str(args.ca_bundle).strip()
        if not ca_bundle_str:
            console.print(
                Panel(
                    (
                        "[red]CA bundle path cannot be empty. "
                        "Provide a PEM file path when using --cacert/--ca-bundle.[/red]"
                    ),
                    title="[bold red]❌ Validation Error[/bold red]",
                    border_style="red",
                    padding=(1, 2),
                )
            )
            return False
        ca_bundle_path = Path(ca_bundle_str).expanduser().absolute()
        if not ca_bundle_path.is_file():
            console.print(
                Panel(
                    f"[red]CA bundle file does not exist: {escape(str(ca_bundle_path))}[/red]",
                    title="[bold red]❌ Validation Error[/bold red]",
                    border_style="red",
                    padding=(1, 2),
                )
            )
            return False
        try:
            create_ssl_context(verify_ssl=True, ca_bundle_path=str(ca_bundle_path))
        except ValueError as exc:
            console.print(
                Panel(
                    f"[red]{escape(str(exc))}[/red]",
                    title="[bold red]❌ Validation Error[/bold red]",
                    border_style="red",
                    padding=(1, 2),
                )
            )
            return False
        args.ca_bundle = str(ca_bundle_path)

    if args.proxy and "://" not in args.proxy:
        # curl treats a scheme-less proxy as plain HTTP.
        args.proxy = f"http://{args.proxy}"

    proxy_error = url_validation_error(args.proxy, PROXY_SCHEMES) if args.proxy else None
    if proxy_error is not None:
        error_text = Text()
        error_text.append("Invalid proxy URL: ", style="bold red")
        error_text.append(f"'{redact_url_credentials(args.proxy)}'", style="yellow")
        error_text.append(f"\n{proxy_error}", style="red")
        error_text.append("\n\nProxy URL must use http://, https://, socks5://, or socks5h://.", style="red")
        console.print(
            Panel(
                error_text,
                title="[bold red]❌ Validation Error[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return False

    return True


def determine_exit_code(  # noqa: PLR0911 - one return per precedence level
    steps: list[StepMetrics],
    *,
    slo_result: SLOResult | None = None,
    fail_on_http_error: bool = False,
    export_failed: bool = False,
) -> int:
    """Determine appropriate exit code based on analysis results.

    Precedence (highest-severity first):

    1. No steps or an internal error → ``EXIT_FATAL_ERROR`` (70).
    2. Redirect limit exceeded → ``EXIT_TOO_MANY_REDIRECTS`` (47).
    3. Network / TLS error → ``EXIT_NETWORK_ERROR`` (75).
    4. ``--json`` report could not be written → ``EXIT_EXPORT_ERROR`` (73).
    5. HTTP 4xx/5xx response with ``--fail`` → ``EXIT_HTTP_FAILURE`` (22).
    6. SLO violation on the final successful step →
       ``EXIT_SLO_VIOLATION`` (4).
    7. Otherwise → ``EXIT_SUCCESS`` (0).

    Invalid arguments (64) are reported before any request is made.

    Args:
        steps: List of step metrics from analysis.
        slo_result: Optional SLO evaluation result for the final
            successful step.
        fail_on_http_error: Whether HTTP 4xx/5xx responses should fail the
            command after results have been rendered.
        export_failed: Whether the ``--json`` report could not be written.

    Returns:
        Appropriate exit code.

    """
    if not steps:
        return EXIT_FATAL_ERROR

    if any(step.error_kind == "internal" for step in steps):
        return EXIT_FATAL_ERROR

    if any(step.redirect_limit_reached for step in steps):
        return EXIT_TOO_MANY_REDIRECTS

    if any(step.has_error for step in steps):
        return EXIT_NETWORK_ERROR

    if export_failed:
        return EXIT_EXPORT_ERROR

    if fail_on_http_error and any(
        step.response.status is not None and step.response.status >= HTTP_FAILURE_MIN for step in steps
    ):
        return EXIT_HTTP_FAILURE

    if slo_result is not None and not slo_result.passed:
        return EXIT_SLO_VIOLATION

    return EXIT_SUCCESS


def _warn_redirect_limit(steps: Sequence[StepMetrics]) -> None:
    """Print a warning when redirect following stopped at its limit."""
    for step in steps:
        if step.redirect_limit_reached:
            console.print(f"[yellow]Warning:[/yellow] {escape(step.note or REDIRECT_LIMIT_NOTE)}")
            return


def main() -> int:
    """Run the CLI with Rich UI enhancements.

    Returns:
        Exit code: ``0`` on success, ``4`` on SLO threshold violation,
        ``22`` on HTTP failure with ``--fail``, ``47`` when the redirect limit
        is reached, ``64`` on invalid arguments, ``70`` on internal error,
        ``73`` when the ``--json`` report cannot be written, and ``75`` on
        network or TLS failure. See :func:`determine_exit_code` for precedence.

    """
    _configure_output_encoding()

    try:
        parser = create_parser()
        if argcomplete:  # pragma: no cover
            argcomplete.autocomplete(parser)

        setup_signal_handlers()
        args = parser.parse_args()

        if not validate_arguments(args):
            return EXIT_USAGE_ERROR

        if args.compact and args.metrics_only:
            console.print("[yellow]Warning:[/yellow] --compact is ignored because --metrics-only takes precedence.")

        try:
            content, auto_headers = read_request_data(args.data)
        except (FileNotFoundError, OSError) as e:
            console.print(f"[red]Error reading data: {escape(str(e))}[/red]")
            return EXIT_USAGE_ERROR
        method = args.method if args.method is not None else HTTPMethod.GET
        method_was_explicit = args.method is not None

        if content and method == HTTPMethod.GET and not method_was_explicit:
            method = HTTPMethod.POST
            logger.info("Auto-switching from GET to POST due to request body")

        if content and method in (HTTPMethod.GET, HTTPMethod.HEAD) and method_was_explicit:
            logger.warning(
                "%s requests with body are uncommon but allowed. Consider using POST, PUT, or PATCH.",
                method.value,
            )

        headers_dict = _merge_headers(auto_headers, args.headers or {})

        noproxy = args.proxy == ""
        dns_resolver = None
        if args.address_family is not None or args.resolve_entries:
            dns_resolver = OverrideDNSResolver(
                args.resolve_entries,
                family=args.address_family or socket.AF_UNSPEC,
            )
        analyzer = HTTPTapAnalyzer(
            follow_redirects=args.follow,
            timeout=args.timeout,
            http2=not args.no_http2,
            verify_ssl=not args.ignore_ssl,
            ca_bundle_path=args.ca_bundle,
            proxy=None if noproxy else args.proxy,
            noproxy=noproxy,
            dns_resolver=dns_resolver,
        )

        renderer = OutputRenderer(
            compact=args.compact,
            metrics_only=args.metrics_only,
        )

        steps = _execute_analysis(analyzer, args, method, content, headers_dict)
        slo_result = _evaluate_slo(steps, args.slo_thresholds)
        return _complete_analysis(renderer, steps, args, slo_result=slo_result)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Interrupted by user[/yellow]")
        return UNIX_SIGNAL_EXIT_OFFSET + signal.SIGINT

    except Exception as e:
        logger.exception("Unexpected error")

        error_panel = Panel(
            f"[red]{escape(str(e))}[/red]",
            title="[bold red]❌ Internal Error[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
        console.print(error_panel)
        return EXIT_FATAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
