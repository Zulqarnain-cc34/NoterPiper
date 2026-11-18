"""Weekly-digest state for the Habitica plugin — its only consumer.

One JSON file under `.noterpiper_state/` (git-ignored) accumulates each day's
collect() snapshot so the Sunday digest can aggregate the week. No server, no
external store.

Persistence: on a persistent machine the directory simply lives on disk. On
GitHub Actions the runner is wiped between runs, so prayers.yml carries the
directory across runs via the Actions cache (restore newest → run → save).
Cache eviction (rare) just restarts the week — a missing dir is always handled
gracefully here, never an error.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from ... import config

STATE_DIR = config.PROJECT_ROOT / ".noterpiper_state"

_EMPTY = {"week_start": None, "week_end": None, "day_runs": [], "last_digest_sent": None}


def load_weekly_state() -> dict:
    """Load weekly digest state. Missing/corrupt file returns empty state."""
    path = STATE_DIR / "habitica_weekly.json"
    try:
        loaded = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(_EMPTY, day_runs=[])
    if not isinstance(loaded, dict) or not isinstance(loaded.get("day_runs"), list):
        return dict(_EMPTY, day_runs=[])
    return {**_EMPTY, **loaded}


def save_weekly_state(state: dict) -> None:
    """Persist weekly digest state."""
    STATE_DIR.mkdir(exist_ok=True)
    (STATE_DIR / "habitica_weekly.json").write_text(json.dumps(state, indent=2))


def get_weekly_bounds(now: datetime) -> tuple[date, date]:
    """Week start (Monday) and end (Sunday) for the given date."""
    start = now.date() - timedelta(days=now.date().weekday())  # Monday
    return start, start + timedelta(days=6)  # Sunday


def append_daily_run(state: dict, collected: dict, now: datetime) -> dict:
    """Record today's collect() result once per day, pruning runs that aren't from the
    current week — stale entries would otherwise pollute the stats forever on a
    persistent machine (e.g. the digest disabled for a month, then re-enabled)."""
    start, end = get_weekly_bounds(now)
    runs = [
        r
        for r in state.get("day_runs", [])
        if start.isoformat() <= str(r.get("date", "")) <= end.isoformat()
    ]
    today = now.date().isoformat()
    if not any(r.get("date") == today for r in runs):
        runs.append({"date": today, "collected": collected})
    state["day_runs"] = runs
    state["week_start"], state["week_end"] = start.isoformat(), end.isoformat()
    return state


def compute_weekly_stats(day_runs: list[dict]) -> dict:
    """Aggregate the week's day_runs: total shown items, the best streak seen among
    at-risk dailies, and a sample at-risk name for the digest's callout."""
    total = 0
    best_streak: tuple[str | None, int] = (None, 0)
    at_risk_names: list[str] = []

    for run in day_runs:
        c = run.get("collected", {})
        total += len(c.get("at_risk", []))
        total += len(c.get("overdue", []))
        total += sum(len(v) for v in c.get("sections", {}).values())
        for name, streak in c.get("at_risk", []):
            at_risk_names.append(name)
            if streak > best_streak[1]:
                best_streak = (name, streak)

    return {
        "total_items": total,
        "best_streak": best_streak,
        "any_at_risk": bool(at_risk_names),
        "at_risk_sample": at_risk_names[0] if at_risk_names else None,
    }
