"""Output modes (Rich, compact, metrics-only, JSON, Prometheus) and response accounting."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e import servers as srv
from tests.e2e.harness import EXIT_OK, RunCommand, Servers, assert_timing_invariants, parse_metrics

if TYPE_CHECKING:
    from pathlib import Path

    from tests.e2e.certs import CertSet


def test_rich_default(run: RunCommand, servers: Servers) -> None:
    url = servers.url(servers.origin)
    res = run([url]).expect(EXIT_OK)
    assert "HTTP Tap Analysis" in res.stdout
    assert f"Step 1: {url}" in res.stdout
    assert "Status: 200" in res.stdout
    assert "Total:" in res.stdout
    assert "Traceback" not in res.output


def test_rich_shows_tls_details(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    url = f"https://e2e.test:{servers.port(servers.tls_valid)}/ok"
    res = run(
        [
            "--resolve",
            f"e2e.test:{servers.port(servers.tls_valid)}:{servers.config.target_ip}",
            "--cacert",
            str(certs.ca),
            url,
        ]
    ).expect(EXIT_OK)
    assert "TLS" in res.stdout
    assert "Status: 200" in res.stdout


def test_compact(run: RunCommand, servers: Servers) -> None:
    url = servers.url(servers.origin)
    res = run(["--compact", url]).expect(EXIT_OK)
    line = next(line for line in res.stdout.splitlines() if line.startswith("Step 1:"))
    assert re.match(
        rf"Step 1: 200 GET {re.escape(url)} \| dns=[\d.]+ms connect=[\d.]+ms tls=[\d.]+ms "
        r"ttfb=[\d.]+ms total=[\d.]+ms \| 3 B$",
        line,
    ), line


def test_compact_redirect_chain_has_summary(run: RunCommand, servers: Servers) -> None:
    res = run(["--compact", "-L", servers.url(servers.origin, "/redirect/2")]).expect(EXIT_OK)
    assert re.search(r"^Step 1: 302 GET ", res.stdout, re.MULTILINE)
    assert re.search(r"^Step 3: 200 GET .*/ok ", res.stdout, re.MULTILINE)
    assert "Redirect Chain Summary" in res.stdout


def test_metrics_only_tokens(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", servers.url(servers.origin)]).expect(EXIT_OK)
    (step,) = parse_metrics(res.stdout)
    for key in ("dns", "connect", "tls", "ttfb", "total", "status", "bytes", "ip", "family", "proxy"):
        assert key in step, (key, step)
    assert step["status"] == "200"
    assert step["bytes"] == "3"
    assert step["proxy"] == "direct"
    assert res.stderr.strip() == ""
    assert "\x1b[" not in res.stdout


def test_metrics_only_values_have_no_spaces_with_odd_inputs(run: RunCommand, servers: Servers) -> None:
    """Proxy and URL values are percent-encoded so every token stays key=value."""
    proxy = servers.proxy_url(servers.proxy, userinfo="user:pw%20x@")
    res = run(["--metrics-only", "-x", proxy, servers.url(servers.origin, "/ok?q=a%20b")]).expect(EXIT_OK)
    (step,) = parse_metrics(res.stdout)
    assert step["proxy"].startswith("http://user:")


def test_metrics_only_error_line_is_single_line(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", f"http://{servers.host}:{servers.dead.port}/"]).expect(75)
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, res.describe()
    assert lines[0].startswith("Step 1: ERROR"), res.describe()


def test_metrics_only_redirect_chain(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", "-L", servers.url(servers.origin, "/redirect/3")]).expect(EXIT_OK)
    steps = parse_metrics(res.stdout)
    assert [s["status"] for s in steps] == ["302", "302", "302", "200"]


def test_json_file(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "report.json"
    url = servers.url(servers.origin)
    res = run(["--json", str(path), url]).expect(EXIT_OK)
    assert "HTTP Tap Analysis" in res.stdout, "Rich report is still printed with --json FILE"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["initial_url"] == url
    assert data["total_steps"] == 1 == len(data["steps"])
    step = data["steps"][0]
    assert step["response"]["status"] == 200
    assert step["response"]["bytes"] == 3
    if servers.config.target_host == servers.config.target_ip:
        assert step["network"]["ip"] == servers.config.target_ip
    assert step["error"] is None
    assert data["summary"] == {
        "total_time_ms": data["summary"]["total_time_ms"],
        "final_status": 200,
        "final_url": url,
        "final_bytes": 3,
        "errors": 0,
    }
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", data["timestamp"])
    assert_timing_invariants(step, res.wall)


def test_json_stdout_only_json(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", servers.url(servers.origin)]).expect(EXIT_OK)
    data = json.loads(res.stdout)
    assert data["steps"][0]["response"]["status"] == 200
    assert "HTTP Tap Analysis" not in res.stdout
    assert "\x1b[" not in res.stdout


def test_json_stdout_with_metrics_only_still_pure_json(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", "--metrics-only", servers.url(servers.origin)]).expect(EXIT_OK)
    json.loads(res.stdout)


def test_json_stdout_on_network_error_is_json(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", f"http://{servers.host}:{servers.dead.port}/"]).expect(75)
    data = json.loads(res.stdout)
    assert data["summary"]["errors"] == 1
    assert data["steps"][0]["error"]


def test_json_overwrites_existing_file(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "report.json"
    path.write_text("old garbage")
    run(["--metrics-only", "--json", str(path), servers.url(servers.origin)]).expect(EXIT_OK)
    json.loads(path.read_text(encoding="utf-8"))


def test_json_creates_parent_directories(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "a" / "b" / "report.json"
    run(["--metrics-only", "--json", str(path), servers.url(servers.origin)]).expect(EXIT_OK)
    json.loads(path.read_text(encoding="utf-8"))


def test_json_unwritable_path(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    blocker = out_dir / "file"
    blocker.write_text("x")
    res = run(["--metrics-only", "--json", str(blocker / "report.json"), servers.url(servers.origin)]).expect(73)
    assert "Failed to export JSON" in res.stderr
    assert "status=200" in res.stdout, "results are still printed"


def test_json_path_is_directory(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    run(["--metrics-only", "--json", str(out_dir), servers.url(servers.origin)]).expect(73)


def test_prometheus_file(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "httptap.prom"
    run(["--metrics-only", "--prometheus", str(path), servers.url(servers.origin, "/ok?secret=q")]).expect(EXIT_OK)
    text = path.read_text(encoding="utf-8")
    host = servers.config.target_host
    assert f'httptap_request_success{{host="{host}",step="1"}} 1' in text
    for phase in ("dns", "connect", "tls", "ttfb", "wait", "xfer", "total"):
        assert re.search(
            rf'httptap_request_duration_seconds{{host="{re.escape(host)}",step="1",phase="{phase}"}} '
            r"[0-9.e-]+$",
            text,
            re.MULTILINE,
        ), phase
    assert f'httptap_response_status_code{{host="{host}",step="1"}} 200' in text
    assert f'httptap_response_body_size_bytes{{host="{host}",step="1"}} 3' in text
    assert re.search(r"^httptap_last_run_timestamp_seconds\{host=\"[^\"]+\"\} \d+\.\d+$", text, re.MULTILINE)
    assert "secret" not in text, "queries must not become labels"
    assert "/ok" not in text, "paths must not become labels"
    for line in text.splitlines():
        assert line.startswith(("# HELP ", "# TYPE ", "httptap_")), line


def test_prometheus_failed_step_exports_only_success_zero(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    path = out_dir / "fail.prom"
    run(["--metrics-only", "--prometheus", str(path), f"http://{servers.host}:{servers.dead.port}/"]).expect(75)
    text = path.read_text(encoding="utf-8")
    assert re.search(r'^httptap_request_success\{host="[^"]+",step="1"\} 0$', text, re.MULTILINE)
    assert "httptap_request_duration_seconds{" not in text
    assert "httptap_response_status_code{" not in text


def test_prometheus_unwritable_is_warning(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    """Documented behaviour: only --json failures change the exit code (73); Prometheus failures warn."""
    blocker = out_dir / "file"
    blocker.write_text("x")
    res = run(["--metrics-only", "--prometheus", str(blocker / "x.prom"), servers.url(servers.origin)])
    res.expect(EXIT_OK)
    assert "Failed to export Prometheus metrics" in res.stderr


def test_all_exports_together(run: RunCommand, servers: Servers, out_dir: Path) -> None:
    jpath, ppath = out_dir / "r.json", out_dir / "r.prom"
    otlp = servers.url(servers.collector, "/v1/traces")
    before = len(servers.collector.spans)
    res = run(
        ["--compact", "--json", str(jpath), "--prometheus", str(ppath), "--otlp", otlp, servers.url(servers.origin)]
    ).expect(EXIT_OK)
    assert "Step 1: 200 GET" in res.stdout
    assert json.loads(jpath.read_text(encoding="utf-8"))["summary"]["final_status"] == 200
    assert "httptap_request_success" in ppath.read_text(encoding="utf-8")
    assert len(servers.collector.spans) > before


@pytest.mark.parametrize(
    ("path", "status", "expected_bytes"),
    [
        ("/gzip", 200, len(srv.GZIP_BODY)),
        ("/empty", 200, 0),
        ("/204", 204, 0),
        ("/304", 304, 0),
        ("/chunked", 200, sum(len(c) for c in srv.CHUNKS)),
        ("/large", 200, srv.LARGE_SIZE),
        ("/latin1-header", 200, len(b"latin1\n")),
        ("/huge-headers?count=60&size=150", 200, len(b"huge\n")),
    ],
    ids=["gzip-wire-bytes", "empty", "204", "304", "chunked", "large-5MB", "latin1-header", "huge-headers"],
)
def test_response_bytes(run: RunCommand, servers: Servers, path: str, status: int, expected_bytes: int) -> None:
    res = run(["--json", "-", servers.url(servers.origin, path)]).expect(EXIT_OK)
    step = res.json()["steps"][0]
    assert step["response"]["status"] == status
    assert step["response"]["bytes"] == expected_bytes
    assert_timing_invariants(step, res.wall)


def test_gzip_bytes_are_wire_not_decoded(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", servers.url(servers.origin, "/gzip")]).expect(EXIT_OK)
    assert res.json()["steps"][0]["response"]["bytes"] != len(srv.GZIP_PAYLOAD)


def test_head_bytes_zero(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", "-X", "HEAD", servers.url(servers.origin, "/head-check")]).expect(EXIT_OK)
    step = res.json()["steps"][0]
    assert step["response"]["status"] == 200
    assert step["response"]["bytes"] == 0
    assert step["response"]["headers"].get("content-length") == str(srv.HEAD_CHECK_SIZE)


def test_latin1_header_rendered(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", servers.url(servers.origin, "/latin1-header")]).expect(EXIT_OK)
    value = res.json()["steps"][0]["response"]["headers"]["x-latin1"]
    assert value == "café crème"


def test_very_large_header_block_no_internal_error(run: RunCommand, servers: Servers) -> None:
    res = run(["--metrics-only", servers.url(servers.origin, "/huge-headers?count=400&size=400")])
    assert res.code in (EXIT_OK, 75), res.describe()


def test_set_cookie_masked(run: RunCommand, servers: Servers) -> None:
    res = run(["--json", "-", servers.url(servers.origin, "/set-cookie")]).expect(EXIT_OK)
    assert srv.COOKIE_SECRET not in res.stdout
    assert srv.COOKIE_SECRET[4:-4] not in res.stdout


@pytest.mark.parametrize("path", ["/ok", "/large", "/redirect/2"])
def test_timing_invariants(run: RunCommand, servers: Servers, path: str) -> None:
    res = run(["--json", "-", "-L", servers.url(servers.origin, path)]).expect(EXIT_OK)
    data = res.json()
    for step in data["steps"]:
        assert_timing_invariants(step, res.wall)
    total = sum(s["timing"]["total_ms"] for s in data["steps"])
    assert abs(data["summary"]["total_time_ms"] - total) <= 0.01 * total + 0.01
    assert total <= res.wall * 1000


def test_timing_invariants_tls(run: RunCommand, servers: Servers, certs: CertSet) -> None:
    port = servers.port(servers.tls_valid)
    res = run(
        [
            "--json",
            "-",
            "--resolve",
            f"e2e.test:{port}:{servers.config.target_ip}",
            "--cacert",
            str(certs.ca),
            f"https://e2e.test:{port}/ok",
        ]
    ).expect(EXIT_OK)
    step = res.json()["steps"][0]
    assert step["timing"]["tls_ms"] > 0
    assert_timing_invariants(step, res.wall)
