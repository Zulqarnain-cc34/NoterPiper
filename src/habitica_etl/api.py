"""Minimal, read-only Habitica API client (stdlib only — no new deps).

Reads the API token from `.env` (key `API_TOKEN`) and never logs it. The User ID
comes from `.env` (`USER_ID`) or falls back to the existing export. Used to pull
the current account data so the pipeline/dashboard can refresh without a manual
export. All calls here are **GET (read-only)**.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from . import config

API_BASE = "https://habitica.com/api/v3"


def _load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _creds() -> tuple[str, str]:
    env = _load_env(config.PROJECT_ROOT / ".env")
    token = env.get("API_TOKEN") or os.environ.get("HABITICA_API_TOKEN")
    user_id = env.get("USER_ID") or os.environ.get("HABITICA_USER_ID")
    if not user_id:  # fallback: read the id from a saved snapshot/export
        for src in (config.DATA_DIR / "habitica-live.json", config.RAW_JSON):
            try:
                d = json.loads(src.read_text())
                user_id = d.get("id") or d.get("_id")
                if user_id:
                    break
            except Exception:
                pass
    if not token or not user_id:
        raise RuntimeError("Missing API_TOKEN (.env) or USER_ID — cannot call API.")
    return user_id, token


def _get(path: str) -> Any:
    user_id, token = _creds()
    req = urllib.request.Request(
        API_BASE + path,
        headers={
            "x-api-user": user_id,
            "x-api-key": token,
            # x-client: "UserID-AppName" per Habitica guidelines
            "x-client": f"{user_id}-habitica-productivity",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))["data"]


def fetch_user() -> dict[str, Any]:
    """GET /user — account object (auth, preferences, stats, …)."""
    return _get("/user")


def fetch_tasks() -> list[dict[str, Any]]:
    """GET /tasks/user — all active tasks (with their history arrays)."""
    return _get("/tasks/user")


def fetch_export_like() -> dict[str, Any]:
    """Assemble a dict matching the manual-export shape the loaders expect:
    user object with `tasks.{dailys,todos,habits,rewards}` grouped by type.
    """
    user = fetch_user()
    tasks = fetch_tasks()
    groups: dict[str, list] = {"dailys": [], "todos": [], "habits": [], "rewards": []}
    key = {"daily": "dailys", "todo": "todos", "habit": "habits", "reward": "rewards"}
    for t in tasks:
        g = key.get(t.get("type"))
        if g:
            groups[g].append(t)
    user["tasks"] = groups
    return user
