"""Habitica nightly-nudge source — the second plugin.

One calm end-of-day summary of everything still open: unlogged prayer habits, due
dailies (streaks at risk flagged first), and every open to-do (overdue flagged first).
Gated to fire only
when Habitica is configured, the nudge is enabled, and it's the set time. A stable
title ("Nightly check-in") gives it robust once-per-day dedup under the ~2-min engine.

The message leads with urgency (at-risk streaks, overdue to-dos) and caps each group
to a few names with "+N more", so it stays readable whether you have 3 items or 30.
"""
from __future__ import annotations

from datetime import date, datetime

from ... import api
from ...engine import Notification

PRAYERS = ("Fajr", "Zohar", "Asr", "Maghrib", "Isha")
STREAK_RISK = 7          # a daily with a streak this long is "at risk" if still unticked
WINDOW_MIN = 5           # fire within this many minutes after the set time
NUDGE_TITLE = "Nightly check-in"
CAP = 5                  # max names listed per group before "+N more"


def _due_now(now: datetime, target_hhmm: str, window: int = WINDOW_MIN) -> bool:
    th, tm = (int(x) for x in target_hhmm.split(":")[:2])
    delta = (now.hour * 60 + now.minute) - (th * 60 + tm)
    return 0 <= delta < window


def _todo_date(todo: dict) -> date | None:
    """A to-do's due date (date only), or None if it has none / is unparseable."""
    d = todo.get("date")
    if not d:
        return None
    try:
        return date.fromisoformat(str(d)[:10])
    except ValueError:
        return None


def collect(tasks: dict, now: datetime, streak_risk: int = STREAK_RISK) -> dict:
    """Group everything still open tonight. `streak_risk` is the streak length at or
    above which an unticked daily is flagged "at risk" and pushed to the top."""
    today = now.date()
    prayers = [h["text"].strip() for h in tasks.get("habits", [])
               if any(p in h.get("text", "") for p in PRAYERS)
               and (h.get("counterUp", 0) + h.get("counterDown", 0)) == 0]

    due_dailies = [(d["text"].strip(), int(d.get("streak", 0))) for d in tasks.get("dailys", [])
                   if d.get("isDue") and not d.get("completed")]
    at_risk = sorted((t for t in due_dailies if t[1] >= streak_risk),
                     key=lambda t: t[1], reverse=True)
    dailies = [name for name, streak in due_dailies if streak < streak_risk]

    todos_overdue, todos_open = [], []
    for t in tasks.get("todos", []):
        if t.get("completed"):
            continue                                 # only completed to-dos are excluded
        d = _todo_date(t)
        if d is not None and d < today:
            todos_overdue.append(t["text"].strip())  # past its due date → flagged, shown first
        else:
            todos_open.append(t["text"].strip())     # due today, future, or undated — all still open

    return {"prayers": prayers, "at_risk": at_risk, "dailies": dailies,
            "todos_overdue": todos_overdue, "todos_due": todos_open}


def _cap(names: list[str]) -> str:
    if len(names) <= CAP:
        return ", ".join(names)
    return ", ".join(names[:CAP]) + f", +{len(names) - CAP} more"


def summarize(c: dict) -> tuple[str, str, str]:
    """One grouped, scalable message. Returns (body, priority, tags-as-one)."""
    at_risk, overdue, due = c["at_risk"], c["todos_overdue"], c["todos_due"]
    todos = [f"{t} (overdue)" for t in overdue] + due
    total = len(at_risk) + len(todos) + len(c["dailies"]) + len(c["prayers"])
    if total == 0:
        return "All done today — everything is logged. 🌙", "low", "white_check_mark"

    blocks = []
    if at_risk:
        blocks.append(f"At risk · {len(at_risk)}\n" + _cap([f"{n} · {s}" for n, s in at_risk]))
    if todos:
        blocks.append(f"To-dos · {len(todos)}\n" + _cap(todos))
    if c["dailies"]:
        blocks.append(f"Dailies · {len(c['dailies'])}\n" + _cap(c["dailies"]))
    if c["prayers"]:
        blocks.append(f"Prayers · {len(c['prayers'])}\n" + _cap(c["prayers"]))

    headline = f"{total} left before midnight"
    if at_risk:
        headline += f" · {len(at_risk)} at risk 🔥"
    priority, tag = ("high", "warning") if (at_risk or overdue) else ("default", "bell")
    return f"{headline}\n\n" + "\n\n".join(blocks), priority, tag


class HabiticaSource:
    id = "habitica"

    def check(self, now: datetime, config: dict) -> list[Notification]:
        if not api.configured():
            return []                                       # Habitica is optional
        show_todos = config.get("show_todos", True)
        show_dailies = config.get("show_dailies", True)
        show_prayers = config.get("show_prayers", True)
        if not (show_todos or show_dailies or show_prayers):
            return []                                       # every group hidden → nothing to ever show
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
        c = collect(tasks, now, int(config.get("streak_risk", STREAK_RISK)))
        if not show_todos:                                  # include-toggles set in the app
            c["todos_overdue"], c["todos_due"] = [], []
        if not show_dailies:                                # dailies off → their at-risk goes too
            c["at_risk"], c["dailies"] = [], []
        if not show_prayers:
            c["prayers"] = []
        body, priority, tag = summarize(c)
        dedup = None if forced else NUDGE_TITLE              # forced always delivers; scheduled dedups
        return [Notification(NUDGE_TITLE, body, priority=priority, tags=(tag,), dedup_key=dedup)]
