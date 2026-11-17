"""Helpers shared by the in-repo plugins — one copy of the timing math.

Every plugin gates on "is `now` inside the window at/after a target time?". Two shapes
exist: a clock string ("HH:MM" — habitica, dates) and a concrete datetime (prayer,
ramadan). Both live here so the four former copies can't drift again.

Known limit: the clock-string window doesn't wrap midnight — a 23:58 target only gets
its pre-midnight ticks. Fine for the ~2-min external timer; don't set times that late.
"""

from __future__ import annotations

from datetime import datetime


def due_now(now: datetime, target_hhmm: str, window: int) -> bool:
    """True while `now` is within `window` minutes at/after the HH:MM target.
    A malformed target is never due — a config typo must not crash a source."""
    try:
        th, tm = (int(x) for x in str(target_hhmm).split(":")[:2])
    except ValueError:
        return False
    delta = (now.hour * 60 + now.minute) - (th * 60 + tm)
    return 0 <= delta < window


def due_at(remind: datetime, now: datetime, window: int) -> bool:
    """True while `now` is within `window` minutes at/after the `remind` moment."""
    return 0 <= (now - remind).total_seconds() / 60 < window


def fmt(t: datetime) -> str:
    """'5:03 PM' — the human time used in notification bodies."""
    return t.strftime("%I:%M %p").lstrip("0")


def to_dt(hhmm: str, ref: datetime) -> datetime:
    """Aladhan's 'HH:MM' (possibly with a trailing ' (TZ)') on `ref`'s date."""
    h, m = (int(x) for x in hhmm.split()[0].split(":")[:2])
    return ref.replace(hour=h, minute=m, second=0, microsecond=0)
