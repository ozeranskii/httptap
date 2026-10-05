"""End-to-end TLS handshake against a local self-signed server."""

from __future__ import annotations

import ssl
import threading
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
