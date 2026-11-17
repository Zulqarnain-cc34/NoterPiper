"""Date reminders — birthdays, bills, document expiry, from a simple list.

No API, pure date math. Each item is a label + a date; the plugin reminds you a set
number of days ahead. A date written `MM-DD` recurs every year (a birthday); written
`YYYY-MM-DD` it's a one-off (a bill, a passport expiry) and stops once it's past. Fires
once a day at the set time. `now` is engine-supplied, so the logic is pure and testable.
"""

from __future__ import annotations

from datetime import date, datetime

from ...engine import Notification
from .._common import due_now as _due_now

WINDOW_MIN = 5


def _date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:  # e.g. Feb 29 in a common year
        return None


def next_occurrence(raw: str, today: date) -> date | None:
    """The next date on/after `today` for an item's date string. `MM-DD` recurs yearly;
    `YYYY-MM-DD` is one-off (None once it's past)."""
    try:
        parts = [int(x) for x in str(raw).strip().split("-")]
    except ValueError:
        return None
    if len(parts) == 2:  # MM-DD → recurring
        m, d = parts
        this = _date(today.year, m, d)
        if this is None:
            return None
        return this if this >= today else _date(today.year + 1, m, d)
    if len(parts) == 3:  # YYYY-MM-DD → one-off
        one = _date(*parts)
        return one if one is not None and one >= today else None
    return None


class DateRemindersSource:
    id = "dates"
    wants_location = False
    defaults = {"enabled": True, "lead_days": 3, "time": "09:00", "window": WINDOW_MIN, "items": []}
    config_schema = [
        {"key": "enabled", "type": "toggle", "label": "Date reminders"},
        {
            "key": "lead_days",
            "type": "stepper",
            "label": "Remind ahead",
            "hint": "days before the date",
            "min": 0,
            "max": 30,
            "unit": "days",
        },
        {"key": "time", "type": "time", "label": "Time"},
        {
            "key": "items",
            "type": "list",
            "label": "Dates",
            "hint": "pick a date — toggle 'every year' for a birthday",
            # recurring: the date control pairs with an "every year" toggle. On → the date is
            # stored as MM-DD (recurs yearly); off → YYYY-MM-DD (a one-off). Logic unchanged.
            "recurring": True,
            "fields": [
                {"key": "label", "type": "text", "label": "What"},
                {"key": "date", "type": "date", "label": "Date"},
            ],
        },
    ]

    def check(self, now: datetime, config: dict) -> list[Notification]:
        forced = bool(config.get("force"))
        if not forced:
            if not config.get("enabled", True):
                return []
            if not _due_now(
                now, config.get("time", "09:00"), int(config.get("window", WINDOW_MIN))
            ):
                return []
        today = now.date()
        lead = int(config.get("lead_days", 3))
        out: list[Notification] = []
        for item in config.get("items", []):
            label = item.get("label", "").strip() if isinstance(item, dict) else ""
            if not label:
                continue
            d = next_occurrence(item.get("date"), today)
            if d is None:
                continue
            days = (d - today).days
            if not 0 <= days <= lead:
                continue
            when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            out.append(
                Notification(label, when, priority="default", tags=("calendar",), dedup_key=label)
            )
        return out
