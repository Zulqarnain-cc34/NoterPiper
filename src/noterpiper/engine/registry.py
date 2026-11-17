"""Plugin discovery — find every Source in a package, so there's no hardcoded list.

A plugin registers itself simply by existing: drop a package under `noterpiper/plugins/`
whose module defines a class satisfying the `Source` contract (a `str` `id` and a
`check` method), and it's picked up automatically. This is the naming-convention /
`pkgutil` approach from the Python Packaging Guide — the right fit for in-repo plugins
on a stdlib, no-install, serverless deployment. (Third-party pip-installed plugins would
layer on `importlib.metadata` entry points; the `Source` contract stays identical.)
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType

from .plugin import Source


def _is_source_class(obj: object, module: ModuleType) -> bool:
    """A class defined *in this module* that looks like a Source (str id + check())."""
    return (inspect.isclass(obj)
            and obj.__module__ == module.__name__          # defined here, not imported in
            and isinstance(getattr(obj, "id", None), str)
            and callable(getattr(obj, "check", None)))


def discover_sources(package: ModuleType) -> list[Source]:
    """Every Source found under `package`, instantiated, sorted by id for a stable run."""
    sources: list[Source] = []
    for info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        module = importlib.import_module(info.name)
        for obj in vars(module).values():
            if _is_source_class(obj, module):
                sources.append(obj())
    return sorted(sources, key=lambda s: s.id)
