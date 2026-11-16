#!/usr/bin/env python3
"""Nightly Habitica nudge via ntfy.sh — a single end-of-day check.

OPTIONAL: if Habitica credentials aren't set, this does nothing (prayer reminders
work without Habitica). One clean, grouped message — prayers and dailies, each
item listed once, streaks at risk flagged.

Settings (env / .env):  NTFY_TOPIC, HABITICA_API_TOKEN, HABITICA_USER_ID.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muezzin import api, config, net, settings  # noqa: E402

PRAYERS = ("Fajr", "Zohar", "Asr", "Maghrib", "Isha")  # standard prayer names
STREAK_RISK = 7  # warn when a streak this long is unticked


def due_now(now_local: datetime, target_hhmm: str, window_min: int = 30) -> bool:
    """True if now is within [target, target+window) the same day — so exactly
    one evening run fires the nudge at the configured local time."""
    th, tm = (int(x) for x in target_hhmm.split(":")[:2])
    delta = (now_local.hour * 60 + now_local.minute) - (th * 60 + tm)
    return 0 <= delta < window_min


def collect(tasks: dict) -> tuple[list[str], list[tuple[str, int]]]:
    """Gather what's still outstanding: unlogged prayer habits, and due-but-not-done
    dailies with their streak. Each item appears once (no 'not done' vs 'at risk'
    double-listing)."""
    prayers = [h["text"].strip() for h in tasks.get("habits", [])
               if any(p in h.get("text", "") for p in PRAYERS)
               and (h.get("counterUp", 0) + h.get("counterDown", 0)) == 0]
    dailies = [(d["text"].strip(), int(d.get("streak", 0))) for d in tasks.get("dailys", [])
               if d.get("isDue") and not d.get("completed")]
    return prayers, dailies


def build_message(prayers: list[str], dailies: list[tuple[str, int]]) -> tuple[str, str, str, str]:
    """A clean, grouped, de-duplicated nudge: counts per group, one daily per line,
    a flame on streaks at risk. Returns (title, body, priority, tags)."""
    total = len(prayers) + len(dailies)
    if total == 0:
        return "All done today", "Everything is logged. 🌙", "low", "white_check_mark"

    blocks = []
    if prayers:
        blocks.append(f"Prayers · {len(prayers)}\n" + ", ".join(prayers))
    if dailies:
        ordered = sorted(dailies, key=lambda d: (d[1] >= STREAK_RISK, d[1]), reverse=True)  # at-risk first, longest streak first
        rows = [f"{name} · {streak} 🔥" if streak >= STREAK_RISK else name
                for name, streak in ordered]
        blocks.append(f"Dailies · {len(dailies)}\n" + "\n".join(rows))

    urgent = any(streak >= STREAK_RISK for _, streak in dailies)
    title = f"{total} left before midnight"
    priority, tags = ("high", "warning") if urgent else ("default", "bell")
    return title, "\n\n".join(blocks), priority, tags


def send(topic: str, title: str, body: str, priority: str, tags: str) -> None:
    net.request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
                headers={"Title": title, "Priority": priority, "Tags": tags})


def main() -> int:
    if not api.configured():
        print("[skip] Habitica not configured — nightly nudge is optional.")
        return 0

    s = settings.load_settings()

    # The on-demand "send now" button (workflow_dispatch) always sends — it's the
    # alive-test, so it ignores the on/off flag and the time gate. Scheduled runs
    # respect both: only when enabled, and only at the configured local time.
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        if not s.nudge_enabled:
            print("[skip] nightly nudge is turned off in config.json.")
            return 0
        try:
            now_local = datetime.now(ZoneInfo(s.timezone))
        except Exception as e:
            print("[skip] configured timezone is invalid; skipping tonight's nudge.")
            return 0
        if not due_now(now_local, s.nudge_time):
            print(f"[skip] not nudge time yet (set to {s.nudge_time}).")
            return 0

    try:
        tasks = api.fetch_tasks_by_type()
    except Exception as e:                      # Habitica down / token issue — skip, don't fail the job
        print(f"[skip] couldn't reach Habitica, skipping tonight's nudge: {e}")
        return 0

    prayers, dailies = collect(tasks)
    title, body, priority, tags = build_message(prayers, dailies)

    topic = config.env("NTFY_TOPIC")
    if not topic:
        print(f"[dry-run — set NTFY_TOPIC to push]\n\n{title}\n{body}")
        return 0
    send(topic, title, body, priority, tags)
    print(f"pushed to ntfy.sh/{topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
