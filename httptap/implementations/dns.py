"""DNS resolver implementations."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from ipaddress import IPv6Address, ip_address
from typing import Any, cast

import httpx

from httptap.constants import MS_IN_SECOND
from httptap.utils import format_address_family

AddrInfo = tuple[Any, ...]


@dataclass(frozen=True)
class AddressRecord:
    """Normalized representation of socket.getaddrinfo output."""

    family: int
    sockaddr: tuple[Any, ...]


def _normalize_addrinfo(addr_info: Iterable[AddrInfo]) -> list[AddressRecord]:
    """Normalize raw getaddrinfo output into AddressRecord objects."""
    records: list[AddressRecord] = []
    iterable = addr_info if isinstance(addr_info, Sequence) else tuple(addr_info)

    for entry in iterable:
        if not entry:
            continue

        family_obj = entry[0]
        if isinstance(family_obj, socket.AddressFamily):
            family = int(family_obj)
        elif isinstance(family_obj, int):
            family = family_obj
        else:
            family = socket.AF_UNSPEC

        sockaddr = _extract_sockaddr(entry)
        records.append(AddressRecord(family=family, sockaddr=sockaddr))
    return records


def _extract_sockaddr(entry: Iterable[Any]) -> tuple[Any, ...]:
    """Extract the first tuple-valued element from the entry (typically sockaddr)."""
    for item in reversed(tuple(entry)):
        if isinstance(item, tuple):
            return item
    return ()


def _override_key(host: str) -> str:
    """Return ``host`` in the IDNA 2008 A-label form httpx sends as Host and SNI.

    ``--resolve`` entries and lookups are compared in this form, so a U-label
    and its A-label name the same host. Names httpx cannot encode keep their
    lowercased spelling.
    """
    try:
        return httpx.URL(scheme="http", host=host).raw_host.decode("ascii")
    except httpx.InvalidURL:
        return host.lower()


class DNSResolutionError(Exception):
    """Raised when DNS resolution fails.

    Signals that a hostname could not be resolved to an IP address, whether
    due to a lookup failure, a timeout, or an empty address list. Wraps the
    originating ``socket`` error where one is available.
    """


class SystemDNSResolver:
    """DNS resolver using the system getaddrinfo implementation.

    Resolves hostnames with :func:`socket.getaddrinfo` on a background thread so
    the lookup can be bounded by a timeout. It implements the
    :class:`~httptap.interfaces.DNSResolver` protocol and is the default resolver
    used by the analyzer.
    """

    __slots__ = ("_family",)

    def __init__(self, family: int = socket.AF_UNSPEC) -> None:
        """Initialize a resolver restricted to an optional address family."""
        self._family = family

    def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
        """Resolve host and return IP, family label, and elapsed milliseconds.

        Args:
            host: Hostname to resolve (e.g., "example.com").
            port: Port number used to hint the address lookup.
            timeout: Maximum time to wait for resolution, in seconds.

        Returns:
            Tuple of ``(ip_address, ip_family, elapsed_ms)`` where ``ip_family``
            is one of ``"IPv4"``, ``"IPv6"``, or ``"AF_<num>"`` for other
            address families, and ``elapsed_ms`` is the resolution time in
            milliseconds.

        Raises:
            DNSResolutionError: If resolution times out, the lookup fails, or no
                usable address record is returned.
        """
        addresses, elapsed_ms = self.resolve_all(host, port, timeout)
        ip, ip_family = addresses[0]
        return ip, ip_family, elapsed_ms

    def resolve_all(self, host: str, port: int, timeout: float) -> tuple[list[tuple[str, str]], float]:
        """Resolve host and return every usable address in resolver order."""
        start_time = time.perf_counter()

        addr_info: list[AddrInfo] | None = None
        worker_error: Exception | None = None

        def resolver_task() -> None:
            nonlocal addr_info, worker_error
            try:
                addr_info = cast(
                    "list[AddrInfo]",
                    socket.getaddrinfo(
                        host,
                        port,
                        family=self._family,
                        type=socket.SOCK_STREAM,
                    ),
                )
            except Exception as exc:  # pragma: no cover - handled below  # noqa: BLE001
                worker_error = exc

        thread = threading.Thread(target=resolver_task, daemon=True)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            message = f"DNS resolution timed out for {host} after {timeout:.2f}s"
            raise DNSResolutionError(message)

        if worker_error:
            if isinstance(worker_error, socket.gaierror):
                message = f"DNS resolution failed for {host}: {worker_error}"
                raise DNSResolutionError(message) from worker_error
            details = f"Unexpected error during DNS resolution for {host}: {worker_error}"
            raise DNSResolutionError(details) from worker_error

        records = _normalize_addrinfo(addr_info or [])
        if not records:
            message = f"No address records for {host}"
            raise DNSResolutionError(message)

        addresses = self._addresses(host, records)
        elapsed_ms = (time.perf_counter() - start_time) * MS_IN_SECOND
        return addresses, elapsed_ms

    def _addresses(self, host: str, records: Sequence[AddressRecord]) -> list[tuple[str, str]]:
        """Return the usable ``(ip, family)`` pairs of ``records``, in order."""
        addresses = [
            address
            for record in records
            if record.sockaddr and record.sockaddr[0] and (address := self._address(record)) is not None
        ]
        if not addresses:
            if self._family == socket.AF_INET6:
                message = f"No IPv6 address for {host}"
                raise DNSResolutionError(message)
            message = f"Failed to extract IP address for {host}"
            raise DNSResolutionError(message)
        return addresses

    def _address(self, record: AddressRecord) -> tuple[str, str] | None:
        """Return ``(ip, family)`` for a record, treating IPv4-mapped IPv6 as the IPv4 it is.

        Without global IPv6, ``getaddrinfo(..., AF_INET6)`` can return
        ``::ffff:a.b.c.d``: connecting to it uses IPv4. Such a record is
        dropped when IPv6 was required and reported as IPv4 otherwise.
        """
        ip = str(record.sockaddr[0])
        if record.family == socket.AF_INET6:
            mapped = IPv6Address(ip.partition("%")[0]).ipv4_mapped
            if mapped is not None:
                return None if self._family == socket.AF_INET6 else (str(mapped), "IPv4")
        return ip, format_address_family(record.family)


class OverrideDNSResolver:
    """Resolve configured host and port pairs to fixed IP addresses."""

    __slots__ = ("_fallback", "_overrides")

    def __init__(
        self,
        overrides: dict[tuple[str, int], str],
        *,
        family: int = socket.AF_UNSPEC,
    ) -> None:
        """Initialize fixed overrides and a family-restricted fallback resolver."""
        self._overrides = {(_override_key(host), port): address for (host, port), address in overrides.items()}
        self._fallback = SystemDNSResolver(family)

    def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
        """Resolve a configured address immediately or delegate to the system resolver."""
        address = self._overrides.get((_override_key(host), port))
        if address is None:
            return self._fallback.resolve(host, port, timeout)

        parsed_address = ip_address(address)
        family = "IPv6" if isinstance(parsed_address, IPv6Address) else "IPv4"
        return str(parsed_address), family, 0.0

    def resolve_all(self, host: str, port: int, timeout: float) -> tuple[list[tuple[str, str]], float]:
        """Return the pinned address, or every system address for fallback."""
        if (_override_key(host), port) in self._overrides:
            ip, family, elapsed_ms = self.resolve(host, port, timeout)
            return [(ip, family)], elapsed_ms
        return self._fallback.resolve_all(host, port, timeout)
