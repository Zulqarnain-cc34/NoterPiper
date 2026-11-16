"""Settings and small shared helpers.

All configuration comes from environment variables (or a local `.env` for running
on your own machine). Nothing user-specific is hard-coded, so the project is
reproducible for anyone.

    NTFY_TOPIC       your private ntfy topic            (required)
    PRAYER_CITY      your city, e.g. Istanbul           (overrides config.json)
    PRAYER_COUNTRY   your country, e.g. Turkey          (overrides config.json)
    PRAYER_METHOD    Aladhan calc method id             (overrides config.json)
    PRAYER_TIMEZONE  IANA tz, e.g. Europe/Istanbul      (overrides config.json)
    HABITICA_API_TOKEN / HABITICA_USER_ID   enable the optional nightly nudge
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import overload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data"
RAW_JSON = DATA_DIR / "habitica-live.json"  # optional local snapshot (User-ID fallback)


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


@overload
def env(key: str) -> str | None: ...
@overload
def env(key: str, default: str) -> str: ...
def env(key: str, default: str | None = None) -> str | None:
    """A setting: process environment wins (e.g. GitHub Actions), then `.env`.

    With a default, it always returns a string; without one, it may return None.
    """
    return os.environ.get(key) or _load_env_file(ENV_FILE).get(key) or default
