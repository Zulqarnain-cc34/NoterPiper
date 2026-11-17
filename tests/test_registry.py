"""Plugin auto-discovery — the engine finds every Source with no hardcoded list.

Two sources of plugins, same Source contract:
  • in-repo packages under noterpiper/plugins/ — pkgutil scan (the PyPA pattern)
  • pip-installed packages — importlib.metadata entry points (`noterpiper.plugins`),
    so a third party can `pip install` a plugin and it auto-registers (pytest's model)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noterpiper import plugins  # noqa: E402
from noterpiper.engine import Source  # noqa: E402
from noterpiper.engine.registry import (  # noqa: E402
    discover_all, discover_entry_points, discover_sources)


class _Weather:                               # a stand-in third-party plugin
    id = "weather"
    def check(self, now, config):
        return []


class _EP:                                    # a stand-in importlib.metadata EntryPoint
    name = "weather"
    def load(self):
        return _Weather


def _fake_eps(group=None, **_):
    return [_EP()] if group == "noterpiper.plugins" else []


# ─── in-repo (pkgutil) ───

def test_discovers_every_shipped_source():
    assert {s.id for s in discover_sources(plugins)} == {"prayer", "habitica", "ramadan"}


def test_discovered_sources_satisfy_the_contract():
    for s in discover_sources(plugins):
        assert isinstance(s, Source)
        assert isinstance(s.id, str) and s.id


def test_discovery_is_sorted_by_id_for_stable_order():
    ids = [s.id for s in discover_sources(plugins)]
    assert ids == sorted(ids)


# ─── pip-installed (entry points) ───

def test_discovers_entry_point_plugins(monkeypatch):
    monkeypatch.setattr("noterpiper.engine.registry.metadata.entry_points", _fake_eps)
    found = discover_entry_points()
    assert [s.id for s in found] == ["weather"]
    assert isinstance(found[0], Source)


def test_a_broken_entry_point_never_breaks_discovery(monkeypatch):
    class _BadEP:
        name = "broken"
        def load(self):
            raise ImportError("missing dependency")
    monkeypatch.setattr("noterpiper.engine.registry.metadata.entry_points",
                        lambda group=None, **_: [_BadEP()] if group == "noterpiper.plugins" else [])
    assert discover_entry_points() == []      # isolated, not raised


def test_discover_all_combines_in_repo_and_installed(monkeypatch):
    monkeypatch.setattr("noterpiper.engine.registry.metadata.entry_points", _fake_eps)
    assert {s.id for s in discover_all(plugins)} == {"prayer", "habitica", "ramadan", "weather"}
