"""Prayer-reminder source — the first plugin.

The prayer-time logic behind the Source contract: fetch today's times (Aladhan),
work out each prayer's reminder moment from its rule, and return the ones due *now*.
`now` is supplied by the engine (timezone-aware), so this is pure and testable.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
from datetime import datetime, timedelta

from ... import net
from ...engine import Notification

# When each prayer STARTS and when its window ENDS (ends when the next one starts;
# Isha ends at Islamic midnight).
STARTS_AT = {"Fajr": "Fajr", "Zohar": "Dhuhr", "Asr": "Asr", "Maghrib": "Maghrib", "Isha": "Isha"}
ENDS_AT = {
    "Fajr": "Sunrise",
    "Zohar": "Asr",
    "Asr": "Maghrib",
    "Maghrib": "Isha",
    "Isha": "Midnight",
}
DEFAULT_RULE = {"before_end": 30}
WINDOW_MIN = 5  # fire if a run lands within this many minutes after the reminder time
DEFAULT_REMINDERS = {
    "Fajr": {"before_end": 30},
    "Zohar": {"before_end": 30},
    "Asr": {"before_end": 30},
    "Maghrib": {"before_end": 30},
    "Isha": {"after_start": 60},
}


def _fmt(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def _to_dt(hhmm: str, ref: datetime) -> datetime:
    h, m = (int(x) for x in hhmm.split()[0].split(":")[:2])
    return ref.replace(hour=h, minute=m, second=0, microsecond=0)


def _reminder_dt(prayer: str, timings: dict, ref: datetime, rules: dict) -> datetime:
    rule = rules.get(prayer, DEFAULT_RULE)
    if "after_start" in rule:
        return _to_dt(timings[STARTS_AT[prayer]], ref) + timedelta(minutes=int(rule["after_start"]))
    return _to_dt(timings[ENDS_AT[prayer]], ref) - timedelta(
        minutes=int(rule.get("before_end", 30))
    )


def _due(remind: datetime, now: datetime, window: int = WINDOW_MIN) -> bool:
    return 0 <= (now - remind).total_seconds() / 60 < window


def fetch_timings(city: str, country: str, method: str) -> dict:
    """Today's prayer times for the city from Aladhan. Raises a clear, location-free
    error (public logs) if the request is rejected or the response is unusable."""
    url = "https://api.aladhan.com/v1/timingsByCity?" + urllib.parse.urlencode(
        {"city": city, "country": country, "method": method}
    )
    try:
        payload = net.get_json(url)
    except urllib.error.HTTPError as e:
        if e.code < 500:
            raise RuntimeError(
                f"Aladhan rejected the configured location (HTTP {e.code}). "
                f"Check your city / country / method."
            ) from e
        raise
    data = payload.get("data") if isinstance(payload, dict) else None
    timings = data.get("timings") if isinstance(data, dict) else None
    if not isinstance(timings, dict):
        raise RuntimeError("Aladhan returned no usable prayer times for the configured location.")
    return timings


class PrayerSource:
    id = "prayer"
    wants_location = True  # city/country/method/timezone come from the shared location
    defaults = {"window": WINDOW_MIN, "reminders": DEFAULT_REMINDERS}

    def check(self, now: datetime, config: dict) -> list[Notification]:
        timings = fetch_timings(config.get("city"), config.get("country"), config.get("method"))
        rules = config.get("reminders", {})
        window = int(config.get("window", WINDOW_MIN))
        out: list[Notification] = []
        for prayer in STARTS_AT:
            try:
                remind = _reminder_dt(prayer, timings, now, rules)
            except (KeyError, ValueError, TypeError):
                continue  # bad rule / missing timing → skip this one
            if not _due(remind, now, window):
                continue
            try:
                end = _to_dt(timings[ENDS_AT[prayer]], now)
                while end < remind:
                    end += timedelta(days=1)
                body = f"Time to pray · ends {_fmt(end)}"
            except (KeyError, ValueError, TypeError):
                body = "Time to pray"  # end time unavailable — still remind
            out.append(
                Notification(prayer, body, priority="max", tags=("mosque",), dedup_key=prayer)
            )
        return out
