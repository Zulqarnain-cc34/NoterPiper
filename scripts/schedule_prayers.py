#!/usr/bin/env python3
"""Prayer-time reminders via ntfy.sh — precise, no server.

Run once each morning (GitHub Action). It fetches today's prayer times for your
city (Aladhan API, free), then **pre-schedules** 5 notifications on ntfy — each
delivered exactly LEAD_MIN minutes before that prayer's window ends, at max
priority (rings/vibrates like a call). ntfy handles the exact timing, so the
Action's own schedule can be loose.

Settings (in .env or as env vars / GitHub Secrets):
    NTFY_TOPIC   = your-secret-topic      (required to actually send)
    PRAYER_CITY  = Lahore                  (or Islamabad, or any city)
    LEAD_MIN     = 30                       (minutes before a prayer ends)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from habitica_etl import api, config  # noqa: E402  (reuse _load_env + PROJECT_ROOT)

PKT = timezone(timedelta(hours=5))

# Each prayer's window ends when the next time starts (Fajr ends at sunrise, …,
# Isha ends at Islamic midnight). Keys are Aladhan timing names.
ENDS_AT = {
    "Fajr": "Sunrise", "Zohar": "Asr", "Asr": "Maghrib",
    "Maghrib": "Isha", "Isha": "Midnight",
}
MESSAGES = {
    "Fajr": "🌅 Fajr ends soon — pray now and start your day in light.",
    "Zohar": "☀️ Zohar is ending — take a few minutes and pray.",
    "Asr": "🌤️ Asr ends soon — pause and pray before it passes.",
    "Maghrib": "🌇 Maghrib is short — pray now before Isha begins.",
    "Isha": "🌙 Isha ends soon — close your day with prayer.",
}


def setting(key: str, default: str | None = None) -> str | None:
    env = api._load_env(config.PROJECT_ROOT / ".env")
    return env.get(key) or os.environ.get(key) or default


def fetch_timings(city: str) -> dict[str, str]:
    url = "https://api.aladhan.com/v1/timingsByCity?" + urllib.parse.urlencode(
        {"city": city, "country": "Pakistan", "method": 1})  # 1 = Karachi method
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())["data"]["timings"]


def to_dt(hhmm: str, day: datetime) -> datetime:
    h, m = (int(x) for x in hhmm.split()[0].split(":")[:2])
    return datetime(day.year, day.month, day.day, h, m, tzinfo=PKT)


def schedule(topic: str, when: datetime, title: str, body: str) -> None:
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "max",                 # rings / bypasses silent
            "Tags": "mosque",
            "At": str(int(when.timestamp())),  # scheduled delivery
            "Click": "https://habitica.com",   # tap opens Habitica
        },
    )
    urllib.request.urlopen(req, timeout=15)


def main() -> int:
    city = setting("PRAYER_CITY", "Lahore")
    lead = int(setting("LEAD_MIN", "30"))
    topic = setting("NTFY_TOPIC")

    timings = fetch_timings(city)
    now = datetime.now(PKT)

    planned = []
    for prayer, end_key in ENDS_AT.items():
        end = to_dt(timings[end_key], now)
        if end <= now:                 # already passed (e.g. midnight rolled) → next day
            end += timedelta(days=1)
        remind = end - timedelta(minutes=lead)
        if remind <= now:
            continue
        planned.append((prayer, remind))
        if topic:
            schedule(topic, remind, f"🕌 {prayer} — time to pray", MESSAGES[prayer])

    print(f"City: {city} · lead: {lead} min · now: {now:%a %H:%M} PKT")
    for prayer, remind in planned:
        print(f"  {prayer:8} → remind {remind:%a %H:%M}  ({MESSAGES[prayer]})")
    if not topic:
        print("\n[dry-run — set NTFY_TOPIC in .env to actually schedule on your phone]")
    else:
        print(f"\nScheduled {len(planned)} reminders on ntfy.sh/{topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
