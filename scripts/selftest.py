#!/usr/bin/env python3
"""Live self-test — confirms the delivery path and shows today's prayer times.

1. Shows today's prayer start-times for your city (via the prayer plugin).
2. Sends ONE real notification the same way reminders are sent, so you can confirm
   it actually reaches your phone.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noterpiper import config, settings  # noqa: E402
from noterpiper.channels import NtfyChannel  # noqa: E402
from noterpiper.engine import Notification  # noqa: E402
from noterpiper.plugins.prayer import STARTS_AT, fetch_timings  # noqa: E402


def main() -> int:
    s = settings.load_settings()
    topic = config.env("NTFY_TOPIC")

    try:
        timings = fetch_timings(s.city, s.country, s.method)
        now = datetime.now(ZoneInfo(s.timezone))
        print(f"{s.city} — {now:%a %H:%M}:")
        for prayer, start_key in STARTS_AT.items():
            print(f"  {prayer:8} starts {timings.get(start_key, '?')}")
    except Exception as e:
        print(f"[warn] couldn't fetch prayer times: {e}")

    if not topic:
        print("\n[no NTFY_TOPIC set — skipping the live delivery test]")
        return 0

    NtfyChannel(topic).send(
        Notification("Self-test", "If this reached your phone, reminders will too."))
    print("\nSent a live test notification — watch your phone now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
