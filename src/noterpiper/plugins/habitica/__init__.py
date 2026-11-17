"""Habitica nudge source — tag-driven, up to three pushes.

The core is one calm end-of-day summary of what you still owe today (see
HABITICA-SETUP.md). It reads only Habitica's structured fields, never the wording of
a title:

  • Dailies  — due today (`isDue`, any frequency) and not done; long `streak` → 🔥 at-risk.
  • To-dos   — due today or overdue are listed; undated / later ones become a backlog count.
  • Habits   — daily-reset "good" (+) habits still untapped today (weekly/monthly left out).
  • Hidden   — tasks tagged `Archived`, or `#### …` / `-----` dividers, are skipped.

Each task's section is its first (non-Archived) tag; untagged tasks fall back to a
"Dailies" / "To-dos" / "Habits" section — so it works with zero setup for any layout. The
message is ordered by urgency — at-risk → overdue → due-today sections (hardest first)
→ a backlog count. A stable title gives each push once-per-day dedup.

Three pushes, each with its own switch and clock:

  • Evening ("Nightly check-in")       — the classic nudge; top-level `enabled`/`time`
    (what the phone page writes), or a nested `evening: {enabled, time}` override.
  • Morning ("Habitica morning briefing") — opt-in `morning: {enabled, time}`; counts
    only, no names — a heads-up, not a list.
  • Weekly ("Habitica weekly digest")  — opt-in `weekly: {enabled, day, time}`; stats
    aggregated from the week's runs (see `state.py` for the persistence caveat).

Quiet mode: `notify_dailies` / `notify_habits` / `notify_todos` drop a whole type, and
`tag_whitelist` (list or comma string, case-insensitive) keeps only those sections —
except overdue to-dos, which are always shown: being late outranks being quiet.

The on-demand "send now" button (`force`) sends exactly one push — the full summary —
bypassing every gate and dedup.
"""

from __future__ import annotations

import re
import urllib.error
from datetime import date, datetime

from ... import api
from ...engine import Notification
from .._common import due_now
from . import weekly

STREAK_RISK = 7  # a daily with a streak this long is "at risk" if still unticked
WINDOW_MIN = 5  # fire within this many minutes after the set time
NUDGE_TITLE = "Nightly check-in"
MORNING_TITLE = "Habitica morning briefing"
WEEKLY_TITLE = "Habitica weekly digest"
# ASCII title == dedup_key so the once/day dedup matches (see HABITICA notes / ntfy channel).
AUTH_FAIL_TITLE = "Habitica sign-in failed"
CAP = 5  # max names listed per group before "+N more"
ARCHIVED = "archived"  # tasks carrying a tag named this (any case) are hidden


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


def _parse_whitelist(raw) -> list[str] | None:
    """Normalize `tag_whitelist` to lowercase names. None / empty / garbage → no filtering.
    Accepts a list or a comma-separated string (what a config text field stores)."""
    if isinstance(raw, str):
        raw = raw.split(",")
    if not isinstance(raw, (list, tuple, set)):
        return None  # None, or a malformed config value — filtering off beats crashing
    names = [str(p).strip().lower() for p in raw if str(p).strip()]
    return names or None


def _allowed_tags(task: dict, tags: dict, whitelist: list[str] | None) -> bool:
    """True if the task's section tag passes the (lowercased) whitelist.
    Untagged tasks always pass — a whitelist narrows sections, it can't orphan tasks."""
    if whitelist is None:
        return True
    names = _tag_names(task, tags)
    return not names or names[0].lower() in whitelist


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
    summary can lead with the hard ones; open to-dos not owed tonight are just counted.
    `counts` tracks how many of each type made it in — the morning brief's breakdown."""

    def __init__(self) -> None:
        self.at_risk: list[tuple[str, int]] = []  # dailies over the streak threshold (cross-cut)
        self.overdue: list[tuple[str, float]] = []  # to-dos past their due date
        self.sections: dict[str, list[tuple[str, float]]] = {}  # section → [(name, priority)]
        self.later = 0  # open to-dos not owed tonight (undated or scheduled later) → a count
        self.counts = {"dailies": 0, "habits": 0, "todos": 0}  # shown items, by type

    def add(self, section: str, name: str, prio: float) -> None:
        self.sections.setdefault(section, []).append((name, prio))


def _owe_daily(
    owed: _Owed,
    d: dict,
    tags: dict,
    streak_risk: int,
    notify_dailies: bool = True,
    tag_whitelist: list[str] | None = None,
) -> None:
    if not notify_dailies or not d.get("isDue") or d.get("completed") or _hidden(d, tags):
        return
    if not _allowed_tags(d, tags, tag_whitelist):
        return
    name, streak = d["text"].strip(), int(d.get("streak", 0))
    owed.counts["dailies"] += 1
    if streak >= streak_risk:
        owed.at_risk.append((name, streak))  # urgency trumps category
    else:
        owed.add(_section(d, tags, "Dailies"), name, _priority(d))


