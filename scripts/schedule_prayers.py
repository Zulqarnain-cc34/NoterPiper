#!/usr/bin/env python3
"""Prayer-time reminders via ntfy.sh — precise, serverless.

Run once each morning. Fetches today's prayer times for your city (Aladhan API),
then PRE-SCHEDULES one notification per prayer on ntfy, delivered at the exact
time (per reminders.json), at max priority. ntfy handles exact delivery, so this
job's own schedule can be loose. Works for any city — timezone comes from Aladhan.

Settings (env / .env):  NTFY_TOPIC, PRAYER_CITY, PRAYER_COUNTRY, PRAYER_METHOD.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muezzin import config, net  # noqa: E402

# Aladhan timing names for when each prayer STARTS and when its window ENDS
# (a prayer's window ends when the next one starts; Isha ends at Islamic midnight).
STARTS_AT = {"Fajr": "Fajr", "Zohar": "Dhuhr", "Asr": "Asr", "Maghrib": "Maghrib", "Isha": "Isha"}
ENDS_AT = {"Fajr": "Sunrise", "Zohar": "Asr", "Asr": "Maghrib", "Maghrib": "Isha", "Isha": "Midnight"}
DEFAULT_RULE = {"before_end": 30}
MESSAGES = {
    "Fajr": "🌅 Fajr ends soon — pray now and start your day in light.",
    "Zohar": "☀️ Zohar is ending — take a few minutes and pray.",
    "Asr": "🌤️ Asr ends soon — pause and pray before it passes.",
    "Maghrib": "🌇 Maghrib is short — pray now before Isha begins.",
    "Isha": "🌙 Isha ends soon — close your day with prayer.",
}


def load_rules() -> dict:
    """Read the editable reminders.json; fall back to 30-min-before-end."""
    try:
        data = json.loads((config.PROJECT_ROOT / "reminders.json").read_text())
        return {k: v for k, v in data.items() if not k.startswith("__")}
    except Exception:
        return {}


def fetch_timings(city: str, country: str, method: str) -> tuple[dict[str, str], str]:
    """Return (timings, IANA-timezone) for the city from Aladhan."""
    url = "https://api.aladhan.com/v1/timingsByCity?" + urllib.parse.urlencode(
        {"city": city, "country": country, "method": method})
    data = net.get_json(url)["data"]
    return data["timings"], data["meta"]["timezone"]


def to_dt(hhmm: str, ref: datetime) -> datetime:
    """Build ref's date at the given HH:MM in ref's timezone."""
    h, m = (int(x) for x in hhmm.split()[0].split(":")[:2])
    return ref.replace(hour=h, minute=m, second=0, microsecond=0)


def plan_reminders(timings: dict, now: datetime, rules: dict) -> list[tuple[str, datetime]]:
    """For each prayer, compute its reminder time from rules:
    {"before_end": N} → N min before the window ends; {"after_start": N} →
    N min after it begins. Past reminders roll to the next day. Pure & testable."""
    out = []
    for prayer in STARTS_AT:
        rule = rules.get(prayer, DEFAULT_RULE)
        if "after_start" in rule:
            remind = to_dt(timings[STARTS_AT[prayer]], now) + timedelta(minutes=int(rule["after_start"]))
        else:
            remind = to_dt(timings[ENDS_AT[prayer]], now) - timedelta(minutes=int(rule.get("before_end", 30)))
        if remind <= now:
            remind += timedelta(days=1)
        out.append((prayer, remind))
    out.sort(key=lambda x: x[1])
    return out


def schedule(topic: str, when: datetime, title: str, body: str) -> None:
    net.request(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,                    # ASCII only (HTTP header)
            "Priority": "max",                 # rings / bypasses silent
            "Tags": "mosque",
            "At": str(int(when.timestamp())),  # exact scheduled delivery
        },
    )


def main() -> int:
    city = config.env("PRAYER_CITY", "Lahore")
    country = config.env("PRAYER_COUNTRY", "Pakistan")
    method = config.env("PRAYER_METHOD", "1")
    topic = config.env("NTFY_TOPIC")
    rules = load_rules()

    timings, tzname = fetch_timings(city, country, method)
    now = datetime.now(ZoneInfo(tzname))
    planned = plan_reminders(timings, now, rules)

    sent = failed = 0
    for prayer, remind in planned:
        if topic:
            try:
                schedule(topic, remind, f"{prayer} - time to pray", MESSAGES[prayer])
                sent += 1
            except Exception as e:             # one failed send never aborts the rest
                failed += 1
                print(f"[warn] {prayer} reminder failed: {e}")

    print(f"{city}, {country} ({tzname}) · now {now:%a %H:%M}")
    for prayer, remind in planned:
        print(f"  {prayer:8} → {remind:%a %H:%M}")
    if not topic:
        print("\n[dry-run — set NTFY_TOPIC to actually schedule]")
        return 0
    print(f"\nScheduled {sent}/{len(planned)} on ntfy.sh/{topic}"
          + (f" ({failed} failed)" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
