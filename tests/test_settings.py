"""Locks the settings loader: env → config.json → defaults, crash-proof (offline)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muezzin import config, settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """Keep the real .env / shell vars out of these tests; env-override is tested
    explicitly in test_env_overrides_config."""
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "absent.env")
    for k in ("PRAYER_CITY", "PRAYER_COUNTRY", "PRAYER_METHOD", "PRAYER_TIMEZONE"):
        monkeypatch.delenv(k, raising=False)


def _write(tmp_path, obj):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(obj))
    return p


def test_missing_file_returns_defaults(tmp_path):
    s = settings.load_settings(tmp_path / "nope.json")
    assert s.city == "Makkah"
    assert s.nudge_time == "21:30"
    assert s.nudge_enabled is True


def test_malformed_file_returns_defaults(tmp_path):
    bad = tmp_path / "config.json"
    bad.write_text("{ not valid json")
    assert settings.load_settings(bad).city == "Makkah"


def test_values_load_and_coerce(tmp_path):
    f = _write(tmp_path, {
        "city": "Istanbul", "country": "Turkey", "method": 3,   # method as int
        "nudge": {"time": "22:00"},                              # no "enabled" key
    })
    s = settings.load_settings(f)
    assert s.city == "Istanbul" and s.country == "Turkey"
    assert s.method == "3"                                       # coerced to str
    assert s.nudge_time == "22:00"
    assert s.nudge_enabled is True                               # defaults True when absent


def test_disabled_nudge_is_read(tmp_path):
    f = _write(tmp_path, {"nudge": {"time": "20:00", "enabled": False}})
    assert settings.load_settings(f).nudge_enabled is False


def test_enabled_string_false_is_off(tmp_path):
    f = _write(tmp_path, {"nudge": {"enabled": "false"}})    # hand-edited JSON string
    assert settings.load_settings(f).nudge_enabled is False


def test_env_overrides_config(tmp_path, monkeypatch):
    f = _write(tmp_path, {"city": "Istanbul"})
    monkeypatch.setenv("PRAYER_CITY", "Cairo")
    assert settings.load_settings(f).city == "Cairo"


def test_timezone_env_overrides_config(tmp_path, monkeypatch):
    f = _write(tmp_path, {"timezone": "Europe/Istanbul"})
    monkeypatch.setenv("PRAYER_TIMEZONE", "Asia/Dubai")
    assert settings.load_settings(f).timezone == "Asia/Dubai"


def test_invalid_time_falls_back_to_default(tmp_path):
    f = _write(tmp_path, {"nudge": {"time": "9pm"}})       # hand-edited junk
    assert settings.load_settings(f).nudge_time == "21:30"


def test_out_of_range_time_falls_back(tmp_path):
    f = _write(tmp_path, {"nudge": {"time": "99:99"}})
    assert settings.load_settings(f).nudge_time == "21:30"


def test_method_zero_is_preserved(tmp_path):
    f = _write(tmp_path, {"method": 0})                     # 0 = Jafari, a real method
    assert settings.load_settings(f).method == "0"


def test_invalid_timezone_falls_back_to_default(tmp_path):
    f = _write(tmp_path, {"timezone": "Not/AZone"})
    assert settings.load_settings(f).timezone == "Asia/Riyadh"
