"""Shared-location settings: env → config.json → defaults (crash-proof), plus keyed_config.
Per-plugin config lives with the plugins now; this only resolves the shared location."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noterpiper import config, settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """Keep the real .env / shell vars out of these tests; env-override is tested explicitly."""
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "absent.env")
    for k in ("PRAYER_CITY", "PRAYER_COUNTRY", "PRAYER_METHOD", "PRAYER_TIMEZONE"):
        monkeypatch.delenv(k, raising=False)


def _write(tmp_path, obj):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(obj))
    return p


# ─── shared location resolution ───


def test_missing_file_returns_defaults(tmp_path):
    s = settings.load_settings(tmp_path / "nope.json")
    assert (s.city, s.country, s.method, s.timezone) == (
        "Makkah",
        "Saudi Arabia",
        "4",
        "Asia/Riyadh",
    )


def test_malformed_file_returns_defaults(tmp_path):
    bad = tmp_path / "config.json"
    bad.write_text("{ not valid json")
    assert settings.load_settings(bad).city == "Makkah"


def test_location_loads_and_coerces_method_to_str(tmp_path):
    f = _write(tmp_path, {"city": "Istanbul", "country": "Turkey", "method": 3})  # method as int
    s = settings.load_settings(f)
    assert s.city == "Istanbul" and s.country == "Turkey" and s.method == "3"


def test_method_zero_is_preserved(tmp_path):
    assert settings.load_settings(_write(tmp_path, {"method": 0})).method == "0"  # 0 = Jafari, real


def test_env_overrides_config(tmp_path, monkeypatch):
    f = _write(tmp_path, {"city": "Istanbul"})
    monkeypatch.setenv("PRAYER_CITY", "Cairo")
    assert settings.load_settings(f).city == "Cairo"


def test_timezone_env_overrides_config(tmp_path, monkeypatch):
    f = _write(tmp_path, {"timezone": "Europe/Istanbul"})
    monkeypatch.setenv("PRAYER_TIMEZONE", "Asia/Dubai")
    assert settings.load_settings(f).timezone == "Asia/Dubai"


def test_invalid_timezone_falls_back_to_default(tmp_path):
    f = _write(tmp_path, {"timezone": "Not/AZone"})
    assert settings.load_settings(f).timezone == "Asia/Riyadh"


# ─── config.json → per-plugin sections ───


def test_keyed_config_normalizes_the_legacy_shape(tmp_path):
    f = _write(
        tmp_path,
        {
            "city": "Lahore",
            "reminders": {"Fajr": {"before_end": 10}},
            "nudge": {"time": "20:00", "streak_risk": 5},
            "ramadan": {"enabled": False},
        },
    )
    raw = settings.keyed_config(f)
    assert raw["habitica"] == {"time": "20:00", "streak_risk": 5}  # nudge -> habitica
    assert raw["prayer"]["reminders"]["Fajr"]["before_end"] == 10  # top-level reminders -> prayer
    assert raw["ramadan"]["enabled"] is False
    assert "city" not in raw and "nudge" not in raw  # location/legacy keys stay out


def test_keyed_config_passes_through_the_new_keyed_shape(tmp_path):
    f = _write(
        tmp_path,
        {
            "city": "X",
            "habitica": {"time": "21:00"},
            "prayer": {"reminders": {}},
            "ramadan": {"enabled": True},
        },
    )
    raw = settings.keyed_config(f)
    assert raw["habitica"] == {"time": "21:00"} and raw["ramadan"]["enabled"] is True
