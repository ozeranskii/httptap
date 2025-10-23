"""DNS resolver implementations."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from httptap.constants import MS_IN_SECOND

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


class DNSResolutionError(Exception):
    """Raised when DNS resolution fails."""


class SystemDNSResolver:
    """DNS resolver using the system getaddrinfo implementation."""

    __slots__ = ()

    def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
        """Resolve host and return IP, family label, and elapsed milliseconds."""
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
                        family=socket.AF_UNSPEC,
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

        if addr_info is None:
            message = f"No address records for {host}"
            raise DNSResolutionError(message)

        if not addr_info:
            message = f"No address records for {host}"
            raise DNSResolutionError(message)

        records = _normalize_addrinfo(addr_info)
        if not records:
            message = f"No address records for {host}"
            raise DNSResolutionError(message)

        record = records[0]
        ip = str(record.sockaddr[0]) if record.sockaddr else None
        if not ip:
            message = f"Failed to extract IP address for {host}"
            raise DNSResolutionError(message)

        elapsed_ms = (time.perf_counter() - start_time) * MS_IN_SECOND
        ip_family = self._family_to_label(record.family)
        return ip, ip_family, elapsed_ms

    @staticmethod
    def _family_to_label(family: int) -> str:
        if family == socket.AF_INET6:
            return "IPv6"
        if family == socket.AF_INET:
            return "IPv4"
        return f"AF_{family}"
