#!/usr/bin/env python3
"""Prayer-time reminders via ntfy.sh — live, serverless.

An external timer triggers this every ~2 minutes (on GitHub Actions). Each run reads config.json fresh, fetches
today's prayer times (Aladhan), and sends any reminder that is **due right now**
straight to ntfy. Because config is read live, a settings change takes effect
within a few minutes. ntfy's own message cache is the de-dup store, so a reminder
is sent once even though many runs fall inside its window.

Settings come from config.json (location + offsets); NTFY_TOPIC from env / .env.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muezzin import config, net, settings  # noqa: E402

# Aladhan timing names for when each prayer STARTS and when its window ENDS
# (a prayer's window ends when the next one starts; Isha ends at Islamic midnight).
STARTS_AT = {"Fajr": "Fajr", "Zohar": "Dhuhr", "Asr": "Asr", "Maghrib": "Maghrib", "Isha": "Isha"}
ENDS_AT = {"Fajr": "Sunrise", "Zohar": "Asr", "Asr": "Maghrib", "Maghrib": "Isha", "Isha": "Midnight"}
DEFAULT_RULE = {"before_end": 30}
WINDOW_MIN = 20  # fire if a run lands within this many minutes after the reminder time
                 # (absorbs the ~2-min trigger interval and any late run; de-dup stops repeats)


def fmt(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")  # "3:14 PM"


def message(prayer: str, end: datetime) -> tuple[str, str]:
    """Clean, professional notification: title = prayer, body = concise + end time."""
    return prayer, f"Time to pray · ends {fmt(end)}"


def fetch_timings(city: str, country: str, method: str) -> tuple[dict[str, str], str]:
    """Return (timings, IANA-timezone) for the city from Aladhan.

    Fails with a clear, actionable message if the location is wrong or the
    response is malformed — never a cryptic KeyError deep in the run.
    """
    url = "https://api.aladhan.com/v1/timingsByCity?" + urllib.parse.urlencode(
        {"city": city, "country": country, "method": method})
    try:
        payload = net.get_json(url)
    except urllib.error.HTTPError as e:
        if e.code < 500:  # 4xx = Aladhan rejected the request (usually a bad location)
            raise RuntimeError(
                f"Aladhan rejected the configured location (HTTP {e.code}). "
                f"Check your city / country / method in config.json or the PRAYER_* variables."
            ) from e
        raise
    data = payload.get("data") if isinstance(payload, dict) else None
    timings = data.get("timings") if isinstance(data, dict) else None
    tzname = (data.get("meta") or {}).get("timezone") if isinstance(data, dict) else None
    if not isinstance(timings, dict) or not tzname:
        raise RuntimeError(
            "Aladhan returned no usable prayer times for the configured location. "
            "Check the city / country in config.json are spelled correctly."
        )
    return timings, tzname


def to_dt(hhmm: str, ref: datetime) -> datetime:
    """Build ref's date at the given HH:MM in ref's timezone."""
    h, m = (int(x) for x in hhmm.split()[0].split(":")[:2])
    return ref.replace(hour=h, minute=m, second=0, microsecond=0)


def reminder_dt(prayer: str, timings: dict, ref: datetime, rules: dict) -> datetime:
    """When this prayer's reminder should fire, on ref's date:
    {"after_start": N} → N min after it begins; {"before_end": N} (default 30) →
    N min before its window ends. Pure & testable."""
    rule = rules.get(prayer, DEFAULT_RULE)
    if "after_start" in rule:
        return to_dt(timings[STARTS_AT[prayer]], ref) + timedelta(minutes=int(rule["after_start"]))
    return to_dt(timings[ENDS_AT[prayer]], ref) - timedelta(minutes=int(rule.get("before_end", 30)))


def due(remind: datetime, now: datetime, window_min: int = WINDOW_MIN) -> bool:
    """True if now is within [remind, remind+window) — due, and its window not
    yet missed (so a late/skipped cron run is still caught)."""
    delta = (now - remind).total_seconds() / 60
    return 0 <= delta < window_min


def plan_reminders(timings: dict, now: datetime, rules: dict) -> list[tuple[str, datetime]]:
    """Today's reminder time per prayer, past ones rolled to tomorrow, sorted.
    Kept for the self-test and tests; the live loop uses reminder_dt + due."""
    out = []
    for prayer in STARTS_AT:
        try:
            remind = reminder_dt(prayer, timings, now, rules)
        except (KeyError, ValueError, TypeError) as e:
            print(f"[warn] skipping {prayer}: {e}")   # bad rule / missing timing → skip just this one
            continue
        if remind <= now:
            remind += timedelta(days=1)
        out.append((prayer, remind))
    out.sort(key=lambda x: x[1])
    return out


def already_sent(topic: str, title: str, now: datetime) -> bool:
    """ntfy's cache is the de-dup store: True if a reminder with this title already
    went out today, so repeated runs inside the window don't re-send it."""
    try:
        since = int(to_dt("00:00", now).timestamp())
        raw = net.request(f"https://ntfy.sh/{topic}/json?poll=1&since={since}").decode()
        for line in raw.splitlines():
            if not line.strip():
                continue
            m = json.loads(line)
            if m.get("event") == "message" and m.get("title") == title:
                return True
    except Exception as e:
        print(f"[warn] de-dup check failed ({e}) — sending anyway")
    return False


def send_live(topic: str, title: str, body: str) -> None:
    net.request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
                headers={"Title": title, "Priority": "max", "Tags": "mosque"})  # no At → delivered now


def main() -> int:
    s = settings.load_settings()
    topic = config.env("NTFY_TOPIC")

    try:
        timings, tzname = fetch_timings(s.city, s.country, s.method)
    except Exception as e:
        # One tick failing (Aladhan/network blip) isn't worth a failure email
        # every run — skip; the next run recovers.
        print(f"[skip] couldn't fetch prayer times this run: {e}")
        return 0
    now = datetime.now(ZoneInfo(tzname))

    sent = 0
    for prayer in STARTS_AT:
        try:
            remind = reminder_dt(prayer, timings, now, s.reminders)
        except (KeyError, ValueError, TypeError) as e:
            print(f"[warn] skip {prayer}: {e}")
            continue
        if not due(remind, now):
            continue
        try:
            end = to_dt(timings[ENDS_AT[prayer]], now)
            while end < remind:                 # align the window-end to this occurrence
                end += timedelta(days=1)
            title, body = message(prayer, end)
        except (KeyError, ValueError, TypeError):
            title, body = prayer, "Time to pray"   # end time unavailable — still remind
        if not topic:
            print(f"[dry-run] {prayer} is due — would send now")
            continue
        if already_sent(topic, title, now):
            print(f"[skip] {prayer} already sent today")
            continue
        try:
            send_live(topic, title, body)
            sent += 1
            print(f"sent {prayer}")
        except Exception as e:
            print(f"[warn] {prayer} send failed: {e}")

    print(f"{sent} sent this run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
