"""The entry point's config assembly.

build_config is now generic: for every discovered source it merges the plugin's own
defaults <- shared location (if wanted) <- the user's config[id]. No per-plugin wiring."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_engine  # noqa: E402

# Settings now only carries the shared location.
S = SimpleNamespace(city="Lahore", country="Pakistan", method="1", timezone="Asia/Karachi")


def test_location_is_injected_only_into_plugins_that_want_it():
    cfg = run_engine.build_config(run_engine.SOURCES, S, {})
    assert cfg["prayer"]["city"] == "Lahore"            # prayer.wants_location
    assert cfg["ramadan"]["method"] == "1"              # ramadan.wants_location (for Aladhan)
    assert "city" not in cfg["habitica"]                # habitica doesn't


def test_plugin_defaults_fill_in_when_the_user_sets_nothing():
    cfg = run_engine.build_config(run_engine.SOURCES, S, {})
    assert cfg["habitica"]["streak_risk"] == 7 and cfg["habitica"]["enabled"] is True
    assert cfg["ramadan"]["suhoor_lead"] == 45
    assert cfg["prayer"]["window"] == 5


def test_user_config_overrides_the_defaults():
    cfg = run_engine.build_config(run_engine.SOURCES, S, {"habitica": {"streak_risk": 20}})
    assert cfg["habitica"]["streak_risk"] == 20          # override wins
    assert cfg["habitica"]["enabled"] is True            # untouched default kept


def test_build_config_marks_the_forced_source():
    cfg = run_engine.build_config(run_engine.SOURCES, S, {}, force_source="ramadan")
    assert cfg["ramadan"]["force"] is True
    assert cfg["habitica"]["force"] is False


def test_select_sources_runs_all_by_default():
    assert {s.id for s in run_engine.select_sources()} == {"prayer", "habitica", "ramadan", "dates"}


def test_select_sources_runs_only_the_forced_one():
    assert [s.id for s in run_engine.select_sources("habitica")] == ["habitica"]
