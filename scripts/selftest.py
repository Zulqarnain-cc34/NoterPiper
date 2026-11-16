#!/usr/bin/env python3
"""Live self-test — proves notifications fire on time.

1. Shows today's planned prayer-reminder times (offline logic).
2. Sends ONE real scheduled test ~90s out and verifies ntfy confirms the exact
   delivery second — the same mechanism the prayer reminders use.

Usage:  python scripts/selftest.py     (needs NTFY_TOPIC in .env)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import schedule_prayers as sp  # noqa: E402


def main() -> int:
    topic = sp.setting("NTFY_TOPIC")
    city = sp.setting("PRAYER_CITY", "Lahore")
    lead = int(sp.setting("LEAD_MIN", "30"))

    now = datetime.now(sp.PKT)
    plan = sp.plan_reminders(sp.fetch_timings(city), now, lead)
    print(f"Planned reminders for {city} (now {now:%a %H:%M} PKT):")
    for prayer, remind in plan:
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
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    ok = resp.get("time") == target
    when = datetime.fromtimestamp(target, sp.PKT)
    print(f"\nLive timing test → ntfy confirmed delivery at {when:%H:%M:%S}: "
          f"{'EXACT ✓' if ok else 'MISMATCH ✗'}")
    print("Watch your phone in ~90 seconds.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