def _owe_todo(
    owed: _Owed,
    t: dict,
    tags: dict,
    today: date,
    notify_todos: bool = True,
    tag_whitelist: list[str] | None = None,
) -> None:
    if t.get("completed") or _hidden(t, tags):
        return
    name, prio = t["text"].strip(), _priority(t)
    dd = _todo_date(t)
    if dd and dd < today:  # overdue — urgent, shown despite quiet mode
        owed.overdue.append((name, prio))
        owed.counts["todos"] += 1
        return
    if not notify_todos or not _allowed_tags(t, tags, tag_whitelist):
        return  # quiet mode: no section entry AND no backlog mention
    if dd is None or dd > today:  # undated or scheduled later → backlog, not owed tonight
        owed.later += 1
    else:  # due today → its section
        owed.add(_section(t, tags, "To-dos"), name, prio)
        owed.counts["todos"] += 1


def _owe_habit(
    owed: _Owed,
    h: dict,
    tags: dict,
    notify_habits: bool = True,
    tag_whitelist: list[str] | None = None,
) -> None:
    # Only a daily-reset "good" (+) habit has a daily "did you do it today?". Weekly/monthly
    # habits reset on their own cycle — no nightly deadline — so they're never owed tonight.
    # Untagged daily habits fall back to "Habits" (like dailies/to-dos), never vanish.
    # Defaults match Habitica's: a habit with no frequency is daily, no `up` is a good habit.
    if (
        not notify_habits
        or _hidden(h, tags)
        or h.get("frequency", "daily") != "daily"
        or not h.get("up", True)
    ):
        return
    if not _allowed_tags(h, tags, tag_whitelist):
        return
    if (h.get("counterUp", 0) + h.get("counterDown", 0)) != 0:
        return  # already tapped today
    owed.counts["habits"] += 1
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
    wl = _parse_whitelist(tag_whitelist)
    for d in tasks.get("dailys", []):
        _owe_daily(owed, d, tags, streak_risk, notify_dailies, wl)
    for t in tasks.get("todos", []):
        _owe_todo(owed, t, tags, now.date(), notify_todos, wl)
    for h in tasks.get("habits", []):
        _owe_habit(owed, h, tags, notify_habits, wl)
    return {
        "at_risk": owed.at_risk,
        "overdue": owed.overdue,
        "sections": owed.sections,
        "later": owed.later,
        "counts": owed.counts,
    }


def _cap(names: list[str]) -> str:
    if len(names) <= CAP:
        return ", ".join(names)
    return ", ".join(names[:CAP]) + f", +{len(names) - CAP} more"


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


# Sections that come from the type fallback (shown after the user's tag sections).
_FALLBACK = ("Dailies", "To-dos", "Habits")


def summarize_morning(c: dict) -> tuple[str, str, str]:
    """Brief morning heads-up — counts by type, never task names. Returns (body, priority, tag)."""
    at_risk, overdue, sections = c["at_risk"], c["overdue"], c["sections"]
    time_bound = len(at_risk) + len(overdue) + sum(len(v) for v in sections.values())
    if time_bound == 0:
        return "Nothing owed today — great start! 🌅", "low", "sunny"

    n = c["counts"]  # collect() always provides it; every shown item bumps a bucket
    d, h, t = n["dailies"], n["habits"], n["todos"]
    parts = []
    if d:
        parts.append(f"{d} dail{'y' if d == 1 else 'ies'}")
    if h:
        parts.append(f"{h} habit{_plural(h)}")
    if t:
        parts.append(f"{t} to-do{_plural(t)}")
    line = " · ".join(parts)
    if at_risk:
        line += f" · {len(at_risk)} at risk 🔥"
    urgent = bool(at_risk or overdue)
    body = f"{line}\n\nGet ready for today! 🌅"
    return body, ("high" if urgent else "default"), ("warning" if urgent else "sunny")


def summarize_weekly(stats: dict, week_start: date, week_end: date) -> tuple[str, str, str]:
    """Weekly aggregated summary. Returns (body, priority, tag)."""
    total = stats.get("total_items", 0)
    best_name, best_streak = stats.get("best_streak") or (None, 0)
    any_at_risk = bool(stats.get("any_at_risk"))
    sample = stats.get("at_risk_sample")

    week_str = f"{week_start.strftime('%b %d')}–{week_end.strftime('%d')}"
    blocks = []
    if total > 0:
        blocks.append(f"{total} item{_plural(total)} due this week")
    if best_name and best_streak > 0:
        blocks.append(f"Best streak · {best_name} ({best_streak})")
    if any_at_risk and sample:
        blocks.append(f"At risk · {sample}")
    if not blocks:
        blocks.append("All clear — nice week!")

    priority = "high" if any_at_risk else "default"
    tag = "warning" if any_at_risk else "white_check_mark"
    return f"Weekly Summary · {week_str}\n\n" + "\n\n".join(blocks), priority, tag


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


