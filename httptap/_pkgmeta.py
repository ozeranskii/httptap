"""Package metadata access with strong typing.

Provides cached access to package metadata using a structured dataclass
instead of individual functions. Falls back to sensible defaults when
running from source (e.g., during development without an installed distribution).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from typing import Protocol, cast


class _MetadataMapping(Protocol):
    def get(self, key: str, default: object = ...) -> object: ...


PACKAGE_NAME = "httptap"


@dataclass(frozen=True, slots=True)
class PackageInfo:
    """Immutable container for package metadata.

    Attributes:
        version: Package version string (e.g., "0.1.0").
        author: Package author name.
        homepage: Project homepage URL.
        license: License identifier (e.g., "Apache-2.0").

    """

    version: str
    author: str
    homepage: str
    license: str


@lru_cache(maxsize=1)
def get_package_info() -> PackageInfo:
    """Return package metadata with proper defaults.

    Uses importlib.metadata to retrieve package information when installed,
    falling back to default values during development. Results are cached
    for performance.

    Returns:
        PackageInfo instance with all metadata fields populated.

    Examples:
        >>> info = get_package_info()
        >>> print(f"{info.version} by {info.author}")
        0.1.0 by Sergei Ozeranskii

    """
    # Default values for development (when package not installed)
    defaults = PackageInfo(
        version="0.0.0",
        author="Sergei Ozeranskii",
        homepage="https://github.com/ozeranskii/httptap",
        license="Apache-2.0",
    )

    try:
        # Get version (always available for installed packages)
        version = metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return defaults

    meta = cast("_MetadataMapping", metadata.metadata(PACKAGE_NAME))

    def _normalize(value: object, fallback: str) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
        return fallback

    author = _normalize(meta.get("Author"), defaults.author)
    homepage = _normalize(meta.get("Home-page"), defaults.homepage)
    license_val = _normalize(meta.get("License"), defaults.license)

    return PackageInfo(
        version=version,
        author=author,
        homepage=homepage,
        license=license_val,
    )
