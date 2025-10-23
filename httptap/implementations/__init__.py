"""Concrete implementations of Protocol interfaces.

This package provides production-ready implementations for the Protocol
interfaces defined in `httptap.interfaces`. Each implementation can be
used as the default behavior or replaced with custom logic for testing or
specialized environments.

Modules:
    httptap.implementations.dns: DNS resolvers.
    httptap.implementations.tls: TLS inspection helpers.
    httptap.implementations.timing: Timing collectors.
"""

from __future__ import annotations

from .dns import DNSResolutionError, SystemDNSResolver
from .timing import PerfCounterTimingCollector
from .tls import SocketTLSInspector, TLSInspectionError

__all__ = [
    "DNSResolutionError",
    "PerfCounterTimingCollector",
    "SocketTLSInspector",
    "SystemDNSResolver",
    "TLSInspectionError",
]
