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
