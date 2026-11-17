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
from noterpiper import (  # noqa: E402
    config,
    plugins,  # noqa: E402
    settings,
)
from noterpiper.channels import NtfyChannel, WebhookChannel  # noqa: E402
from noterpiper.engine.config import build as build_slices  # noqa: E402
from noterpiper.engine.engine import Engine  # noqa: E402
from noterpiper.engine.registry import discover_all  # noqa: E402

# Plugins auto-register — no hardcoded list. In-repo ones (under noterpiper/plugins/) plus
# any pip-installed plugin that declares a `noterpiper.plugins` entry point.
SOURCES = discover_all(plugins)


def build_config(sources, s, raw: dict, force_source: str | None = None) -> dict:
    """Assemble each plugin's config generically: the plugin's own defaults <- the shared
    location (if it wants it) <- the user's overrides in config[id]. No per-plugin wiring."""
    location = {"city": s.city, "country": s.country, "method": s.method, "timezone": s.timezone}
    return build_slices(sources, raw, location, force_source)


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
    channels = [NtfyChannel(topic)]  # the enabled delivery channels
    webhook_url = config.env("WEBHOOK_URL")
    if webhook_url:
        channels.append(WebhookChannel(webhook_url))
    cfg = build_config(SOURCES, s, settings.keyed_config(), force)
    sent = Engine(channels, select_sources(force)).run(now, cfg)
    print(f"{sent} sent this run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
