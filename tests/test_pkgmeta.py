from __future__ import annotations

import importlib.metadata as importlib_metadata
from typing import TYPE_CHECKING

import pytest

from httptap import _pkgmeta

if TYPE_CHECKING:
    from collections.abc import Iterator

    from faker import Faker


class _DummyMetadata:
    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def get_all(self, name: str, failobj: object = None) -> object:
        value = self._data.get(name, failobj)
        return value if isinstance(value, list) or value is failobj else [value]


@pytest.fixture(autouse=True)
def clear_pkgmeta_cache() -> Iterator[None]:
    _pkgmeta.get_package_info.cache_clear()
    yield
    _pkgmeta.get_package_info.cache_clear()


def test_get_package_info_normalizes_list_values(
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> None:
    primary_author = faker.name()
    secondary_author = faker.name()
    primary_homepage = faker.url()
    secondary_homepage = faker.url()
    primary_license = faker.pystr(min_chars=5, max_chars=12)
    secondary_license = faker.pystr(min_chars=5, max_chars=12)

    metadata_values: dict[str, object] = {
        "Author": [primary_author, secondary_author],
        "Home-page": [primary_homepage, secondary_homepage],
        "License": [primary_license, secondary_license],
    }

    version = faker.pystr(min_chars=3, max_chars=8)

    monkeypatch.setattr(importlib_metadata, "version", lambda _: version)
    monkeypatch.setattr(
        importlib_metadata,
        "metadata",
        lambda _: _DummyMetadata(metadata_values),
    )

    info = _pkgmeta.get_package_info()

    assert info.version == version
    assert info.author == primary_author
    assert info.homepage == primary_homepage
    assert info.license == primary_license


def test_get_package_info_falls_back_for_non_string_lists(
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> None:
    metadata_values: dict[str, object] = {
        "Author": [faker.random_int()],
        "Home-page": [object()],
        "License": [None],
    }

    version = faker.pystr(min_chars=3, max_chars=8)

    monkeypatch.setattr(importlib_metadata, "version", lambda _: version)
    monkeypatch.setattr(
        importlib_metadata,
        "metadata",
        lambda _: _DummyMetadata(metadata_values),
    )

    info = _pkgmeta.get_package_info()

    assert info.version == version
    assert info.author == "Sergei Ozeranskii"
    assert info.homepage == "https://github.com/ozeranskii/httptap"
    assert info.license == "Apache-2.0"


def test_get_package_info_returns_defaults_when_package_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        importlib_metadata,
        "version",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(importlib_metadata.PackageNotFoundError()),
    )

    info = _pkgmeta.get_package_info()

    assert info.version == "0.0.0"
    assert info.author == "Sergei Ozeranskii"
    assert info.homepage == "https://github.com/ozeranskii/httptap"
    assert info.license == "Apache-2.0"


def _install_metadata(monkeypatch: pytest.MonkeyPatch, values: dict[str, object]) -> None:
    monkeypatch.setattr(importlib_metadata, "version", lambda _: "1.2.3")
    monkeypatch.setattr(importlib_metadata, "metadata", lambda _: _DummyMetadata(values))


def test_get_package_info_reads_core_metadata_2_4(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_metadata(
        monkeypatch,
        {
            "Author": "Example Author",
            "License-Expression": "MIT",
            "Project-URL": ["Documentation, https://docs.example.test", "Homepage, https://example.test"],
        },
    )

    info = _pkgmeta.get_package_info()

    assert info.license == "MIT"
    assert info.homepage == "https://example.test"


def test_get_package_info_falls_back_without_homepage_project_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_metadata(monkeypatch, {"Project-URL": ["Issues, https://example.test/issues"]})

    info = _pkgmeta.get_package_info()

    assert info.homepage == "https://github.com/ozeranskii/httptap"
    assert info.license == "Apache-2.0"
