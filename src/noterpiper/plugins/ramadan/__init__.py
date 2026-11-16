"""Ramadan suhoor & iftar source.

During Ramadan (Hijri month 9), two reminders a day computed from Aladhan's Fajr and
Maghrib: a suhoor nudge a set number of minutes before Fajr (stop eating soon), and an
iftar nudge at Maghrib (break your fast). Silent the rest of the year — unless the
config page's 'send now' test forces a preview of today's times, so it can be verified
any time. `now` is engine-supplied (tz-aware), so the logic is pure and testable.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
from datetime import datetime, timedelta

from ... import net
from ...engine import Notification

RAMADAN = 9        # Hijri month number
WINDOW_MIN = 10    # fire if a run lands within this many minutes after the reminder time
SUHOOR_LEAD = 45   # default minutes before Fajr
IFTAR_LEAD = 0     # default minutes before Maghrib (0 = exactly at Maghrib)


def _fmt(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def _to_dt(hhmm: str, ref: datetime) -> datetime:
    h, m = (int(x) for x in hhmm.split()[0].split(":")[:2])
    return ref.replace(hour=h, minute=m, second=0, microsecond=0)


def _due(remind: datetime, now: datetime, window: int) -> bool:
    return 0 <= (now - remind).total_seconds() / 60 < window


def fetch_day(city: str, country: str, method: str) -> dict:
    """Today's timings + Hijri month number from Aladhan (same endpoint as the prayer
    plugin). Raises a clear, location-free error if the request is unusable."""
    url = "https://api.aladhan.com/v1/timingsByCity?" + urllib.parse.urlencode(
        {"city": city, "country": country, "method": method})
    try:
        payload = net.get_json(url)
    except urllib.error.HTTPError as e:
        if e.code < 500:
            raise RuntimeError(
                f"Aladhan rejected the configured location (HTTP {e.code}). "
                f"Check your city / country / method.") from e
        raise
    data = payload.get("data") if isinstance(payload, dict) else None
    timings = data.get("timings") if isinstance(data, dict) else None
    if not isinstance(timings, dict):
        raise RuntimeError("Aladhan returned no usable times for the configured location.")
    month = ((data.get("date") or {}).get("hijri") or {}).get("month") or {}
    try:
        hijri_month = int(month.get("number"))
    except (TypeError, ValueError):
        hijri_month = None
    return {"timings": timings, "hijri_month": hijri_month}


class RamadanSource:
    id = "ramadan"

    def check(self, now: datetime, config: dict) -> list[Notification]:
        forced = bool(config.get("force"))                  # config page's 'send now' test
        if not forced and not config.get("enabled", True):
            return []
        day = fetch_day(config.get("city"), config.get("country"), config.get("method"))
        try:
            fajr = _to_dt(day["timings"]["Fajr"], now)
            maghrib = _to_dt(day["timings"]["Maghrib"], now)
        except (KeyError, ValueError, TypeError):
            return []                                       # missing times → skip, don't crash

        if forced:                                          # preview today's times, any month / time
            return [Notification(
                "Ramadan preview",                          # ASCII title — ntfy puts it in an HTTP header;
                f"Suhoor ends {_fmt(fajr)} (Fajr) · Iftar {_fmt(maghrib)} (Maghrib)",
                priority="default", tags=("crescent_moon",), dedup_key=None)]   # 🌙 comes from the tag

        if day["hijri_month"] != RAMADAN:                   # scheduled runs: Ramadan only
            return []

        window = int(config.get("window", WINDOW_MIN))
        suhoor = fajr - timedelta(minutes=int(config.get("suhoor_lead", SUHOOR_LEAD)))
        iftar = maghrib - timedelta(minutes=int(config.get("iftar_lead", IFTAR_LEAD)))
        out: list[Notification] = []
        if _due(suhoor, now, window):                       # ASCII titles (HTTP header); emoji via tags
            out.append(Notification("Suhoor", f"Stop eating soon — Fajr at {_fmt(fajr)}",
                                    priority="high", tags=("crescent_moon",), dedup_key="suhoor"))
        if _due(iftar, now, window):
            out.append(Notification("Iftar", f"Time to break your fast — Maghrib at {_fmt(maghrib)}",
                                    priority="high", tags=("sunrise_over_mountains",), dedup_key="iftar"))
        return out
