"""Checks on what the installed distribution declares and ships."""

from __future__ import annotations

import ast
import importlib.metadata as importlib_metadata
from importlib.resources import files
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

import httptap


def _imported_top_level_modules() -> set[str]:
    modules: set[str] = set()
    for source in Path(httptap.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules.update(alias.name.partition(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.partition(".")[0])
    return modules


def test_package_ships_pep561_marker() -> None:
    assert files("httptap").joinpath("py.typed").is_file()


def test_every_runtime_dependency_is_imported() -> None:
    """Required dependencies are installed for every user, so each must be used."""
    providers = importlib_metadata.packages_distributions()
    imported = {
        canonicalize_name(distribution)
        for module in _imported_top_level_modules()
        for distribution in providers.get(module, [])
    }
    runtime = {
        canonicalize_name(requirement.name)
        for requirement in map(Requirement, importlib_metadata.requires("httptap") or [])
        if requirement.marker is None
    }

    assert runtime - imported == set()
