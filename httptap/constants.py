"""Shared constants used across the httptap codebase."""

from __future__ import annotations

import os
from enum import Enum, unique
from http import HTTPStatus


@unique
class HTTPMethod(str, Enum):
    """HTTP methods supported by httptap.

    Inherits from str to enable direct comparison with strings
    and argparse integration without custom type conversion.
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


MS_IN_SECOND = 1000.0
DEFAULT_TIMEOUT_SECONDS = 20.0
TLS_PROBE_MAX_TIMEOUT_SECONDS = 5.0
HTTP_DEFAULT_PORT = 80
HTTPS_DEFAULT_PORT = 443
CONNECT_PHASE_RATIO = 0.30
TLS_PHASE_RATIO = 0.70
CERT_EXPIRY_CRITICAL_DAYS = 30
CERT_EXPIRY_WARNING_DAYS = 90
UNIX_SIGNAL_EXIT_OFFSET = 128
BYTES_PER_KIB = 1024

_EX_OK_FALLBACK = 0
_EX_USAGE_FALLBACK = 64
_EX_TEMPFAIL_FALLBACK = 75
_EX_SOFTWARE_FALLBACK = 70

EXIT_CODE_OK = getattr(os, "EX_OK", _EX_OK_FALLBACK)
EXIT_CODE_USAGE = getattr(os, "EX_USAGE", _EX_USAGE_FALLBACK)
EXIT_CODE_TEMPFAIL = getattr(os, "EX_TEMPFAIL", _EX_TEMPFAIL_FALLBACK)
EXIT_CODE_SOFTWARE = getattr(os, "EX_SOFTWARE", _EX_SOFTWARE_FALLBACK)

HTTP_SUCCESS_MIN = HTTPStatus.OK.value
HTTP_SUCCESS_MAX = HTTPStatus.MULTIPLE_CHOICES.value - 1
HTTP_REDIRECT_MIN = HTTPStatus.MULTIPLE_CHOICES.value
HTTP_REDIRECT_MAX = HTTPStatus.BAD_REQUEST.value - 1
