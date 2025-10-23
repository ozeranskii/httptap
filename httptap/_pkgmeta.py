"""Helpers for accessing package metadata.

Provides cached access to version, author, and homepage information derived
from the package metadata. Falls back to sensible defaults when running from
source (e.g., during development without an installed distribution).
"""

from __future__ import annotations

from functools import lru_cache
from importlib import metadata

PACKAGE_NAME = "httptap"
DEFAULT_VERSION = "0.0.0"
DEFAULT_AUTHOR = "Sergei Ozeranskii"
DEFAULT_LICENSE = "Apache-2.0"
DEFAULT_HOMEPAGE = "https://github.com/ozeranskii/httptap"


@lru_cache
def package_version() -> str:
    """Return the installed package version or a development fallback."""
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return DEFAULT_VERSION


@lru_cache
def package_author() -> str:
    """Return the declared package author."""
    try:
        meta = metadata.metadata(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return DEFAULT_AUTHOR
    return meta.get("Author", DEFAULT_AUTHOR)


@lru_cache
def package_home_page() -> str:
    """Return the declared package homepage."""
    try:
        meta = metadata.metadata(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return DEFAULT_HOMEPAGE
    return meta.get("Home-page", DEFAULT_HOMEPAGE)


@lru_cache
def package_license() -> str:
    """Return the declared package license."""
    try:
        meta = metadata.metadata(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return DEFAULT_LICENSE
    return meta.get("License", DEFAULT_LICENSE)
