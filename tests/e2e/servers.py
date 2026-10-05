"""Stdlib test servers: HTTP(S) origin, HTTP/CONNECT proxy, SOCKS5 proxy, OTLP collector.

Every server is threaded, binds an ephemeral port and records what it received so
tests can assert on the request that actually reached the wire.
"""

from __future__ import annotations

import base64
import gzip
import json
import selectors
import socket
import socketserver
import ssl
import struct
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import parse_qs, urlsplit

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from opentelemetry.proto.common.v1.common_pb2 import AnyValue
    from opentelemetry.proto.trace.v1.trace_pb2 import Span

_ServerT = TypeVar("_ServerT", bound=socketserver.BaseServer)

GZIP_PAYLOAD = b"httptap-e2e gzip payload line\n" * 1000
GZIP_BODY = gzip.compress(GZIP_PAYLOAD, mtime=0)
LARGE_SIZE = 5 * 1024 * 1024
HEAD_CHECK_SIZE = 1234
LOCATION_CRED_PASSWORD = "topsecretlocation"
COOKIE_SECRET = "supersecretcookievalue"
CHUNKS = [b"alpha-", b"beta-", b"gamma-", b"delta"]
MAX_STALL_SECONDS = 30.0


@dataclass
class Recorded:
    method: str
    path: str
    headers: list[tuple[str, str]]
    body: bytes
    client: tuple[Any, ...]
    extra: dict[str, Any] = field(default_factory=dict)

    def header(self, name: str) -> str | None:
        for key, value in self.headers:
            if key.lower() == name.lower():
                return value
        return None

    @property
    def query(self) -> dict[str, list[str]]:
        return parse_qs(urlsplit(self.path).query)


class _RecordingMixin:
    """Shared state: request log, stop flag and quiet error handling."""

    daemon_threads = True
    # On Windows SO_REUSEADDR lets a socket bind a port another socket is listening on.
    allow_reuse_address = sys.platform != "win32"
    block_on_close = False

    def init_state(self) -> None:
        self.records: list[Recorded] = []
        self.twins: list[_RecordingMixin] = []
        self.records_lock = threading.Lock()
        self.stopping = threading.Event()

    def record(self, item: Recorded) -> None:
        with self.records_lock:
            self.records.append(item)

    def find(self, token: str) -> list[Recorded]:
        """Return requests (including those of IPv4/IPv6 twins) whose path, headers or extras contain ``token``."""
        items: list[Recorded] = []
        for server in (self, *self.twins):
            with server.records_lock:
                items.extend(server.records)
        return [r for r in items if token in r.path or any(token in v for _, v in r.headers) or token in str(r.extra)]

    def handle_error(self, request: object, client_address: object) -> None:  # noqa: ARG002
        # Client aborts and rejected handshakes are expected in negative tests.
        return

    def stall(self, seconds: float) -> None:
        deadline = time.monotonic() + min(seconds, MAX_STALL_SECONDS)
        while time.monotonic() < deadline and not self.stopping.is_set():
            time.sleep(0.05)


class HTTPServerV4(_RecordingMixin, ThreadingHTTPServer):
    address_family = socket.AF_INET

    def __init__(self, addr: tuple[str, int], handler: type, *, tls: ssl.SSLContext | None = None) -> None:
        self.init_state()
        self.tls = tls
        self.peer_base: str | None = None
        super().__init__(addr, handler)

    def server_bind(self) -> None:
        # HTTPServer.server_bind calls getfqdn(), which can block on reverse DNS.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


class HTTPServerV6(HTTPServerV4):
    address_family = socket.AF_INET6


class OriginHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "httptap-e2e-origin"
    sys_version = ""
    timeout = 60
    server: HTTPServerV4

    def setup(self) -> None:
        if self.server.tls is not None:
            self.request.settimeout(10)
            self.request = self.server.tls.wrap_socket(self.request, server_side=True)
        super().setup()

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            # socketserver only closes the raw socket, which the TLS wrapper has detached from.
            if self.server.tls is not None:
                self.request.close()

    def log_message(self, *_args: object) -> None:
        return

    def _read_body(self) -> bytes:
        length = self.headers.get("Content-Length")
        if length is not None:
            return self.rfile.read(int(length))
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            body = b""
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip(), 16)
                if size == 0:
                    self.rfile.readline()
                    return body
                body += self.rfile.read(size)
                self.rfile.readline()
        return b""

    def _send(
        self,
        status: int,
        body: bytes = b"",
        headers: list[tuple[str, str]] | None = None,
        *,
        content_type: str | None = "text/plain; charset=utf-8",
        length: int | None = None,
    ) -> None:
        self.send_response(status)
        if content_type and status not in (204, 304):
            self.send_header("Content-Type", content_type)
        for key, value in headers or []:
            self.send_header(key, value)
        if status not in (204, 304):
            self.send_header("Content-Length", str(len(body) if length is None else length))
        self.end_headers()
        if self.command != "HEAD" and status not in (204, 304) and body:
            self.wfile.write(body)

    def _origin(self) -> str:
        scheme = "https" if self.server.tls is not None else "http"
        host = self.headers.get("Host") or "127.0.0.1"
        return f"{scheme}://{host}"

    def _dispatch(self) -> None:  # noqa: C901, PLR0912, PLR0915
        body = self._read_body()
        parts = urlsplit(self.path)
        path = parts.path
        query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        self.server.record(Recorded(self.command, self.path, list(self.headers.items()), body, self.client_address))
        route = path.strip("/").split("/")
        name = route[0] if route else ""

        if name in ("", "ok"):
            self._send(200, b"ok\n")
        elif name == "status":
            code = int(route[1])
            self._send(code, b"" if code in (204, 304) else f"status {code}\n".encode())
        elif name == "redirect":
            n = int(route[1])
            target = f"/redirect/{n - 1}" if n > 1 else "/ok"
            self._send(302, b"", [("Location", target)])
        elif name == "redirect-to":
            self._send(int(query.get("code", "302")), b"", [("Location", query["url"])])
        elif name == "loop":
            self._send(302, b"", [("Location", "/loop")])
        elif name == "relative-redirect":
            self._send(302, b"", [("Location", "ok")])
        elif name == "cross-origin":
            target = f"{self.server.peer_base}/echo?{parts.query}"
            self._send(int(query.get("code", "302")), b"", [("Location", target)])
        elif name == "location-cred":
            host = self.headers.get("Host") or "127.0.0.1"
            scheme = "https" if self.server.tls is not None else "http"
            target = f"{scheme}://alice:{LOCATION_CRED_PASSWORD}@{host}/echo?{parts.query}"
            self._send(302, b"", [("Location", target)])
        elif name == "bad-location":
            kind = query.get("kind", "port")
            target = {
                "port": "http://127.0.0.1:abc/",
                "ipv6": "http://[::1",
                "bigport": "http://127.0.0.1:99999/",
            }[kind]
            self._send(302, b"", [("Location", target)])
        elif name == "gzip":
            self._send(200, GZIP_BODY, [("Content-Encoding", "gzip")])
        elif name == "large":
            self._send_large()
        elif name == "empty":
            self._send(200, b"")
        elif name == "204":
            self._send(204)
        elif name == "304":
            self._send(304, headers=[("ETag", '"e2e"')])
        elif name == "head-check":
            self._send(200, b"h" * HEAD_CHECK_SIZE)
        elif name == "slow-headers":
            self.server.stall(float(query.get("s", "3")))
            self._send(200, b"late\n")
        elif name == "slow-body":
            self.server.stall(float(query.get("h", "0")))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"x")
            self.wfile.flush()
            self.server.stall(float(query.get("s", str(MAX_STALL_SECONDS))))
            self.close_connection = True
        elif name == "trickle":
            n = int(query.get("n", "100"))
            interval = float(query.get("i", "0.3"))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(n))
            self.end_headers()
            for _ in range(n):
                if self.server.stopping.is_set():
                    break
                self.wfile.write(b".")
                self.wfile.flush()
                time.sleep(interval)
            self.close_connection = True
        elif name == "close-mid-body":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "1000")
            self.end_headers()
            self.wfile.write(b"y" * 100)
            self.wfile.flush()
            self.close_connection = True
        elif name == "latin1-header":
            self._send(200, b"latin1\n", [("X-Latin1", "café crème")])
        elif name == "huge-headers":
            count = int(query.get("count", "60"))
            size = int(query.get("size", "150"))
            self._send(200, b"huge\n", [(f"X-Huge-{i:03d}", "v" * size) for i in range(count)])
        elif name == "echo":
            payload = {
                "method": self.command,
                "path": self.path,
                "headers": list(self.headers.items()),
                "body_b64": base64.b64encode(body).decode(),
                "body_len": len(body),
            }
            self._send(200, json.dumps(payload).encode(), content_type="application/json")
        elif name == "set-cookie":
            self._send(200, b"cookie\n", [("Set-Cookie", f"session={COOKIE_SECRET}; Path=/; HttpOnly")])
        elif name == "chunked":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for chunk in CHUNKS:
                self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
        else:
            self._send(404, b"not found\n")

    def _send_large(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(LARGE_SIZE))
        self.end_headers()
        if self.command == "HEAD":
            return
        block = b"L" * 65536
        for _ in range(LARGE_SIZE // len(block)):
            self.wfile.write(block)

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_PATCH = do_OPTIONS = _dispatch  # noqa: N815


def _pump(a: socket.socket, b: socket.socket, stopping: threading.Event) -> int:
    """Relay bytes both ways until either side closes. Returns bytes relayed."""
    sel = selectors.DefaultSelector()
    sel.register(a, selectors.EVENT_READ, b)
    sel.register(b, selectors.EVENT_READ, a)
    total = 0
    try:
        while not stopping.is_set():
            events = sel.select(timeout=0.2)
            for key, _ in events:
                src: socket.socket = key.fileobj  # type: ignore[assignment]
                dst: socket.socket = key.data
                try:
                    data = src.recv(65536)
                except OSError:
                    return total
                if not data:
                    return total
                try:
                    dst.sendall(data)
                except OSError:
                    return total
                total += len(data)
    finally:
        sel.close()
    return total


def _connect_upstream(host_map: dict[str, str], host: str, port: int) -> socket.socket:
    target = host_map.get(host.lower().strip("[]"), host.strip("[]"))
    return socket.create_connection((target, port), timeout=5)


class ProxyServer(HTTPServerV4):
    def __init__(self, addr: tuple[str, int], *, auth: tuple[str, str] | None, host_map: dict[str, str]) -> None:
        self.auth = auth
        self.host_map = host_map
        super().__init__(addr, ProxyHandler)


def _split_authority(authority: str) -> tuple[str, int] | None:
    """Parse host:port like Squid: an IPv6 literal must be bracketed, otherwise the request is rejected."""
    if authority.startswith("["):
        host, sep, port = authority[1:].partition("]:")
        return (host, int(port)) if sep and port.isdigit() else None
    if authority.count(":") != 1:
        return None
    host, _, port = authority.partition(":")
    return (host, int(port)) if port.isdigit() else None


class ProxyHandler(BaseHTTPRequestHandler):
    """Forward proxy (absolute-form requests) and CONNECT tunnel with optional Basic auth."""

    protocol_version = "HTTP/1.1"
    timeout = 60
    server: ProxyServer

    def log_message(self, *_args: object) -> None:
        return

    def _authorized(self) -> bool:
        if self.server.auth is None:
            return True
        expected = base64.b64encode(f"{self.server.auth[0]}:{self.server.auth[1]}".encode()).decode()
        return (self.headers.get("Proxy-Authorization") or "") == f"Basic {expected}"

    def _reject(self, status: int, message: str, extra: list[tuple[str, str]] | None = None) -> None:
        body = message.encode()
        self.send_response(status)
        for key, value in extra or []:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_CONNECT(self) -> None:
        ok = self._authorized()
        self.server.record(
            Recorded("CONNECT", self.path, list(self.headers.items()), b"", self.client_address, {"auth_ok": ok})
        )
        if not ok:
            self._reject(407, "proxy auth required", [("Proxy-Authenticate", 'Basic realm="e2e"')])
            return
        authority = _split_authority(self.path)
        if authority is None:
            self._reject(400, f"invalid CONNECT authority {self.path!r}")
            return
        host, port = authority
        try:
            upstream = _connect_upstream(self.server.host_map, host, port)
        except OSError as exc:
            self._reject(502, f"upstream connect failed: {exc}")
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.wfile.flush()
        upstream.settimeout(None)
        self.connection.settimeout(None)
        try:
            _pump(self.connection, upstream, self.server.stopping)
        finally:
            upstream.close()
            self.close_connection = True

    def _forward(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        ok = self._authorized()
        self.server.record(
            Recorded(self.command, self.path, list(self.headers.items()), body, self.client_address, {"auth_ok": ok})
        )
        if not ok:
            self._reject(407, "proxy auth required", [("Proxy-Authenticate", 'Basic realm="e2e"')])
            return
        if self.path.startswith("http://"):
            hostport = self.path[len("http://") :].split("/", 1)[0].rpartition("@")[2]
            if ":" in hostport and _split_authority(hostport) is None:
                self._reject(400, f"invalid absolute-form authority {hostport!r}")
                return
        parts = urlsplit(self.path)
        if parts.scheme != "http" or not parts.hostname:
            self._reject(400, "absolute-form http:// URL required")
            return
        try:
            upstream = _connect_upstream(self.server.host_map, parts.hostname, parts.port or 80)
        except OSError as exc:
            self._reject(502, f"upstream connect failed: {exc}")
            return
        target = parts.path or "/"
        if parts.query:
            target += f"?{parts.query}"
        lines = [f"{self.command} {target} HTTP/1.1"]
        for key, value in self.headers.items():
            if key.lower() in ("proxy-authorization", "proxy-connection", "connection", "keep-alive"):
                continue
            lines.append(f"{key}: {value}")
        lines.append("Connection: close")
        upstream.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body)
        upstream.settimeout(60)
        try:
            # Either side may hang up mid-response; the relay just stops.
            with suppress(OSError):
                while data := upstream.recv(65536):
                    self.wfile.write(data)
        finally:
            upstream.close()
            self.close_connection = True

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_PATCH = do_OPTIONS = _forward  # noqa: N815


class SocksServer(_RecordingMixin, socketserver.ThreadingTCPServer):
    address_family = socket.AF_INET

    def __init__(self, addr: tuple[str, int], *, auth: tuple[str, str] | None, host_map: dict[str, str]) -> None:
        self.init_state()
        self.auth = auth
        self.host_map = host_map
        self.refuse: set[str] = set()
        super().__init__(addr, SocksHandler)


class SocksHandler(socketserver.BaseRequestHandler):
    server: SocksServer

    def _recv(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                msg = "eof"
                raise ConnectionError(msg)
            data += chunk
        return data

    def handle(self) -> None:  # noqa: C901, PLR0911, PLR0912, PLR0915
        sock: socket.socket = self.request
        sock.settimeout(10)
        info: dict[str, Any] = {}
        try:
            ver, nmethods = self._recv(2)
            if ver != 5:
                return
            methods = set(self._recv(nmethods))
            info["methods"] = sorted(methods)
            if self.server.auth is not None:
                if 2 not in methods:
                    sock.sendall(b"\x05\xff")
                    info["result"] = "no-acceptable-method"
                    return
                sock.sendall(b"\x05\x02")
                _, ulen = self._recv(2)
                user = self._recv(ulen).decode(errors="replace")
                (plen,) = self._recv(1)
                password = self._recv(plen).decode(errors="replace")
                info["user"] = user
                if (user, password) != self.server.auth:
                    sock.sendall(b"\x01\x01")
                    info["result"] = "auth-failed"
                    return
                sock.sendall(b"\x01\x00")
            else:
                if 0 not in methods:
                    sock.sendall(b"\x05\xff")
                    return
                sock.sendall(b"\x05\x00")
            _, cmd, _, atyp = self._recv(4)
            if atyp == 1:
                host = socket.inet_ntop(socket.AF_INET, self._recv(4))
                info["atyp"] = "ipv4"
            elif atyp == 4:
                host = socket.inet_ntop(socket.AF_INET6, self._recv(16))
                info["atyp"] = "ipv6"
            elif atyp == 3:
                (length,) = self._recv(1)
                host = self._recv(length).decode("ascii", errors="replace")
                info["atyp"] = "domain"
            else:
                return
            (port,) = struct.unpack("!H", self._recv(2))
            info.update(host=host, port=port, cmd=cmd)
            if cmd != 1 or host.lower() in self.server.refuse:
                sock.sendall(b"\x05\x05\x00\x01" + b"\x00" * 6)
                info["result"] = "refused"
                return
            try:
                upstream = _connect_upstream(self.server.host_map, host, port)
            except OSError:
                sock.sendall(b"\x05\x05\x00\x01" + b"\x00" * 6)
                info["result"] = "connect-failed"
                return
            sock.sendall(b"\x05\x00\x00\x01" + b"\x00" * 6)
            info["result"] = "ok"
            sock.settimeout(None)
            upstream.settimeout(None)
            try:
                _pump(sock, upstream, self.server.stopping)
            finally:
                upstream.close()
        except (OSError, ConnectionError, ValueError):
            info.setdefault("result", "aborted")
        finally:
            self.server.record(
                Recorded("SOCKS", f"{info.get('host')}:{info.get('port')}", [], b"", self.client_address, info)
            )


class CollectorServer(HTTPServerV4):
    def __init__(self, addr: tuple[str, int], *, fail_status: int | None = None) -> None:
        self.fail_status = fail_status
        self.spans: list[dict[str, Any]] = []
        super().__init__(addr, CollectorHandler)


class CollectorHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 30
    server: CollectorServer

    def log_message(self, *_args: object) -> None:
        return

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = gzip.decompress(raw) if (self.headers.get("Content-Encoding") or "") == "gzip" else raw
        self.server.record(Recorded("POST", self.path, list(self.headers.items()), body, self.client_address))
        if self.server.fail_status is not None:
            payload = b"collector failure"
            self.send_response(self.server.fail_status)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        with self.server.records_lock:
            for resource_spans in request.resource_spans:
                for scope_spans in resource_spans.scope_spans:
                    for span in scope_spans.spans:
                        self.server.spans.append(_span_to_dict(span))
        payload = ExportTraceServiceResponse().SerializeToString()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _any_value(value: AnyValue) -> object:
    kind = value.WhichOneof("value")
    return getattr(value, kind) if kind else None


def _span_to_dict(span: Span) -> dict[str, Any]:
    return {
        "name": span.name,
        "trace_id": span.trace_id.hex(),
        "span_id": span.span_id.hex(),
        "parent_span_id": span.parent_span_id.hex(),
        "start": span.start_time_unix_nano,
        "end": span.end_time_unix_nano,
        "attributes": {a.key: _any_value(a.value) for a in span.attributes},
        "status_code": span.status.code,
        "status_message": span.status.message,
        "raw": span.SerializeToString(),
    }


def start(server: _ServerT) -> _ServerT:
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
    thread.start()
    return server


def stop(server: socketserver.BaseServer) -> None:
    stopping = getattr(server, "stopping", None)
    if stopping is not None:
        stopping.set()
    server.shutdown()
    server.server_close()


def tls_context(cert: str, key: str) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert, key)
    # Only HTTP/1.1 is implemented server-side; h2 offered by the client is declined.
    ctx.set_alpn_protocols(["http/1.1"])
    return ctx


def bind_v6_same_port(port: int, handler_factory: Callable[[tuple[str, int]], _ServerT]) -> _ServerT | None:
    """Try to bind an IPv6 twin on ::1 using the same port number as an IPv4 server."""
    try:
        return handler_factory(("::1", port))
    except OSError:
        return None


class DeadPort:
    """A port with no listener, so connections are refused.

    A bound-but-not-listening socket is not enough: macOS silently drops the SYN
    and the client times out instead of getting a refusal.
    """

    def __init__(self, host: str = "127.0.0.1") -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, 0))
        self.port = sock.getsockname()[1]
        sock.close()
