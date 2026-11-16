"""One file holds every user-editable setting (location, offsets, nightly nudge).

Precedence: environment variable → config.json → built-in default. A missing or
malformed config.json falls back to defaults — a bad file never crashes a run.
This is the single source of truth the phone config page edits.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config

DEFAULT_REMINDERS = {
    "Fajr": {"before_end": 30}, "Zohar": {"before_end": 30},
    "Asr": {"before_end": 30}, "Maghrib": {"before_end": 30},
    "Isha": {"after_start": 60},
}


@dataclass(frozen=True)
class Settings:
    city: str
    country: str
    method: str
    reminders: dict
    nudge_time: str      # "HH:MM", local
    nudge_enabled: bool
    timezone: str        # IANA name, used to fire the nudge at the right local time
    prayer_window: int = 5    # minutes a prayer reminder stays "due" after its time
    nudge_window: int = 5     # minutes the nightly nudge stays "due" after its time
    nudge_streak_risk: int = 7     # streak length at which an unticked daily is "at risk"
    nudge_show_todos: bool = True      # include due/overdue to-dos in the nudge
    nudge_show_dailies: bool = True    # include due dailies (and their at-risk flag)
    nudge_show_prayers: bool = True    # include unlogged prayer habits


DEFAULTS = Settings(
    city="Makkah", country="Saudi Arabia", method="4",
    reminders=DEFAULT_REMINDERS, nudge_time="21:30",
    nudge_enabled=True, timezone="Asia/Riyadh",
)


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:          # missing / malformed → defaults, never a crash
        return {}


def _as_int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):          # missing / hand-edited junk → default
        return default


def _as_bool(v, default: bool = True) -> bool:
    if v is None:
        return default
    if isinstance(v, str):                       # tolerate hand-edited "false"/"no"/"0"
        return v.strip().lower() not in ("false", "0", "no", "off", "")
    return bool(v)


def _valid_time(t: str) -> bool:
    try:
        h, m = (int(x) for x in t.split(":"))
    except (ValueError, TypeError):
        return False
    return 0 <= h < 24 and 0 <= m < 60


def _valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def load_settings(path: Path | None = None) -> Settings:
    raw = _read(path or config.PROJECT_ROOT / "config.json")
    reminders = raw.get("reminders")
    raw_nudge = raw.get("nudge")
    nudge = raw_nudge if isinstance(raw_nudge, dict) else {}

    raw_method = raw.get("method")                       # 0 (Jafari) is valid → don't lose it
    method = config.env("PRAYER_METHOD") or (
        str(raw_method) if raw_method not in (None, "") else DEFAULTS.method)

    nudge_time = str(nudge.get("time") or DEFAULTS.nudge_time)
    if not _valid_time(nudge_time):                      # hand-edited junk → default, never a crash
        nudge_time = DEFAULTS.nudge_time

    tz = config.env("PRAYER_TIMEZONE") or raw.get("timezone") or DEFAULTS.timezone
    if not _valid_tz(tz):                                # bad IANA name → default, nudge still fires
        tz = DEFAULTS.timezone

    return Settings(
        city=config.env("PRAYER_CITY") or raw.get("city") or DEFAULTS.city,
        country=config.env("PRAYER_COUNTRY") or raw.get("country") or DEFAULTS.country,
        method=method,
        reminders=reminders if isinstance(reminders, dict) and reminders else DEFAULTS.reminders,
        nudge_time=nudge_time,
        nudge_enabled=_as_bool(nudge.get("enabled")),
        timezone=tz,
        prayer_window=_as_int(raw.get("window"), DEFAULTS.prayer_window),
        nudge_window=_as_int(nudge.get("window"), DEFAULTS.nudge_window),
        nudge_streak_risk=_as_int(nudge.get("streak_risk"), DEFAULTS.nudge_streak_risk),
        nudge_show_todos=_as_bool(nudge.get("show_todos")),
        nudge_show_dailies=_as_bool(nudge.get("show_dailies")),
        nudge_show_prayers=_as_bool(nudge.get("show_prayers")),
    )
