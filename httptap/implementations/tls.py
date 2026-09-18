"""TLS inspection implementations."""

from __future__ import annotations

import socket
import ssl
from contextlib import closing

from httptap.constants import TLS_PROBE_MAX_TIMEOUT_SECONDS
from httptap.models import NetworkInfo
from httptap.tls_inspector import apply_certificate_info, extract_tls_info, extract_unverified_certificate_info
from httptap.utils import create_ssl_context


class TLSInspectionError(Exception):
    """Raised when TLS inspection fails.

    Signals that a dedicated TLS probe could not complete, for example because
    the TCP connection failed or the TLS handshake could not be established.
    Wraps the originating exception as its cause.
    """


class SocketTLSInspector:
    """TLS inspector that performs a dedicated TLS handshake using ``ssl``.

    Opens a short-lived TCP connection, performs a TLS handshake, and extracts
    the negotiated version, cipher suite, and leaf-certificate details into a
    :class:`~httptap.models.NetworkInfo`. Implements the
    :class:`~httptap.interfaces.TLSInspector` protocol and is the default
    inspector used by the analyzer.
    """

    __slots__ = ("_ca_bundle_path", "_legacy_tls", "_verify")

    def __init__(
        self,
        *,
        verify: bool = True,
        ca_bundle_path: str | None = None,
        legacy_tls: bool = True,
    ) -> None:
        """Initialize inspector with optional verification toggle and custom CA bundle.

        Args:
            verify: Whether to verify TLS certificates.
            ca_bundle_path: Path to custom CA certificate bundle (PEM format).
                Only used when verify is True. If None, uses system CA bundle.
            legacy_tls: Whether an unverified probe may use legacy TLS settings.

        """
        self._verify = verify
        self._ca_bundle_path = ca_bundle_path
        self._legacy_tls = legacy_tls

    def inspect(self, host: str, port: int, timeout: float, *, connect_host: str | None = None) -> NetworkInfo:
        """Inspect TLS connection and extract metadata.

        Args:
            host: Hostname to connect to, also used for SNI.
            port: Port number (typically 443 for HTTPS).
            timeout: Connection timeout in seconds. The probe is additionally
                capped by ``TLS_PROBE_MAX_TIMEOUT_SECONDS``.
            connect_host: Address for the TCP connection. When provided, the
                original ``host`` remains the SNI hostname.

        Returns:
            A NetworkInfo populated with the resolved IP, negotiated TLS
            version and cipher, and leaf-certificate details when available.

        Raises:
            TLSInspectionError: If the connection or TLS handshake fails.
        """
        network_info = NetworkInfo()
        network_info.tls_verified = self._verify
        probe_timeout = min(timeout, TLS_PROBE_MAX_TIMEOUT_SECONDS)

        try:
            connection = socket.create_connection((connect_host or host, port), timeout=probe_timeout)
            with closing(connection) as raw_sock:
                self._populate_network_info(raw_sock, network_info)

                if not self._verify and not self._legacy_tls:
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                else:
                    context = create_ssl_context(verify_ssl=self._verify, ca_bundle_path=self._ca_bundle_path)
                with context.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
                    tls_version, cipher_suite, cert_info = extract_tls_info(tls_sock)
                    if cert_info is None and not self._verify:
                        cert_info = extract_unverified_certificate_info(tls_sock)
                    network_info.tls_version = tls_version
                    network_info.tls_cipher = cipher_suite

                    if cert_info:
                        apply_certificate_info(network_info, cert_info)

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
