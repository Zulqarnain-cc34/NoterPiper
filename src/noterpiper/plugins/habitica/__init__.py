"""Habitica nightly-nudge source — the second plugin.

One calm end-of-day summary: unlogged prayer habits and due-but-not-done dailies,
streaks at risk flagged. Gated to fire only when Habitica is configured, the nudge
is enabled, and it's the set time. A stable title ("Nightly check-in") gives it
robust once-per-day dedup under the ~2-minute engine; the count lives in the body.
"""
from __future__ import annotations

from datetime import datetime

from ... import api
from ...engine import Notification

PRAYERS = ("Fajr", "Zohar", "Asr", "Maghrib", "Isha")
STREAK_RISK = 7          # warn when a streak this long is unticked
WINDOW_MIN = 30          # fire within this many minutes after the set time
NUDGE_TITLE = "Nightly check-in"


def _due_now(now: datetime, target_hhmm: str, window: int = WINDOW_MIN) -> bool:
    th, tm = (int(x) for x in target_hhmm.split(":")[:2])
    delta = (now.hour * 60 + now.minute) - (th * 60 + tm)
    return 0 <= delta < window


def collect(tasks: dict) -> tuple[list[str], list[tuple[str, int]]]:
    """Unlogged prayer habits, and due-but-not-done dailies with their streak."""
    prayers = [h["text"].strip() for h in tasks.get("habits", [])
               if any(p in h.get("text", "") for p in PRAYERS)
               and (h.get("counterUp", 0) + h.get("counterDown", 0)) == 0]
    dailies = [(d["text"].strip(), int(d.get("streak", 0))) for d in tasks.get("dailys", [])
               if d.get("isDue") and not d.get("completed")]
    return prayers, dailies


def summarize(prayers: list[str], dailies: list[tuple[str, int]]) -> tuple[str, str, str]:
    """Return (headline, detail, priority, tags-as-one) — grouped, de-duplicated, a
    flame on at-risk streaks."""
    total = len(prayers) + len(dailies)
    if total == 0:
        return "All done today — everything is logged. 🌙", "low", "white_check_mark"

    blocks = []
    if prayers:
        blocks.append(f"Prayers · {len(prayers)}\n" + ", ".join(prayers))
    if dailies:
        ordered = sorted(dailies, key=lambda d: (d[1] >= STREAK_RISK, d[1]), reverse=True)
        rows = [f"{name} · {streak} 🔥" if streak >= STREAK_RISK else name
                for name, streak in ordered]
        blocks.append(f"Dailies · {len(dailies)}\n" + "\n".join(rows))

    urgent = any(streak >= STREAK_RISK for _, streak in dailies)
    headline = f"{total} left before midnight"
    priority, tag = ("high", "warning") if urgent else ("default", "bell")
    return f"{headline}\n\n" + "\n\n".join(blocks), priority, tag


class HabiticaSource:
    id = "habitica"

    def check(self, now: datetime, config: dict) -> list[Notification]:
        if not api.configured():
            return []                                       # Habitica is optional
        forced = bool(config.get("force"))                  # on-demand 'send now' button
        if not forced:
            if not config.get("enabled", True):
                return []
            nudge_time = str(config.get("nudge_time") or config.get("time") or "21:30")
            if not _due_now(now, nudge_time, int(config.get("window", WINDOW_MIN))):
                return []
        try:
            tasks = api.fetch_tasks_by_type()
        except Exception:
            return []                                       # Habitica down → skip tonight, don't crash
        body, priority, tag = summarize(*collect(tasks))
        dedup = None if forced else NUDGE_TITLE              # forced always delivers; scheduled dedups
        return [Notification(NUDGE_TITLE, body, priority=priority, tags=(tag,), dedup_key=dedup)]
