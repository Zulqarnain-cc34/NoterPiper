"""Loading and raw extraction of Habitica data (live snapshot or export).

Loaders are deliberately thin: they read bytes and hand back plain Python
structures. Interpretation happens in `transform.py`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import config


def file_checksum(path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file (used for import lineage).

    Returns the digest of the empty string if the file does not exist, so
    lineage recording never crashes when a source file is absent.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except FileNotFoundError:
        pass
    return h.hexdigest()


def load_user_json(path: str | Path = config.RAW_JSON) -> dict[str, Any]:
    """Load the full Habitica user document as a dict (untouched)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_dailies(user: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of daily task objects from the user document."""
    return list(user.get("tasks", {}).get("dailys", []))


def extract_todos(user: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of to-do task objects from the user document."""
    return list(user.get("tasks", {}).get("todos", []))


def extract_habits(user: dict[str, Any]) -> list[dict[str, Any]]:
    """Return habit objects (expected empty for this account — kept for safety)."""
    return list(user.get("tasks", {}).get("habits", []))


def account_facts(user: dict[str, Any]) -> dict[str, Any]:
    """Pull the small set of non-gamification account facts we rely on."""
    auth = user.get("auth", {})
    prefs = user.get("preferences", {})
    return {
        "created": auth.get("timestamps", {}).get("created"),
        "last_login": auth.get("timestamps", {}).get("loggedin"),
        "updated": auth.get("timestamps", {}).get("updated"),
        "last_cron": user.get("lastCron"),
        "timezone_offset_min": prefs.get("timezoneOffset"),
        "day_start": prefs.get("dayStart"),
        "n_tags": len(user.get("tags", []) or []),
        "n_webhooks": len(user.get("webhooks", []) or []),
    }
