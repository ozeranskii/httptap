"""End-to-end TLS handshake against a local self-signed server."""

from __future__ import annotations

import socket
import ssl
import threading
import time
from contextlib import suppress
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from httptap.http_client import make_request
from httptap.utils import UTC

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        del format, args


@pytest.fixture
def self_signed_server(tmp_path: Path) -> Iterator[int]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "self-signed.test")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(0xC0FFEE)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("self-signed.test")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_path, key_path)
    server = HTTPServer(("127.0.0.1", 0), _OkHandler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_insecure_request_reports_peer_certificate(self_signed_server: int) -> None:
    """With verification disabled the certificate still comes from the live connection."""
    _timing, network, response = make_request(
        f"https://127.0.0.1:{self_signed_server}/",
        timeout=5.0,
        verify_ssl=False,
        http2=False,
    )

    assert response.status == 200
    assert network.tls_verified is False
    assert network.cert_cn == "self-signed.test"
    assert network.cert_sans == ["self-signed.test"]
    assert network.cert_issuer == "self-signed.test"
    assert network.cert_serial == "C0FFEE"
    assert network.cert_days_left is not None
    assert network.cert_days_left > 0


_TUNNEL_DELAY_SECONDS = 0.2


def _relay(source: socket.socket, target: socket.socket) -> None:
    with suppress(OSError):
        while data := source.recv(65536):
            target.sendall(data)
    with suppress(OSError):
        target.shutdown(socket.SHUT_WR)


def _serve_connect_tunnel(listener: socket.socket) -> None:
    client, _address = listener.accept()
    with client:
        request = b""
        while b"\r\n\r\n" not in request:
            request += client.recv(4096)
        authority = request.split(b" ", 2)[1].decode()
        host, _, port = authority.rpartition(":")
        with socket.create_connection((host, int(port))) as upstream:
            time.sleep(_TUNNEL_DELAY_SECONDS)  # proxy-side latency before the tunnel is up
            client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            to_upstream = threading.Thread(target=_relay, args=(client, upstream), daemon=True)
            to_upstream.start()
            _relay(upstream, client)
            to_upstream.join(timeout=2)


@pytest.fixture
def connect_proxy() -> Iterator[int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    thread = threading.Thread(target=_serve_connect_tunnel, args=(listener,), daemon=True)
    thread.start()
    try:
        yield listener.getsockname()[1]
    finally:
        listener.close()
        thread.join(timeout=2)


def test_connect_tunnel_setup_counts_as_connect_time(self_signed_server: int, connect_proxy: int) -> None:
    """The CONNECT round-trip belongs to connection setup, not to server wait time."""
    timing, network, response = make_request(
        f"https://127.0.0.1:{self_signed_server}/",
        timeout=5.0,
        verify_ssl=False,
        http2=False,
        proxy=f"http://127.0.0.1:{connect_proxy}",
    )

    assert response.status == 200
    assert network.proxy_url == f"http://127.0.0.1:{connect_proxy}"
    assert timing.is_estimated is False
    assert timing.connect_ms >= _TUNNEL_DELAY_SECONDS * 1000
    assert timing.wait_ms < _TUNNEL_DELAY_SECONDS * 1000
