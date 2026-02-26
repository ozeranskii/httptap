"""Output formatting utilities for HTTP request analysis.

This module provides formatters for converting metrics and data
into human-readable formats with Rich markup support.
"""

from rich.panel import Panel
from rich.text import Text

from .constants import (
    BYTES_PER_KIB,
    CERT_EXPIRY_CRITICAL_DAYS,
    CERT_EXPIRY_WARNING_DAYS,
    HTTP_REDIRECT_MAX,
    HTTP_REDIRECT_MIN,
    HTTP_SUCCESS_MAX,
    HTTP_SUCCESS_MIN,
)
from .models import StepMetrics


def format_step_header(step: StepMetrics) -> str:
    """Format step header with number and URL.

    Args:
        step: Step metrics to format.

    Returns:
        Formatted header string with rich markup.

    """
    return f"[bold cyan]Step {step.step_number}:[/bold cyan] [dim]{step.url}[/dim]"


def format_error(step: StepMetrics) -> Panel:
    """Format error information as a Rich panel.

    Args:
        step: Step metrics with error.

    Returns:
        Rich Panel with formatted error information.

    """
    error_text = Text()
    error_text.append("❌ ", style="bold red")
    error_text.append(str(step.error), style="red")

    if step.note:
        error_text.append("\n\n")
        error_text.append("💡 ", style="yellow")
        error_text.append(step.note, style="yellow")

    return Panel(
        error_text,
        title="[bold red]Error[/bold red]",
        border_style="red",
        padding=(0, 1),
    )


def _format_proxy_part(step: StepMetrics) -> str:
    """Format proxy information for display.

    Args:
        step: Step metrics with proxy data.

    Returns:
        Formatted proxy string with Rich markup.

    """
    source = step.network.proxy_source
    if step.proxied_via:
        hint = "from arg --proxy" if source == "--proxy" else f"from env {source}"
        return f"Proxy: {step.proxied_via} ({hint})"
    if source == "NO_PROXY":
        return "[yellow]Proxy: none (bypassed by env no_proxy)[/yellow]"
    if source == "noproxy":
        return 'Proxy: disabled (from --proxy "")'
    if source == "no_proxy_env":
        return "Proxy: direct (no matching proxy scheme in env)"
    return "Proxy: direct"


def format_network_info(step: StepMetrics) -> str | None:
    """Format network and security information.

    Args:
        step: Step metrics with network data.

    Returns:
        Formatted network info string or None if no data.

    """
    parts = []

    ip = step.network.ip
    if ip:
        family = step.network.ip_family
        parts.append(f"IP: {ip} ({family})" if family else f"IP: {ip}")

    http_version = step.network.http_version
    if http_version:
        parts.append(f"HTTP: {http_version}")

    parts.append(_format_proxy_part(step))

    for label, value in (
        ("TLS", step.network.tls_version),
        ("Cipher", step.network.tls_cipher),
        ("Cert", step.network.cert_cn),
    ):
        if value:
            parts.append(f"{label}: {value}")

    days_left = step.network.cert_days_left
    if days_left is not None:
        days_style = (
            "red"
            if days_left < CERT_EXPIRY_CRITICAL_DAYS
            else "yellow"
            if days_left < CERT_EXPIRY_WARNING_DAYS
            else "green"
        )
        parts.append(f"[{days_style}]Expires: {days_left}d[/{days_style}]")
    if step.network.tls_verified is False:
        parts.append("[bold red]⚠ TLS verification disabled[/bold red]")
    elif step.network.tls_custom_ca:
        parts.append("TLS CA: custom bundle")

    return f"  [dim]{' | '.join(parts)}[/dim]" if parts else None


def format_response_info(step: StepMetrics) -> str | None:
    """Format HTTP response information.

    Args:
        step: Step metrics with response data.

    Returns:
        Formatted response info string or None if no data.

    """
    parts = []

    if step.response.status:
        status = step.response.status
        if HTTP_SUCCESS_MIN <= status <= HTTP_SUCCESS_MAX:
            status_style = "green"
        elif HTTP_REDIRECT_MIN <= status <= HTTP_REDIRECT_MAX:
            status_style = "yellow"
        else:
            status_style = "red"
        parts.append(f"[{status_style}]Status: {status}[/{status_style}]")

    if step.response.bytes > 0:
        size_str = format_bytes_human(step.response.bytes)
        parts.append(f"Size: {size_str}")

    if step.response.server:
        parts.append(f"Server: {step.response.server}")
    if step.response.location:
        parts.append(f"→ [cyan]{step.response.location}[/cyan]")

    return f"  {' | '.join(parts)}" if parts else None


def format_bytes_human(num_bytes: int) -> str:
    """Format bytes in human-readable format.

    Args:
        num_bytes: Number of bytes.

    Returns:
        Formatted string with appropriate unit.

    Examples:
        >>> format_bytes_human(512)
        '512 B'
        >>> format_bytes_human(2048)
        '2.0 KB'
        >>> format_bytes_human(1048576)
        '1.0 MB'

    """
    size_kib = num_bytes / BYTES_PER_KIB
    if size_kib < 1:
        return f"{num_bytes} B"
    if size_kib < BYTES_PER_KIB:
        return f"{size_kib:.1f} KB"
    return f"{size_kib / BYTES_PER_KIB:.1f} MB"


def format_metrics_line(step: StepMetrics) -> str:
    """Format step metrics as machine-readable line.

    Args:
        step: Step metrics to format.

    Returns:
        Space-separated key=value pairs.

    Examples:
        >>> format_metrics_line(step)
        'dns=1.5 connect=45.2 tls=67.8 ttfb=156.4 total=234.7 status=200 bytes=1256'

    """
    parts = [
        f"dns={step.timing.dns_ms:.1f}",
        f"connect={step.timing.connect_ms:.1f}",
        f"tls={step.timing.tls_ms:.1f}",
        f"ttfb={step.timing.ttfb_ms:.1f}",
        f"total={step.timing.total_ms:.1f}",
        f"status={step.response.status}",
        f"bytes={step.response.bytes}",
    ]

    if step.network.ip:
        parts.append(f"ip={step.network.ip}")
    if step.network.ip_family:
        parts.append(f"family={step.network.ip_family}")
    if step.network.tls_version:
        parts.append(f"tls_version={step.network.tls_version}")

    if step.proxied_via:
        src = step.network.proxy_source
        hint = "arg" if src == "--proxy" else f"env:{src}"
        parts.append(f"proxy={step.proxied_via} proxy_from={hint}")
    elif step.network.proxy_source == "NO_PROXY":
        parts.append("proxy=none proxy_from=env:no_proxy")
    elif step.network.proxy_source == "noproxy":
        parts.append('proxy=disabled proxy_from=--proxy ""')
    elif step.network.proxy_source == "no_proxy_env":
        parts.append("proxy=direct proxy_from=no_scheme_match")
    else:
        parts.append("proxy=direct")

    return f"Step {step.step_number}: {' '.join(parts)}"
