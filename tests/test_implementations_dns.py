"""Unit tests for DNS resolver implementation."""

from __future__ import annotations

import socket
import threading
import time
from typing import TYPE_CHECKING

import pytest

from httptap.implementations import dns
from httptap.implementations.dns import DNSResolutionError, SystemDNSResolver

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class TestSystemDNSResolver:
    """Test suite for SystemDNSResolver."""

    def test_resolve_ipv4_success(self, mocker: MockerFixture) -> None:
        """Test successful IPv4 DNS resolution."""
        resolver = SystemDNSResolver()

        # Mock getaddrinfo to return IPv4 address
        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]

        ip, ip_family, elapsed_ms = resolver.resolve("example.com", 443, 5.0)

        assert ip == "93.184.216.34"
        assert ip_family == "IPv4"
        assert elapsed_ms >= 0.0
        mock_getaddrinfo.assert_called_once_with(
            "example.com",
            443,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )

    def test_resolve_ipv6_success(self, mocker: MockerFixture) -> None:
        """Test successful IPv6 DNS resolution."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0),
            ),
        ]

        ip, ip_family, elapsed_ms = resolver.resolve("example.com", 443, 5.0)

        assert ip == "2606:2800:220:1:248:1893:25c8:1946"
        assert ip_family == "IPv6"
        assert elapsed_ms >= 0.0

    def test_resolve_timeout_raises_error(self, mocker: MockerFixture) -> None:
        """Test that DNS resolution timeout raises DNSResolutionError."""
        resolver = SystemDNSResolver()

        # Mock getaddrinfo to simulate slow DNS that times out
        def slow_dns(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
            time.sleep(10)  # Sleep longer than timeout
            return []

        mocker.patch("socket.getaddrinfo", side_effect=slow_dns)

        start = time.perf_counter()
        with pytest.raises(DNSResolutionError, match="DNS resolution timed out"):
            resolver.resolve("slow.example.com", 443, 0.1)
        duration = time.perf_counter() - start
        assert duration < 0.5  # Should not wait for worker thread to finish

    def test_resolve_gaierror_raises_dns_error(self, mocker: MockerFixture) -> None:
        """Test that socket.gaierror is converted to DNSResolutionError."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.side_effect = socket.gaierror(
            socket.EAI_NONAME,
            "Name or service not known",
        )

        with pytest.raises(DNSResolutionError, match="DNS resolution failed"):
            resolver.resolve("invalid.example.com", 443, 5.0)

    def test_resolve_unexpected_error_raises_dns_error(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that unexpected errors are wrapped in DNSResolutionError."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(DNSResolutionError, match="Unexpected error"):
            resolver.resolve("error.example.com", 443, 5.0)

    def test_resolve_empty_result_raises_error(self, mocker: MockerFixture) -> None:
        """Test that empty DNS result raises DNSResolutionError."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = []

        with pytest.raises(DNSResolutionError, match="No address records"):
            resolver.resolve("empty.example.com", 443, 5.0)

    def test_resolve_none_result_raises_error(self, mocker: MockerFixture) -> None:
        """Test that None from getaddrinfo raises DNSResolutionError."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = None

        with pytest.raises(DNSResolutionError, match="No address records"):
            resolver.resolve("none.example.com", 443, 5.0)

    def test_resolve_missing_ip_raises_error(self, mocker: MockerFixture) -> None:
        """Test that missing IP in sockaddr raises DNSResolutionError."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        # Return result with empty sockaddr
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ()),
        ]

        with pytest.raises(DNSResolutionError, match="Failed to extract IP"):
            resolver.resolve("malformed.example.com", 443, 5.0)

    def test_resolve_handles_empty_entries(self, mocker: MockerFixture) -> None:
        """Empty addrinfo entries should trigger No address records."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = [(), ()]

        with pytest.raises(DNSResolutionError, match="No address records"):
            resolver.resolve("empty-set.example.com", 443, 5.0)

    def test_extract_sockaddr_returns_empty_tuple(self) -> None:
        """_extract_sockaddr should return empty tuple when none present."""
        assert dns._extract_sockaddr(["not-a-tuple", 123]) == ()

    def test_normalize_addrinfo_covers_edge_cases(self) -> None:
        """_normalize_addrinfo handles empty and non-int family entries."""
        entries = [
            (),
            ("not-a-family", "ignored", ("203.0.113.5", 80)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 443, 0, 0)),
        ]

        records = dns._normalize_addrinfo(entries)

        # First entry skipped, remaining two normalized with graceful defaults.
        assert len(records) == 2
        assert records[0].family == socket.AF_UNSPEC
        assert records[0].sockaddr == ("203.0.113.5", 80)
        assert records[1].family == int(socket.AF_INET6)
        assert records[1].sockaddr == ("::1", 443, 0, 0)

    def test_resolve_handles_short_addrinfo_tuple(self, mocker: MockerFixture) -> None:
        """Some platforms omit the canonname field; ensure we handle flexible tuples."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, ("198.51.100.10", 443)),
        ]

        ip, ip_family, elapsed_ms = resolver.resolve("short.example.com", 443, 5.0)

        assert ip == "198.51.100.10"
        assert ip_family == "IPv4"
        assert elapsed_ms >= 0.0

    @pytest.mark.parametrize(
        ("family", "expected"),
        [
            (socket.AF_INET, "IPv4"),
            (socket.AF_INET6, "IPv6"),
            (99, "AF_99"),
        ],
    )
    def test_family_to_label(self, family: int, expected: str) -> None:
        """Test _family_to_label correctly identifies address families."""
        resolver = SystemDNSResolver()
        assert resolver._family_to_label(family) == expected

    def test_resolve_measures_timing(self, mocker: MockerFixture) -> None:
        """Test that resolver measures elapsed time correctly."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 443)),
        ]

        _, _, elapsed_ms = resolver.resolve("example.com", 443, 5.0)

        # Elapsed time should be measured (even if very small)
        assert elapsed_ms >= 0.0
        # Should complete quickly for mocked call
        assert elapsed_ms < 1000.0  # Less than 1 second

    def test_resolve_thread_safety(self, mocker: MockerFixture) -> None:
        """Test that resolver uses threading for timeout support."""
        resolver = SystemDNSResolver()

        thread_started = threading.Event()

        def track_thread(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
            thread_started.set()
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 443))]

        mocker.patch("socket.getaddrinfo", side_effect=track_thread)

        resolver.resolve("example.com", 443, 5.0)

        # Verify that getaddrinfo was called (implicitly in a thread)
        assert thread_started.is_set()

    def test_resolve_with_non_standard_port(self, mocker: MockerFixture) -> None:
        """Test DNS resolution with non-standard port."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 8443)),
        ]

        ip, ip_family, elapsed_ms = resolver.resolve("example.com", 8443, 5.0)

        assert ip == "93.184.216.34"
        assert ip_family == "IPv4"
        assert elapsed_ms >= 0.0
        mock_getaddrinfo.assert_called_once_with(
            "example.com",
            8443,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )

    def test_resolve_ipv4_preferred_over_ipv6(self, mocker: MockerFixture) -> None:
        """Test that first address is returned when both IPv4 and IPv6 available."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        # Return both IPv4 and IPv6, IPv4 first
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0),
            ),
        ]

        ip, ip_family, elapsed_ms = resolver.resolve("example.com", 443, 5.0)

        # Should return the first address (IPv4)
        assert ip == "93.184.216.34"
        assert ip_family == "IPv4"
        assert elapsed_ms >= 0.0

    def test_resolve_ipv6_when_only_available(self, mocker: MockerFixture) -> None:
        """Test that IPv6 is returned when it's the only available address."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        # Return only IPv6
        mock_getaddrinfo.return_value = [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0),
            ),
        ]

        ip, ip_family, elapsed_ms = resolver.resolve("example.com", 443, 5.0)

        assert ip == "2606:2800:220:1:248:1893:25c8:1946"
        assert ip_family == "IPv6"
        assert elapsed_ms >= 0.0

    def test_resolve_with_very_short_timeout(self, mocker: MockerFixture) -> None:
        """Test DNS resolution with very short timeout."""
        resolver = SystemDNSResolver()

        def slow_dns(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
            time.sleep(0.5)  # Sleep longer than timeout
            return []

        mocker.patch("socket.getaddrinfo", side_effect=slow_dns)

        with pytest.raises(DNSResolutionError, match="DNS resolution timed out"):
            resolver.resolve("slow.example.com", 443, 0.01)  # 10ms timeout

    def test_resolve_localhost(self, mocker: MockerFixture) -> None:
        """Test DNS resolution for localhost."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]

        ip, ip_family, elapsed_ms = resolver.resolve("localhost", 443, 5.0)

        assert ip == "127.0.0.1"
        assert ip_family == "IPv4"
        assert elapsed_ms >= 0.0

    def test_resolve_with_multiple_addresses_same_family(self, mocker: MockerFixture) -> None:
        """Test that first address is returned when multiple addresses of same family exist."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        # Return multiple IPv4 addresses
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.35", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.36", 443)),
        ]

        ip, ip_family, elapsed_ms = resolver.resolve("example.com", 443, 5.0)

        # Should return the first address
        assert ip == "93.184.216.34"
        assert ip_family == "IPv4"
        assert elapsed_ms >= 0.0

    def test_resolve_handles_connection_refused_error(self, mocker: MockerFixture) -> None:
        """Test handling of connection refused during DNS resolution."""
        resolver = SystemDNSResolver()

        mock_getaddrinfo = mocker.patch("socket.getaddrinfo")
        mock_getaddrinfo.side_effect = socket.gaierror(
            socket.EAI_AGAIN,
            "Temporary failure in name resolution",
        )

        with pytest.raises(DNSResolutionError, match="DNS resolution failed"):
            resolver.resolve("unreachable.example.com", 443, 5.0)
