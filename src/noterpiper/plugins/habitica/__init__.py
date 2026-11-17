"""Habitica nightly-nudge source — tag-driven.

One calm end-of-day summary of what you still owe today, grouped by *your own tags*
(see HABITICA-DATA-STANDARD.md). It reads only Habitica's structured fields, never the
wording of a title:

  • Dailies  — `isDue and not completed`; a long `streak` is flagged 🔥 at-risk.
  • To-dos   — `not completed`; past its `date` → "(overdue)".
  • Habits   — opt-in: shown only if *tagged* (and daily-reset & untapped).
  • Anything tagged `Archived` is skipped.

Each task's section is its first (non-Archived) tag; untagged dailies/to-dos fall back
to a "Dailies" / "To-dos" section, so it works with zero setup and gets better as you
tag. At-risk streaks are a cross-cutting block shown first. A stable title
("Nightly check-in") gives robust once-per-day dedup under the ~2-min engine.
"""

from __future__ import annotations

import urllib.error
from datetime import date, datetime

from ... import api
from ...engine import Notification

STREAK_RISK = 7  # a daily with a streak this long is "at risk" if still unticked
WINDOW_MIN = 5  # fire within this many minutes after the set time
NUDGE_TITLE = "Nightly check-in"
# ASCII title == dedup_key so the once/day dedup matches (see HABITICA notes / ntfy channel).
AUTH_FAIL_TITLE = "Habitica sign-in failed"
CAP = 5  # max names listed per group before "+N more"
ARCHIVED = "archived"  # tasks carrying a tag named this (any case) are hidden


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


def _tag_names(task: dict, tags: dict) -> list[str]:
    """The task's non-Archived tag names, in order."""
    return [tags[t] for t in task.get("tags", []) if tags.get(t) and tags[t].lower() != ARCHIVED]


def _archived(task: dict, tags: dict) -> bool:
    return any(tags.get(t, "").lower() == ARCHIVED for t in task.get("tags", []))


def _section(task: dict, tags: dict, fallback: str) -> str:
    """Section = the first non-Archived tag (capitalised), else the type fallback."""
    names = _tag_names(task, tags)
    return names[0].capitalize() if names else fallback


class _Owed:
    """Accumulates what's still owed today as collect() walks the tasks."""

    def __init__(self) -> None:
        self.at_risk: list[tuple[str, int]] = []  # dailies over the streak threshold (cross-cut)
        self.sections: dict[str, list[str]] = {}  # section name → display names
        self.overdue: list[str] = []

    def add(self, section: str, display: str) -> None:
        self.sections.setdefault(section, []).append(display)


def _owe_daily(owed: _Owed, d: dict, tags: dict, streak_risk: int) -> None:
    if not d.get("isDue") or d.get("completed") or _archived(d, tags):
        return
    name, streak = d["text"].strip(), int(d.get("streak", 0))
    if streak >= streak_risk:
        owed.at_risk.append((name, streak))  # urgency trumps category
    else:
        owed.add(_section(d, tags, "Dailies"), name)


def _owe_todo(owed: _Owed, t: dict, tags: dict, today: date) -> None:
    if t.get("completed") or _archived(t, tags):
        return
    name = t["text"].strip()
    dd = _todo_date(t)
    if dd is not None and dd < today:
        owed.overdue.append(name)
        owed.add(_section(t, tags, "To-dos"), f"{name} (overdue)")
    else:
        owed.add(_section(t, tags, "To-dos"), name)


def _owe_habit(owed: _Owed, h: dict, tags: dict) -> None:
    # Opt-in: counted only if tagged, daily-reset, a "good" habit, and untapped today.
    if _archived(h, tags) or h.get("frequency") != "daily" or not h.get("up"):
        return
    if (h.get("counterUp", 0) + h.get("counterDown", 0)) != 0:
        return
    names = _tag_names(h, tags)
    if names:
        owed.add(names[0].capitalize(), h["text"].strip())


