"""Habitica nightly-nudge source — tag-driven.

One calm end-of-day summary of what you still owe today (see HABITICA-SETUP.md). It
reads only Habitica's structured fields, never the wording of a title:

  • Dailies  — due today (`isDue`, any frequency) and not done; long `streak` → 🔥 at-risk.
  • To-dos   — due today or overdue are listed; undated / later ones become a backlog count.
  • Habits   — daily-reset "good" (+) habits still untapped today (weekly/monthly left out).
  • Hidden   — tasks tagged `Archived`, or `#### …` / `-----` dividers, are skipped.

Each task's section is its first (non-Archived) tag; untagged tasks fall back to a
"Dailies" / "To-dos" / "Habits" section — so it works with zero setup for any layout. The
one message is ordered by urgency — at-risk → overdue → due-today sections (hardest first)
→ a backlog count. A stable title ("Nightly check-in") gives once-per-day dedup.
"""

from __future__ import annotations

import re
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


def _allowed_tags(task: dict, tags: dict, whitelist: list[str] | None) -> bool:
    """Check if task's first tag is in the whitelist. None = allow all."""
    if whitelist is None:
        return True
    tag_names = [tags[t] for t in task.get("tags", []) if tags.get(t) and tags[t].lower() != ARCHIVED]
    if not tag_names:
        return True  # untagged tasks are always allowed
    return tag_names[0] in whitelist


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


_HEADER = re.compile(r"^#{1,6}\s")  # "#### Morning" — a markdown header used as a divider
_RULE = re.compile(r"^[\s#=_*~·—–-]{3,}$")  # "-----", "######", "———", "===" — a separator rule


def _is_divider(text: str) -> bool:
    """A visual divider/header, not a real task — e.g. '#### Morning' or '-------'."""
    t = text.strip()
    return bool(_HEADER.match(t) or _RULE.match(t))


def _hidden(task: dict, tags: dict) -> bool:
    """Never shown: tagged Archived, or a markdown-header / separator divider (any tags)."""
    return _archived(task, tags) or _is_divider(task.get("text", ""))


def _section(task: dict, tags: dict, fallback: str) -> str:
    """Section = the first non-Archived tag (capitalised), else the type fallback."""
    names = _tag_names(task, tags)
    return names[0].capitalize() if names else fallback


def _priority(task: dict) -> float:
    """Habitica difficulty: 0.1 Trivial · 1 Easy · 1.5 Medium · 2 Hard (higher = harder)."""
    try:
        return float(task.get("priority", 1) or 1)
    except (TypeError, ValueError):
        return 1.0


class _Owed:
    """Tonight's work as collect() walks the tasks. Section items carry a priority so the
    summary can lead with the hard ones; open to-dos not owed tonight are just counted."""

    def __init__(self) -> None:
        self.at_risk: list[tuple[str, int]] = []  # dailies over the streak threshold (cross-cut)
        self.overdue: list[tuple[str, float]] = []  # to-dos past their due date
        self.sections: dict[str, list[tuple[str, float]]] = {}  # section → [(name, priority)]
        self.later = 0  # open to-dos not owed tonight (undated or scheduled later) → a count

    def add(self, section: str, name: str, prio: float) -> None:
        self.sections.setdefault(section, []).append((name, prio))


def _owe_daily(
    owed: _Owed, d: dict, tags: dict, streak_risk: int, notify_dailies: bool = True, tag_whitelist: list[str] | None = None
) -> None:
    if not notify_dailies or not d.get("isDue") or d.get("completed") or _hidden(d, tags):
        return
    if not _allowed_tags(d, tags, tag_whitelist):
        return
    name, streak = d["text"].strip(), int(d.get("streak", 0))
    if streak >= streak_risk:
        owed.at_risk.append((name, streak))  # urgency trumps category
    else:
        owed.add(_section(d, tags, "Dailies"), name, _priority(d))


def _owe_todo(
    owed: _Owed, t: dict, tags: dict, today: date, notify_todos: bool = True, tag_whitelist: list[str] | None = None
) -> None:
    if t.get("completed") or _hidden(t, tags):
        return
    name, prio = t["text"].strip(), _priority(t)
    dd = _todo_date(t)
    if dd is None or dd > today:  # undated or scheduled later → backlog, not owed tonight
        owed.later += 1
    elif dd < today:  # overdue — you're late; gets its own urgent block (always shown)
        owed.overdue.append((name, prio))
    else:  # due today — respect notify_todos
        if notify_todos and _allowed_tags(t, tags, tag_whitelist):
            owed.add(_section(t, tags, "To-dos"), name, prio)


