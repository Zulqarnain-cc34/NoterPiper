"""Example NoterPiper plugin — the smallest real Source.

Copy this folder to start your own plugin:
  • into this repo at `src/noterpiper/plugins/<name>/`  → ships with NoterPiper, and the
    engine auto-discovers it (see `engine/registry.py`); OR
  • into your own repo/package that depends on `noterpiper` → your plugin, your release.

Then rename the class and implement `check()`. You never edit the engine.
Full walkthrough: ../../PLUGIN-AUTHORING.md
"""

from __future__ import annotations

from datetime import datetime

from noterpiper.engine import Notification


def _due_now(now: datetime, hhmm: str, window: int = 5) -> bool:
    """True within `window` minutes after HH:MM (the engine runs every few minutes)."""
    th, tm = (int(x) for x in hhmm.split(":")[:2])
    delta = (now.hour * 60 + now.minute) - (th * 60 + tm)
    return 0 <= delta < window


class ExampleSource:
    """`id` + `check()` is the whole contract (`noterpiper.engine.Source`)."""

    id = "example"  # short, stable — also the key for this plugin's config slice

    def check(self, now: datetime, config: dict) -> list[Notification]:
        if not config.get("enabled", False):  # opt-in; off by default
            return []
        if not _due_now(now, str(config.get("time", "09:00"))):
            return []  # only fire when it's due
        message = str(config.get("message") or "👋 Hello from your NoterPiper plugin")
        # Keep the TITLE ASCII (ntfy puts it in an HTTP header); emoji belong in the body/tags.
        return [
            Notification(
                "Example", message, priority="default", tags=("wave",), dedup_key="example"
            )
        ]
