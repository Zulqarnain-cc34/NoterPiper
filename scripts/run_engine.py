#!/usr/bin/env python3
"""NoterPiper entry point — runs the engine once.

An external timer dispatches this every ~2 minutes. It maps the (flat) settings into
each plugin's config slice — config.json stays flat, so the phone page is unaffected —
then runs the engine: every source is asked what's due, and due notifications are
delivered exactly once via ntfy.

  NTFY_TOPIC      your ntfy topic (required to deliver)
  FORCE_SOURCE    set to a source id (e.g. "habitica") to force it now — this is how
                  the on-demand "send now" button works (workflow_dispatch).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noterpiper import config, settings  # noqa: E402
from noterpiper.channels import NtfyChannel  # noqa: E402
from noterpiper.engine.engine import Engine  # noqa: E402
from noterpiper.plugins.habitica import HabiticaSource  # noqa: E402
from noterpiper.plugins.prayer import PrayerSource  # noqa: E402

SOURCES = [PrayerSource(), HabiticaSource()]


def build_config(s, force_source: str | None = None) -> dict:
    """Map flat settings into per-plugin config slices (keyed by each source's id)."""
    return {
        "prayer": {
            "city": s.city, "country": s.country, "method": s.method,
            "reminders": s.reminders, "window": s.prayer_window,
        },
        "habitica": {
            "time": s.nudge_time, "enabled": s.nudge_enabled,
            "window": s.nudge_window, "force": force_source == "habitica",
        },
    }


def select_sources(force_source: str | None = None) -> list:
    """Normally every source runs. When a source is forced (the on-demand 'send now'
    button), run only that one — so pressing it can't also fire an unrelated reminder."""
    if force_source:
        return [src for src in SOURCES if src.id == force_source]
    return SOURCES


def main() -> int:
    s = settings.load_settings()
    topic = config.env("NTFY_TOPIC")
    if not topic:
        print("[dry-run] NTFY_TOPIC not set — nothing delivered")
        return 0
    force = os.environ.get("FORCE_SOURCE")
    now = datetime.now(ZoneInfo(s.timezone))
    channels = [NtfyChannel(topic)]      # the enabled delivery channels (more to come)
    sent = Engine(channels, select_sources(force)).run(now, build_config(s, force))
    print(f"{sent} sent this run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
