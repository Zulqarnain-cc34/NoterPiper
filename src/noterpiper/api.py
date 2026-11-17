"""Minimal, read-only Habitica API client (stdlib only).

Reads credentials from the environment / `.env` and never logs them. Every call
here is GET (read-only). Habitica is optional — see `configured()`.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from . import config, net

API_BASE = "https://habitica.com/api/v3"
RAW_JSON = config.DATA_DIR / "habitica-live.json"  # optional local snapshot (User-ID fallback)


def _creds() -> tuple[str, str]:
    token = config.env("HABITICA_API_TOKEN") or config.env("API_TOKEN")
    user_id = config.env("HABITICA_USER_ID") or config.env("USER_ID")
    if not user_id:  # fallback: read the id from a saved snapshot, if present
        with contextlib.suppress(Exception):
            user_id = json.loads(RAW_JSON.read_text()).get("id")
    if not token or not user_id:
        raise RuntimeError("Habitica not configured (need HABITICA_API_TOKEN + HABITICA_USER_ID).")
    return user_id, token


def configured() -> bool:
    """True if Habitica credentials are available (the nightly nudge is optional)."""
    try:
        _creds()
        return True
    except RuntimeError:
        return False


def _get(path: str) -> Any:
    user_id, token = _creds()
    headers = {
        "x-api-user": user_id,
        "x-api-key": token,
        "x-client": f"{user_id}-noterpiper",  # "UserID-AppName" per Habitica guidelines
        "Content-Type": "application/json",
    }
    payload = net.get_json(API_BASE + path, headers=headers, timeout=30)
    # {success:false} (often with no `data`) → surface the message, not a bare KeyError
    if isinstance(payload, dict) and payload.get("success") is False:
        msg = payload.get("message") or payload.get("error") or "unknown"
        raise RuntimeError(f"Habitica API error: {msg}")
    return payload["data"]


def fetch_tasks() -> list[dict[str, Any]]:
    """GET /tasks/user — all active tasks (with their history arrays)."""
    return _get("/tasks/user")


def fetch_tasks_by_type() -> dict[str, list]:
    """Tasks grouped: {'dailys': [...], 'todos': [...], 'habits': [...]}.
    Rewards are dropped — no consumer reads them."""
    groups: dict[str, list] = {"dailys": [], "todos": [], "habits": []}
    key = {"daily": "dailys", "todo": "todos", "habit": "habits"}
    for t in fetch_tasks():
        g = key.get(t.get("type", ""))
        if g:
            groups[g].append(t)
    return groups


def fetch_tags() -> dict[str, str]:
    """GET /tags → {tag_id: tag_name}. Tasks reference tags by UUID; this resolves
    them to the user's section labels (see HABITICA-SCHEMA.md)."""
    return {t["id"]: (t.get("name") or "").strip() for t in _get("/tags") if t.get("id")}
