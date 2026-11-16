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
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from habitica_etl import api, config, net  # noqa: E402  (reuse _load_env + PROJECT_ROOT)

PKT = timezone(timedelta(hours=5))

# Aladhan timing names for when each prayer STARTS and when its window ENDS
# (a prayer's window ends when the next one starts; Isha ends at Islamic midnight).
STARTS_AT = {"Fajr": "Fajr", "Zohar": "Dhuhr", "Asr": "Asr", "Maghrib": "Maghrib", "Isha": "Isha"}
ENDS_AT = {"Fajr": "Sunrise", "Zohar": "Asr", "Asr": "Maghrib", "Maghrib": "Isha", "Isha": "Midnight"}

DEFAULT_RULE = {"before_end": 30}


def load_rules() -> dict:
    """Read the owner-editable reminders.json; fall back to 30-min-before-end."""
    try:
        data = json.loads((config.PROJECT_ROOT / "reminders.json").read_text())
        return {k: v for k, v in data.items() if not k.startswith("__")}
    except Exception:
        return {}
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
    return net.get_json(url)["data"]["timings"]


def to_dt(hhmm: str, day: datetime) -> datetime:
    h, m = (int(x) for x in hhmm.split()[0].split(":")[:2])
    return datetime(day.year, day.month, day.day, h, m, tzinfo=PKT)


def plan_reminders(timings: dict, now: datetime, rules: dict) -> list[tuple[str, datetime]]:
    """Pure, testable. For each prayer, compute its reminder time from rules:
    {"before_end": N} → N min before the window ends; {"after_start": N} →
    N min after the prayer begins. Past reminders roll to the next day."""
    out = []
    for prayer in STARTS_AT:
        rule = rules.get(prayer, DEFAULT_RULE)
        if "after_start" in rule:
            base = to_dt(timings[STARTS_AT[prayer]], now)
            remind = base + timedelta(minutes=int(rule["after_start"]))
        else:
            base = to_dt(timings[ENDS_AT[prayer]], now)
            remind = base - timedelta(minutes=int(rule.get("before_end", 30)))
        if remind <= now:                   # already passed today → tomorrow
            remind += timedelta(days=1)
        out.append((prayer, remind))
    out.sort(key=lambda x: x[1])
    return out


def schedule(topic: str, when: datetime, title: str, body: str) -> None:
    net.request(
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


def main() -> int:
    city = setting("PRAYER_CITY", "Lahore")
    topic = setting("NTFY_TOPIC")
    rules = load_rules()

    timings = fetch_timings(city)
    now = datetime.now(PKT)
    planned = plan_reminders(timings, now, rules)

    sent = failed = 0
    for prayer, remind in planned:
        if topic:
            try:
                # Title must be ASCII (HTTP header); the mosque emoji comes from Tags.
                schedule(topic, remind, f"{prayer} - time to pray", MESSAGES[prayer])
                sent += 1
            except Exception as e:          # one failed send never aborts the rest
                failed += 1
                print(f"[warn] {prayer} reminder failed: {e}")

    print(f"City: {city} · now: {now:%a %H:%M} PKT")
    for prayer, remind in planned:
        rule = rules.get(prayer, DEFAULT_RULE)
        how = (f"{rule['after_start']}m after start" if "after_start" in rule
               else f"{rule.get('before_end', 30)}m before end")
        print(f"  {prayer:8} → {remind:%a %H:%M}  ({how})")
    if not topic:
        print("\n[dry-run — set NTFY_TOPIC in .env to actually schedule on your phone]")
        return 0
    print(f"\nScheduled {sent}/{len(planned)} reminders on ntfy.sh/{topic}"
          + (f" ({failed} failed)" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
