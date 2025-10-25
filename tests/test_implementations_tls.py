"""Unit tests for TLS inspector implementation."""

from __future__ import annotations

import socket
import ssl
from typing import TYPE_CHECKING

import pytest

from httptap.implementations.tls import SocketTLSInspector, TLSInspectionError
from httptap.models import NetworkInfo

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class TestSocketTLSInspector:
    """Test suite for SocketTLSInspector."""

    def test_inspect_success_with_full_info(self, mocker: MockerFixture) -> None:
        """Test successful TLS inspection with complete information."""
        inspector = SocketTLSInspector()

        # Mock socket
        mock_socket = mocker.MagicMock(spec=socket.socket)
        mock_socket.getpeername.return_value = ("93.184.216.34", 443)
        mock_socket.family = socket.AF_INET

        # Mock TLS socket
        mock_tls_socket = mocker.MagicMock(spec=ssl.SSLSocket)

        # Mock certificate info
        mock_cert_info = mocker.Mock()
        mock_cert_info.common_name = "example.com"
        mock_cert_info.days_until_expiry = 90

        # Patch dependencies
        mocker.patch("socket.create_connection", return_value=mock_socket)
        mock_context = mocker.MagicMock()
        mock_context.wrap_socket.return_value.__enter__ = mocker.Mock(
            return_value=mock_tls_socket,
        )
        mock_context.wrap_socket.return_value.__exit__ = mocker.Mock(return_value=False)
        mocker.patch("ssl.create_default_context", return_value=mock_context)
        mocker.patch(
            "httptap.implementations.tls.extract_tls_info",
            return_value=("TLSv1.3", "TLS_AES_256_GCM_SHA384", mock_cert_info),
        )

        network_info = inspector.inspect("example.com", 443, 5.0)

        assert network_info.ip == "93.184.216.34"
        assert network_info.ip_family == "IPv4"
        assert network_info.tls_version == "TLSv1.3"
        assert network_info.tls_cipher == "TLS_AES_256_GCM_SHA384"
        assert network_info.cert_cn == "example.com"
        assert network_info.cert_days_left == 90

    def test_inspect_ipv6_address(self, mocker: MockerFixture) -> None:
        """Test TLS inspection with IPv6 address."""
        inspector = SocketTLSInspector()

        mock_socket = mocker.MagicMock(spec=socket.socket)
        mock_socket.getpeername.return_value = (
            "2606:2800:220:1:248:1893:25c8:1946",
            443,
            0,
            0,
        )
        mock_socket.family = socket.AF_INET6

        mock_tls_socket = mocker.MagicMock(spec=ssl.SSLSocket)

        mocker.patch("socket.create_connection", return_value=mock_socket)
        mock_context = mocker.MagicMock()
        mock_context.wrap_socket.return_value.__enter__ = mocker.Mock(
            return_value=mock_tls_socket,
        )
        mock_context.wrap_socket.return_value.__exit__ = mocker.Mock(return_value=False)
        mocker.patch("ssl.create_default_context", return_value=mock_context)
        mocker.patch(
            "httptap.implementations.tls.extract_tls_info",
            return_value=("TLSv1.3", "TLS_AES_128_GCM_SHA256", None),
        )

        network_info = inspector.inspect("example.com", 443, 5.0)

        assert network_info.ip == "2606:2800:220:1:248:1893:25c8:1946"
        assert network_info.ip_family == "IPv6"

    def test_inspect_without_certificate_info(self, mocker: MockerFixture) -> None:
        """Test TLS inspection when certificate info is not available."""
        inspector = SocketTLSInspector()

        mock_socket = mocker.MagicMock(spec=socket.socket)
        mock_socket.getpeername.return_value = ("1.2.3.4", 443)
        mock_socket.family = socket.AF_INET

        mock_tls_socket = mocker.MagicMock(spec=ssl.SSLSocket)

        mocker.patch("socket.create_connection", return_value=mock_socket)
        mock_context = mocker.MagicMock()
        mock_context.wrap_socket.return_value.__enter__ = mocker.Mock(
            return_value=mock_tls_socket,
        )
        mock_context.wrap_socket.return_value.__exit__ = mocker.Mock(return_value=False)
        mocker.patch("ssl.create_default_context", return_value=mock_context)
        mocker.patch(
            "httptap.implementations.tls.extract_tls_info",
            return_value=("TLSv1.2", "ECDHE-RSA-AES128-GCM-SHA256", None),
        )

        network_info = inspector.inspect("example.com", 443, 5.0)

        assert network_info.tls_version == "TLSv1.2"
        assert network_info.tls_cipher == "ECDHE-RSA-AES128-GCM-SHA256"
        assert network_info.cert_cn is None
        assert network_info.cert_days_left is None

    def test_inspect_connection_failure_raises_error(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that connection failure raises TLSInspectionError."""
        inspector = SocketTLSInspector()

        mocker.patch(
            "socket.create_connection",
            side_effect=TimeoutError("Connection timed out"),
        )

        with pytest.raises(
            TLSInspectionError,
            match=r"TLS inspection failed.*timed out",
        ):
            inspector.inspect("unreachable.example.com", 443, 1.0)

    def test_inspect_ssl_error_raises_inspection_error(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that SSL errors are wrapped in TLSInspectionError."""
        inspector = SocketTLSInspector()

        mock_socket = mocker.MagicMock(spec=socket.socket)
        mock_socket.getpeername.return_value = ("1.2.3.4", 443)
        mock_socket.family = socket.AF_INET

        mocker.patch("socket.create_connection", return_value=mock_socket)
        mock_context = mocker.MagicMock()
        mock_context.wrap_socket.side_effect = ssl.SSLError("SSL handshake failed")
        mocker.patch("ssl.create_default_context", return_value=mock_context)

        with pytest.raises(
            TLSInspectionError,
            match=r"TLS inspection failed.*handshake",
        ):
            inspector.inspect("bad-ssl.example.com", 443, 5.0)

    def test_populate_network_info_handles_empty_peer(
        self,
        mocker: MockerFixture,
    ) -> None:
        inspector = SocketTLSInspector()
        network_info = NetworkInfo()

        sock = mocker.MagicMock(spec=socket.socket)
        sock.getpeername.return_value = ()

        inspector._populate_network_info(sock, network_info)

        assert network_info.ip is None
        assert network_info.ip_family is None

    def test_populate_network_info_skips_blank_ip(
        self,
        mocker: MockerFixture,
    ) -> None:
        inspector = SocketTLSInspector()
        network_info = NetworkInfo()

        sock = mocker.MagicMock(spec=socket.socket)
        sock.family = socket.AF_UNIX
        sock.getpeername.return_value = ("", 0)

        inspector._populate_network_info(sock, network_info)

        assert network_info.ip is None
        assert network_info.ip_family is None

    def test_family_to_label_returns_fallback(self) -> None:
        label = SocketTLSInspector._family_to_label(9999)
        assert label == "AF_9999"

    def test_inspect_respects_timeout_limit(self, mocker: MockerFixture) -> None:
        """Test that inspector caps timeout at TLS_PROBE_MAX_TIMEOUT_SECONDS."""
        inspector = SocketTLSInspector()

        mock_socket = mocker.MagicMock(spec=socket.socket)
        mock_socket.getpeername.return_value = ("1.2.3.4", 443)
        mock_socket.family = socket.AF_INET
        mock_tls_socket = mocker.MagicMock(spec=ssl.SSLSocket)

        mock_create = mocker.patch("socket.create_connection", return_value=mock_socket)
        mock_context = mocker.MagicMock()
        mock_context.wrap_socket.return_value.__enter__ = mocker.Mock(
            return_value=mock_tls_socket,
        )
        mock_context.wrap_socket.return_value.__exit__ = mocker.Mock(return_value=False)
        mocker.patch("ssl.create_default_context", return_value=mock_context)
        mocker.patch(
            "httptap.implementations.tls.extract_tls_info",
            return_value=("TLSv1.3", "cipher", None),
        )

        # Request with very long timeout
        inspector.inspect("example.com", 443, 100.0)

        # Should cap at 5 seconds (TLS_PROBE_MAX_TIMEOUT_SECONDS)
        mock_create.assert_called_once()
        called_timeout = mock_create.call_args[1]["timeout"]
        assert called_timeout == 5.0

    def test_inspect_uses_provided_timeout_when_below_max(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that inspector uses provided timeout when below maximum."""
        inspector = SocketTLSInspector()

        mock_socket = mocker.MagicMock(spec=socket.socket)
        mock_socket.getpeername.return_value = ("1.2.3.4", 443)
        mock_socket.family = socket.AF_INET
        mock_tls_socket = mocker.MagicMock(spec=ssl.SSLSocket)

        mock_create = mocker.patch("socket.create_connection", return_value=mock_socket)
        mock_context = mocker.MagicMock()
        mock_context.wrap_socket.return_value.__enter__ = mocker.Mock(
            return_value=mock_tls_socket,
        )
        mock_context.wrap_socket.return_value.__exit__ = mocker.Mock(return_value=False)
        mocker.patch("ssl.create_default_context", return_value=mock_context)
        mocker.patch(
            "httptap.implementations.tls.extract_tls_info",
            return_value=("TLSv1.3", "cipher", None),
        )

        # Request with timeout below max
        inspector.inspect("example.com", 443, 2.0)

        # Should use provided timeout
        mock_create.assert_called_once()
        called_timeout = mock_create.call_args[1]["timeout"]
        assert called_timeout == 2.0

    def test_populate_network_info_handles_getpeername_failure(self) -> None:
        """Test that _populate_network_info handles getpeername() failures."""
        inspector = SocketTLSInspector()

        # Create a real mock socket that raises OSError
        import unittest.mock

        mock_socket = unittest.mock.MagicMock(spec=socket.socket)
        mock_socket.getpeername.side_effect = OSError("Socket not connected")
        mock_socket.family = socket.AF_INET

        network_info = NetworkInfo()

        # Should not raise, just skip IP population
        inspector._populate_network_info(mock_socket, network_info)

        # IP should remain None
        assert network_info.ip is None
        assert network_info.ip_family is None

    @pytest.mark.parametrize(
        ("family", "expected"),
        [
            (socket.AF_INET, "IPv4"),
            (socket.AF_INET6, "IPv6"),
            (42, "AF_42"),
        ],
    )
    def test_family_to_label(self, family: int, expected: str) -> None:
        """Test _family_to_label correctly identifies address families."""
        inspector = SocketTLSInspector()
        assert inspector._family_to_label(family) == expected

    def test_inspect_uses_server_hostname_for_sni(self, mocker: MockerFixture) -> None:
        """Test that inspector provides server_hostname for SNI."""
        inspector = SocketTLSInspector()

        mock_socket = mocker.MagicMock(spec=socket.socket)
        mock_socket.getpeername.return_value = ("1.2.3.4", 443)
        mock_socket.family = socket.AF_INET
        mock_tls_socket = mocker.MagicMock(spec=ssl.SSLSocket)

        mocker.patch("socket.create_connection", return_value=mock_socket)
        mock_context = mocker.MagicMock()
        mock_context.wrap_socket.return_value.__enter__ = mocker.Mock(
            return_value=mock_tls_socket,
        )
        mock_context.wrap_socket.return_value.__exit__ = mocker.Mock(return_value=False)
        mocker.patch("ssl.create_default_context", return_value=mock_context)
        mocker.patch(
            "httptap.implementations.tls.extract_tls_info",
            return_value=("TLSv1.3", "cipher", None),
        )

        inspector.inspect("example.com", 443, 5.0)

        # Verify wrap_socket was called with server_hostname
        mock_context.wrap_socket.assert_called_once()
        call_kwargs = mock_context.wrap_socket.call_args[1]
        assert call_kwargs["server_hostname"] == "example.com"
