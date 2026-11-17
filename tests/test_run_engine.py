"""Phase 6 — the entry point's config mapping.

run_engine keeps config.json flat (so the phone page is unaffected) and maps it into
each plugin's own slice. That mapping is the testable core."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_engine  # noqa: E402

S = SimpleNamespace(city="Lahore", country="Pakistan", method="1",
                    reminders={"Fajr": {"after_start": 5}}, nudge_time="21:30",
                    nudge_enabled=True, timezone="Asia/Karachi",
                    prayer_window=20, nudge_window=30, nudge_streak_risk=7,
                    ramadan_enabled=True, ramadan_suhoor_lead=45,
                    ramadan_iftar_lead=0, ramadan_window=10)


def test_build_config_passes_each_plugins_window():
    cfg = run_engine.build_config(S)
    assert cfg["prayer"]["window"] == 20
    assert cfg["habitica"]["window"] == 30


def test_build_config_splits_settings_into_plugin_slices():
    cfg = run_engine.build_config(S)
    assert cfg["prayer"] == {"city": "Lahore", "country": "Pakistan", "method": "1",
                             "reminders": {"Fajr": {"after_start": 5}}, "window": 20}
    assert cfg["habitica"]["time"] == "21:30"
    assert cfg["habitica"]["enabled"] is True
    assert cfg["habitica"]["force"] is False


def test_build_config_passes_the_streak_risk():
    s = SimpleNamespace(**{**vars(S), "nudge_streak_risk": 10})
    assert run_engine.build_config(s)["habitica"]["streak_risk"] == 10


def test_build_config_marks_the_forced_source():
    cfg = run_engine.build_config(S, force_source="habitica")
    assert cfg["habitica"]["force"] is True
    cfg2 = run_engine.build_config(S, force_source="something-else")
    assert cfg2["habitica"]["force"] is False


def test_build_config_passes_the_ramadan_slice():
    s = SimpleNamespace(**{**vars(S), "ramadan_enabled": False, "ramadan_suhoor_lead": 30,
                           "ramadan_iftar_lead": 10})
    r = run_engine.build_config(s)["ramadan"]
    assert r["city"] == "Lahore" and r["method"] == "1"          # reuses the prayer location
    assert r["enabled"] is False and r["suhoor_lead"] == 30 and r["iftar_lead"] == 10
    assert r["force"] is False
    assert run_engine.build_config(s, force_source="ramadan")["ramadan"]["force"] is True


def test_select_sources_runs_all_by_default():
    assert {s.id for s in run_engine.select_sources()} == {"prayer", "habitica", "ramadan"}


def test_select_sources_runs_only_the_forced_one():
    assert [s.id for s in run_engine.select_sources("habitica")] == ["habitica"]
