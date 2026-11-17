"""State persistence for multi-run features (e.g., weekly digest aggregation).

State files live in `.noterpiper_state/` (git-ignored). Single JSON file per feature.
No server, no external store — just local files managed by the engine.
"""

import json
from datetime import datetime, date, timedelta
from pathlib import Path

STATE_DIR = Path(".noterpiper_state")


def _ensure_state_dir() -> None:
    """Create state dir if missing."""
    STATE_DIR.mkdir(exist_ok=True)


def load_weekly_state() -> dict:
    """Load weekly digest state. Missing/corrupt file returns empty state."""
    _ensure_state_dir()
    path = STATE_DIR / "habitica_weekly.json"
    if not path.exists():
        return {"week_start": None, "week_end": None, "day_runs": [], "last_digest_sent": None}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"week_start": None, "week_end": None, "day_runs": [], "last_digest_sent": None}


def save_weekly_state(state: dict) -> None:
    """Persist weekly digest state."""
    _ensure_state_dir()
    path = STATE_DIR / "habitica_weekly.json"
    path.write_text(json.dumps(state, indent=2))


def append_daily_run(state: dict, collected: dict, now: datetime) -> dict:
    """Add today's collected state to day_runs if not already present."""
    today_iso = now.date().isoformat()
    if not state["day_runs"] or state["day_runs"][-1].get("date") != today_iso:
        state["day_runs"].append({"date": today_iso, "collected": collected})
    return state


def compute_weekly_stats(day_runs: list[dict], now: datetime) -> dict:
    """Compute aggregated stats from the week's day_runs."""
    if not day_runs:
        return {"total_items": 0, "best_streak": (None, 0), "any_at_risk": False}

    total_at_risk = 0
    total_overdue = 0
    total_sections = 0
    best_streak = (None, 0)
    at_risk_names = []

    for run in day_runs:
        c = run.get("collected", {})
        total_at_risk += len(c.get("at_risk", []))
        total_overdue += len(c.get("overdue", []))
        total_sections += sum(len(v) for v in c.get("sections", {}).values())

        # Track best streak
        for name, streak in c.get("at_risk", []):
            if streak > best_streak[1]:
                best_streak = (name, streak)

        # Collect at-risk names
        for name, _ in c.get("at_risk", []):
            at_risk_names.append(name)

    total_items = total_at_risk + total_overdue + total_sections
    any_at_risk = len(at_risk_names) > 0

    return {
        "total_items": total_items,
        "best_streak": best_streak,
        "any_at_risk": any_at_risk,
        "at_risk_sample": at_risk_names[0] if at_risk_names else None,
    }


def get_weekly_bounds(now: datetime) -> tuple[date, date]:
    """Get week start (Monday) and end (Sunday) for the given date."""
    now_date = now.date()
    start = now_date - timedelta(days=now_date.weekday())  # Monday
    end = start + timedelta(days=6)  # Sunday
    return start, end