_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _weekly_digest(c: dict, now: datetime, cfg: dict, window: int) -> list[Notification]:
    """Record today's collect() into the week's state; emit the digest when its day/time hits."""
    if not cfg.get("enabled"):
        return []
    ws = weekly.append_daily_run(weekly.load_weekly_state(), c, now)
    weekly.save_weekly_state(ws)
    day = str(cfg.get("day", "Sunday")).strip().lower()
    if day not in _DAYS:
        print(f"[warn] habitica weekly digest: unknown day {cfg.get('day')!r}")
        return []
    if now.weekday() != _DAYS.index(day) or not due_now(
        now, str(cfg.get("time") or "19:00"), window
    ):
        return []
    stats = weekly.compute_weekly_stats(ws["day_runs"])
    week_start, week_end = weekly.get_weekly_bounds(now)
    body, priority, tag = summarize_weekly(stats, week_start, week_end)
    ws["day_runs"] = []  # the digest closes the week
    ws["last_digest_sent"] = now.isoformat()
    weekly.save_weekly_state(ws)
    return [
        Notification(WEEKLY_TITLE, body, priority=priority, tags=(tag,), dedup_key=WEEKLY_TITLE)
    ]


def _forced_push(c: dict, now: datetime, kind: str) -> Notification:
    """'Send now' = exactly one push in the chosen format. The full summary is both
    the default and the fallback — a corrupt weekly state must not eat a button press."""
    if kind == "morning":
        body, priority, tag = summarize_morning(c)
        return Notification(MORNING_TITLE, body, priority=priority, tags=(tag,), dedup_key=None)
    if kind == "weekly":
        try:
            ws = weekly.append_daily_run(weekly.load_weekly_state(), c, now)  # preview — not saved
            stats = weekly.compute_weekly_stats(ws["day_runs"])
            body, priority, tag = summarize_weekly(stats, *weekly.get_weekly_bounds(now))
            return Notification(WEEKLY_TITLE, body, priority=priority, tags=(tag,), dedup_key=None)
        except Exception as e:
            print(f"[warn] forced weekly preview failed ({e}); sending the full summary")
    body, priority, tag = summarize(c)
    return Notification(NUDGE_TITLE, body, priority=priority, tags=(tag,), dedup_key=None)


def _evening_push(c: dict, now: datetime, config: dict, window: int) -> list[Notification]:
    """The classic nightly nudge, when due. Top-level `enabled`/`time` drive it (that's
    what the phone page writes); a nested `evening` section overrides when present."""
    evening = config.get("evening") or {}
    evening_time = str(evening.get("time") or config.get("time") or "21:30")
    if not evening.get("enabled", True) or not due_now(now, evening_time, window):
        return []
    body, priority, tag = summarize(c)
    return [Notification(NUDGE_TITLE, body, priority=priority, tags=(tag,), dedup_key=NUDGE_TITLE)]


def _morning_push(c: dict, now: datetime, config: dict, window: int) -> list[Notification]:
    """The opt-in counts-only briefing, when due."""
    morning = config.get("morning") or {}
    if not morning.get("enabled") or not due_now(now, str(morning.get("time") or "06:00"), window):
        return []
    body, priority, tag = summarize_morning(c)
    return [
        Notification(MORNING_TITLE, body, priority=priority, tags=(tag,), dedup_key=MORNING_TITLE)
    ]


class HabiticaSource:
    id = "habitica"
    wants_location = False
    defaults = {
        "enabled": True,  # the evening nudge — the switch/clock the phone page writes
        "time": "21:30",
        "window": WINDOW_MIN,
        "streak_risk": STREAK_RISK,
        "notify_dailies": True,
        "notify_habits": True,
        "notify_todos": True,
        "tag_whitelist": None,
        "morning": {"enabled": False, "time": "06:00"},
        "weekly": {"enabled": False, "day": "Sunday", "time": "19:00"},
    }
    # No config_schema: the config page hand-builds this card (docs/index.html), so the
    # generator must not auto-emit competing controls. See PLUGIN-AUTHORING "config UI".

    def check(self, now: datetime, config: dict) -> list[Notification]:
        if not api.configured():
            return []  # Habitica is optional
        forced = bool(config.get("force"))  # on-demand 'send now' button
        if not forced and not config.get("enabled", True):
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
        if forced:
            kind = str(config.get("force_kind") or "evening").strip().lower()
            return [_forced_push(c, now, kind)]

        window = int(config.get("window", WINDOW_MIN))
        notifications = _evening_push(c, now, config, window)
        notifications += _morning_push(c, now, config, window)
        # Weekly digest — guarded: an aggregation bug must never cost the nightly nudge.
        try:
            notifications += _weekly_digest(c, now, config.get("weekly") or {}, window)
        except Exception as e:
            print(f"[warn] habitica weekly digest skipped: {e}")
        return notifications
