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
from importlib import metadata
from types import ModuleType

from .plugin import Source

ENTRY_POINT_GROUP = "noterpiper.plugins"  # pip-installed plugins register here


def _is_source_class(obj: object, module: ModuleType) -> bool:
    """A class defined *in this module* that looks like a Source (str id + check())."""
    return (
        inspect.isclass(obj)
        and obj.__module__ == module.__name__  # defined here, not imported in
        and isinstance(getattr(obj, "id", None), str)
        and callable(getattr(obj, "check", None))
    )


def discover_sources(package: ModuleType) -> list[Source]:
    """Every Source found under `package` (in-repo), instantiated, sorted by id."""
    sources: list[Source] = []
    for info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        module = importlib.import_module(info.name)
        for obj in vars(module).values():
            if _is_source_class(obj, module):
                sources.append(obj())
    return sorted(sources, key=lambda s: s.id)


def discover_entry_points(group: str = ENTRY_POINT_GROUP) -> list[Source]:
    """Sources registered by pip-installed packages via entry points, e.g.

        [project.entry-points."noterpiper.plugins"]
        weather = "noterpiper_weather:WeatherSource"

    This is how a third-party plugin auto-registers after `pip install` — the pytest
    `pytest11` model. One broken entry point never breaks the rest."""
    sources: list[Source] = []
    for ep in metadata.entry_points(group=group):
        try:
            obj = ep.load()
            inst = obj() if inspect.isclass(obj) else obj
        except Exception as e:  # a bad plugin must not take down the engine
            print(f"[warn] plugin entry point {ep.name!r} failed to load: {e}")
            continue
        if isinstance(inst, Source):
            sources.append(inst)
    return sources


def discover_all(package: ModuleType, group: str = ENTRY_POINT_GROUP) -> list[Source]:
    """Every plugin: in-repo (pkgutil) + pip-installed (entry points), deduped by id
    (in-repo wins a clash), sorted for a stable run."""
    by_id: dict[str, Source] = {}
    for s in discover_sources(package) + discover_entry_points(group):
        by_id.setdefault(s.id, s)
    return sorted(by_id.values(), key=lambda s: s.id)