def collect(tasks: dict, tags: dict, now: datetime, streak_risk: int = STREAK_RISK) -> dict:
    """Group everything still owed today by section. `tags` maps tag-id → name."""
    owed = _Owed()
    for d in tasks.get("dailys", []):
        _owe_daily(owed, d, tags, streak_risk)
    for t in tasks.get("todos", []):
        _owe_todo(owed, t, tags, now.date())
    for h in tasks.get("habits", []):
        _owe_habit(owed, h, tags)
    owed.at_risk.sort(key=lambda x: x[1], reverse=True)
    return {"at_risk": owed.at_risk, "sections": owed.sections, "overdue": owed.overdue}


def _cap(names: list[str]) -> str:
    if len(names) <= CAP:
        return ", ".join(names)
    return ", ".join(names[:CAP]) + f", +{len(names) - CAP} more"


# Sections that come from the type fallback (shown after the user's tag sections).
_FALLBACK = ("Dailies", "To-dos")


def summarize(c: dict) -> tuple[str, str, str]:
    """One grouped, scalable message. Returns (body, priority, tags-as-one)."""
    at_risk, sections, overdue = c["at_risk"], c["sections"], c["overdue"]
    total = len(at_risk) + sum(len(v) for v in sections.values())
    if total == 0:
        return "All done today — everything is logged. 🌙", "low", "white_check_mark"

    blocks = []
    if at_risk:
        blocks.append(f"At risk · {len(at_risk)}\n" + _cap([f"{n} · {s}" for n, s in at_risk]))
    tag_sections = sorted(
        (s for s in sections if s not in _FALLBACK), key=lambda s: len(sections[s]), reverse=True
    )
    for s in list(tag_sections) + [s for s in _FALLBACK if s in sections]:
        blocks.append(f"{s} · {len(sections[s])}\n" + _cap(sections[s]))

    headline = f"{total} left before midnight"
    if at_risk:
        headline += f" · {len(at_risk)} at risk 🔥"
    priority, tag = ("high", "warning") if (at_risk or overdue) else ("default", "bell")
    return f"{headline}\n\n" + "\n\n".join(blocks), priority, tag


class HabiticaSource:
    id = "habitica"
    wants_location = False
    defaults = {"enabled": True, "time": "21:30", "window": WINDOW_MIN, "streak_risk": STREAK_RISK}
    # No config_schema: the config page hand-builds this card (docs/index.html), so the
    # generator must not auto-emit competing controls. See PLUGIN-AUTHORING "config UI".

    def check(self, now: datetime, config: dict) -> list[Notification]:
        if not api.configured():
            return []  # Habitica is optional
        forced = bool(config.get("force"))  # on-demand 'send now' button
        if not forced:
            if not config.get("enabled", True):
                return []
            nudge_time = str(config.get("nudge_time") or config.get("time") or "21:30")
            if not _due_now(now, nudge_time, int(config.get("window", WINDOW_MIN))):
                return []
        try:
            tasks = api.fetch_tasks_by_type()
            tags = api.fetch_tags()
        except urllib.error.HTTPError as e:
            # 401/403 = bad or expired token / user id — surface it, don't go silent forever.
            if e.code in (401, 403):
                return [
                    Notification(
                        AUTH_FAIL_TITLE,
                        "Your Habitica API token or user ID looks wrong — update the secrets.",
                        priority="high",
                        tags=("warning",),
                        dedup_key=None if forced else AUTH_FAIL_TITLE,
                    )
                ]
            return []  # other HTTP error (5xx, etc.) → skip tonight, don't crash
        except Exception:
            return []  # Habitica down / network → skip tonight, don't crash
        c = collect(tasks, tags, now, int(config.get("streak_risk", STREAK_RISK)))
        body, priority, tag = summarize(c)
        dedup = None if forced else NUDGE_TITLE  # forced always delivers; scheduled dedups
        return [Notification(NUDGE_TITLE, body, priority=priority, tags=(tag,), dedup_key=dedup)]