def _owe_habit(
    owed: _Owed, h: dict, tags: dict, notify_habits: bool = True, tag_whitelist: list[str] | None = None
) -> None:
    # Only a daily-reset "good" (+) habit has a daily "did you do it today?". Weekly/monthly
    # habits reset on their own cycle — no nightly deadline — so they're never owed tonight.
    # Untagged daily habits fall back to "Habits" (like dailies/to-dos), never vanish.
    # Defaults match Habitica's: a habit with no frequency is daily, no `up` is a good habit.
    if not notify_habits or _hidden(h, tags) or h.get("frequency", "daily") != "daily" or not h.get("up", True):
        return
    if not _allowed_tags(h, tags, tag_whitelist):
        return
    if (h.get("counterUp", 0) + h.get("counterDown", 0)) != 0:
        return  # already tapped today
    owed.add(_section(h, tags, "Habits"), h["text"].strip(), _priority(h))


def collect(
    tasks: dict,
    tags: dict,
    now: datetime,
    streak_risk: int = STREAK_RISK,
    notify_dailies: bool = True,
    notify_habits: bool = True,
    notify_todos: bool = True,
    tag_whitelist: list[str] | None = None,
) -> dict:
    """Tonight's work grouped by section; open to-dos not owed tonight are counted as backlog."""
    owed = _Owed()
    for d in tasks.get("dailys", []):
        _owe_daily(owed, d, tags, streak_risk, notify_dailies, tag_whitelist)
    for t in tasks.get("todos", []):
        _owe_todo(owed, t, tags, now.date(), notify_todos, tag_whitelist)
    for h in tasks.get("habits", []):
        _owe_habit(owed, h, tags, notify_habits, tag_whitelist)
    return {
        "at_risk": owed.at_risk,
        "overdue": owed.overdue,
        "sections": owed.sections,
        "later": owed.later,
    }


def _cap(names: list[str]) -> str:
    if len(names) <= CAP:
        return ", ".join(names)
    return ", ".join(names[:CAP]) + f", +{len(names) - CAP} more"


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


# Sections that come from the type fallback (shown after the user's tag sections).
_FALLBACK = ("Dailies", "To-dos", "Habits")


def summarize(c: dict) -> tuple[str, str, str]:
    """One ruthlessly-ordered message — at-risk → overdue → due-today → backlog count — so
    the single nightly notification leads with what hurts to miss. Returns (body, priority, tag)."""
    at_risk, overdue, sections, later = c["at_risk"], c["overdue"], c["sections"], c["later"]
    time_bound = len(at_risk) + len(overdue) + sum(len(v) for v in sections.values())

    if time_bound == 0:  # nothing owed tonight — stay calm, just note any backlog
        tail = (
            f" — {later} open to-do{_plural(later)} whenever you like"
            if later
            else " — everything is logged"
        )
        return f"All done today{tail}. 🌙", "low", "white_check_mark"

    blocks = []
    if at_risk:
        at_risk.sort(key=lambda x: x[1], reverse=True)  # longest streak first
        blocks.append(f"At risk · {len(at_risk)}\n" + _cap([f"{n} · {s}" for n, s in at_risk]))
    if overdue:
        overdue.sort(key=lambda x: x[1], reverse=True)  # hardest first
        blocks.append(f"Overdue · {len(overdue)}\n" + _cap([n for n, _ in overdue]))
    tag_sections = sorted(
        (s for s in sections if s not in _FALLBACK), key=lambda s: len(sections[s]), reverse=True
    )
    for s in list(tag_sections) + [s for s in _FALLBACK if s in sections]:
        names = [n for n, _ in sorted(sections[s], key=lambda x: x[1], reverse=True)]  # hard first
        blocks.append(f"{s} · {len(names)}\n" + _cap(names))
    if later:
        blocks.append(f"+ {later} open to-do{_plural(later)} in your backlog")

    headline = f"{time_bound} to do before midnight"
    if at_risk:
        headline += f" · {len(at_risk)} at risk 🔥"
    priority, tag = ("high", "warning") if (at_risk or overdue) else ("default", "bell")
    return f"{headline}\n\n" + "\n\n".join(blocks), priority, tag


class HabiticaSource:
    id = "habitica"
    wants_location = False
    defaults = {
        "enabled": True,
        "time": "21:30",
        "window": WINDOW_MIN,
        "streak_risk": STREAK_RISK,
        "notify_dailies": True,
        "notify_habits": True,
        "notify_todos": True,
        "tag_whitelist": None,
    }
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
        c = collect(
            tasks,
            tags,
            now,
            int(config.get("streak_risk", STREAK_RISK)),
            config.get("notify_dailies", True),
            config.get("notify_habits", True),
            config.get("notify_todos", True),
            config.get("tag_whitelist"),
        )
        body, priority, tag = summarize(c)
        dedup = None if forced else NUDGE_TITLE  # forced always delivers; scheduled dedups
        return [Notification(NUDGE_TITLE, body, priority=priority, tags=(tag,), dedup_key=dedup)]
