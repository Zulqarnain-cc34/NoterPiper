"""Plugin auto-discovery — the engine finds every Source in a package, no hardcoded list.

Drop a plugin package under noterpiper/plugins/ and it registers itself; nothing else
changes. (pkgutil naming-convention discovery — the PyPA pattern for in-repo plugins.)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noterpiper import plugins  # noqa: E402
from noterpiper.engine import Source  # noqa: E402
from noterpiper.engine.registry import discover_sources  # noqa: E402


def test_discovers_every_shipped_source():
    assert {s.id for s in discover_sources(plugins)} == {"prayer", "habitica", "ramadan"}


def test_discovered_sources_satisfy_the_contract():
    for s in discover_sources(plugins):
        assert isinstance(s, Source)
        assert isinstance(s.id, str) and s.id


def test_discovery_is_sorted_by_id_for_stable_order():
    ids = [s.id for s in discover_sources(plugins)]
    assert ids == sorted(ids)
