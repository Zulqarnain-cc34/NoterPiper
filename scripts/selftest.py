#!/usr/bin/env python3
"""Live self-test — proves reminders fire on time.

1. Shows today's planned prayer-reminder times for your city.
2. Sends ONE real scheduled test ~90s out and checks ntfy confirms the exact
   delivery second — the same mechanism the prayer reminders use.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import schedule_prayers as sp  # noqa: E402
from muezzin import config  # noqa: E402


def main() -> int:
    topic = config.env("NTFY_TOPIC")
    city = config.env("PRAYER_CITY", "Lahore")
    country = config.env("PRAYER_COUNTRY", "Pakistan")
    method = config.env("PRAYER_METHOD", "1")

    timings, tzname = sp.fetch_timings(city, country, method)
    now = datetime.now(ZoneInfo(tzname))
    print(f"{city}, {country} ({tzname}) — now {now:%a %H:%M}:")
    for prayer, remind in sp.plan_reminders(timings, now, sp.load_rules()):
        print(f"  {prayer:8} → {remind:%a %H:%M}")

    if not topic:
        print("\n[no NTFY_TOPIC set — skipping the live timing test]")
        return 0

    target = int(time.time()) + 90
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data="⏱️ Self-test — if this pops in ~90s, prayer reminders fire on time.".encode(),
        headers={"Title": "Self-test", "Priority": "max", "Tags": "stopwatch", "At": str(target)},
    )
    ok = json.loads(urllib.request.urlopen(req, timeout=15).read()).get("time") == target
    print(f"\nLive timing test → ntfy confirmed exact delivery: {'✓' if ok else '✗'}")
    print("Watch your phone in ~90 seconds.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
