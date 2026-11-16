"""Settings and small shared helpers.

All configuration comes from environment variables (or a local `.env` for running
on your own machine). Nothing user-specific is hard-coded, so the project is
reproducible for anyone.

    NTFY_TOPIC       your private ntfy topic            (required)
    PRAYER_CITY      e.g. Lahore                         (default: Lahore)
    PRAYER_COUNTRY   e.g. Pakistan                       (default: Pakistan)
    PRAYER_METHOD    Aladhan calc method id              (default: 1 = Karachi)
    HABITICA_API_TOKEN / HABITICA_USER_ID   enable the optional nightly nudge
"""
from __future__ import annotations

import os
from pathlib import Path

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


def env(key: str, default: str | None = None) -> str | None:
    """A setting: process environment wins (e.g. GitHub Actions), then `.env`."""
    return os.environ.get(key) or _load_env_file(ENV_FILE).get(key) or default
