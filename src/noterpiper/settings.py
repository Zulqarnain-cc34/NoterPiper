"""Shared-location settings — the one cross-cutting thing several plugins reuse.

Per-plugin config now lives with each plugin (its `defaults`) plus the user's overrides
in `config.json`, keyed by plugin id (see `engine/config.py`). This module does only two
things:

  • `load_settings` — resolve the **shared location** (city / country / method / timezone):
    env var → config.json → built-in default, crash-proof.
  • `keyed_config` — normalize the raw `config.json` into per-plugin sections keyed by id,
    accepting both the new keyed shape and the legacy one.

Precedence: environment variable → config.json → default. A missing or malformed
config.json falls back to defaults — a bad file never crashes a run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config


@dataclass(frozen=True)
class Settings:
    city: str
    country: str
    method: str
    timezone: str  # IANA name — the clock the engine runs the plugins on


DEFAULTS = Settings(city="Makkah", country="Saudi Arabia", method="4", timezone="Asia/Riyadh")


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:  # missing / malformed → defaults, never a crash
        return {}


def _valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def load_settings(path: Path | None = None) -> Settings:
    """Resolve the shared location: env var → config.json → default, crash-proof."""
    raw = _read(path or config.PROJECT_ROOT / "config.json")

    raw_method = raw.get("method")  # 0 (Jafari) is valid → don't lose it
    method = config.env("PRAYER_METHOD") or (
        str(raw_method) if raw_method not in (None, "") else DEFAULTS.method
    )

    tz = config.env("PRAYER_TIMEZONE") or raw.get("timezone") or DEFAULTS.timezone
    if not _valid_tz(tz):  # bad IANA name → default, engine still runs
        tz = DEFAULTS.timezone

    return Settings(
        city=config.env("PRAYER_CITY") or raw.get("city") or DEFAULTS.city,
        country=config.env("PRAYER_COUNTRY") or raw.get("country") or DEFAULTS.country,
        method=method,
        timezone=tz,
    )


_LEGACY_SECTIONS = {"nudge": "habitica"}  # old config.json section name -> plugin id


def keyed_config(path: Path | None = None) -> dict:
    """The raw config.json as per-plugin sections keyed by plugin id.

    Accepts both the new shape (`{"habitica": {...}, "prayer": {...}}`) and the legacy one
    (a `nudge` section, top-level `reminders`/`window`), so an un-migrated config.json keeps
    working. The shared location lives at the top level and is resolved by `load_settings`."""
    raw = _read(path or config.PROJECT_ROOT / "config.json")
    out: dict = {}
    for key, val in raw.items():
        if key == "reminders" or not isinstance(val, dict):
            continue  # location strings + legacy reminders: below
        slot = out.setdefault(_LEGACY_SECTIONS.get(key, key), {})
        if key in _LEGACY_SECTIONS:  # a half-migrated file: legacy fills gaps only,
            for k, v in val.items():  # the new-shape section always wins
                slot.setdefault(k, v)
        else:
            slot.update(val)
    if isinstance(raw.get("reminders"), dict):  # legacy top-level prayer config
        out.setdefault("prayer", {}).setdefault("reminders", raw["reminders"])
    if "window" in raw and not isinstance(raw.get("window"), dict):
        out.setdefault("prayer", {}).setdefault("window", raw["window"])
    return out
