"""TLS inspection implementations."""

from __future__ import annotations

import socket
from contextlib import closing

from httptap.constants import TLS_PROBE_MAX_TIMEOUT_SECONDS
from httptap.models import NetworkInfo
from httptap.tls_inspector import extract_tls_info
from httptap.utils import create_ssl_context


class TLSInspectionError(Exception):
    """Raised when TLS inspection fails."""


class SocketTLSInspector:
    """TLS inspector that performs a dedicated TLS handshake using ``ssl``."""

    __slots__ = ("_verify",)

    def __init__(self, *, verify: bool = True) -> None:
        """Initialize inspector with optional verification toggle."""
        self._verify = verify

    def inspect(self, host: str, port: int, timeout: float) -> NetworkInfo:
        """Inspect TLS connection and extract metadata."""
        network_info = NetworkInfo()
        network_info.tls_verified = self._verify
        probe_timeout = min(timeout, TLS_PROBE_MAX_TIMEOUT_SECONDS)

        try:
            connection = socket.create_connection((host, port), timeout=probe_timeout)
            with closing(connection) as raw_sock:
                self._populate_network_info(raw_sock, network_info)

                # Diagnostic tool: intentionally allows TLSv1.0+ to inspect legacy servers.
                # This is NOT a security issue because httptap is used for troubleshooting,
                # not for transmitting sensitive data in production.
                context = create_ssl_context(verify_ssl=self._verify)
                with context.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
                    tls_version, cipher_suite, cert_info = extract_tls_info(tls_sock)
                    network_info.tls_version = tls_version
                    network_info.tls_cipher = cipher_suite

                    if cert_info:
                        network_info.cert_cn = cert_info.common_name
                        network_info.cert_days_left = cert_info.days_until_expiry

        except Exception as exc:
            msg = f"TLS inspection failed for {host}:{port}: {exc}"
            raise TLSInspectionError(
                msg,
            ) from exc

        return network_info

    def _populate_network_info(
        self,
        raw_sock: socket.socket,
        network_info: NetworkInfo,
    ) -> None:
        try:
            peer = raw_sock.getpeername()
            if peer:
                ip = str(peer[0]) if isinstance(peer, tuple) else str(peer)
                if ip:
                    network_info.ip = ip
                    network_info.ip_family = self._family_to_label(raw_sock.family)
        except OSError:  # pragma: no cover - best effort
            pass

    @staticmethod
    def _family_to_label(family: int) -> str:
        if family == socket.AF_INET6:
            return "IPv6"
        if family == socket.AF_INET:
            return "IPv4"
        return f"AF_{family}"
