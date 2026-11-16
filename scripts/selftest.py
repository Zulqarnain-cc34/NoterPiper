#!/usr/bin/env python3
"""Live self-test — confirms the delivery path works.

1. Shows today's planned prayer-reminder times for your city.
2. Sends ONE real notification the same way reminders are sent (live), so you
   can confirm it actually reaches your phone.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import schedule_prayers as sp  # noqa: E402
from noterpiper import config, settings  # noqa: E402


def main() -> int:
    topic = config.env("NTFY_TOPIC")
    s = settings.load_settings()

    timings, tzname = sp.fetch_timings(s.city, s.country, s.method)
    now = datetime.now(ZoneInfo(tzname))
    print(f"{s.city}, {s.country} ({tzname}) — now {now:%a %H:%M}:")
    for prayer, remind in sp.plan_reminders(timings, now, s.reminders):
        print(f"  {prayer:8} → {remind:%a %H:%M}")

    if not topic:
        print("\n[no NTFY_TOPIC set — skipping the live delivery test]")
        return 0

    # Send one notification exactly the way reminders are sent (live, no schedule).
    sp.send_live(topic, "Self-test", "If this reached your phone, reminders will too.")
    print("\nSent a live test notification — watch your phone now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
