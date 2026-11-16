#!/usr/bin/env python3
"""Nudges via ntfy.sh — a daily check-in pushed to your phone.

This is a pluggable "nudge" runner. Each nudge is a small function that looks at
your Habitica tasks and returns zero or more lines. To add a new nudge (e.g. for
to-dos or a specific daily), write a function and add it to NUDGES — nothing else
changes. One nudge failing never stops the others.

Usage:  python scripts/notify.py   (needs NTFY_TOPIC in .env to actually push)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from habitica_etl import api, config, net  # noqa: E402


def ntfy_topic() -> str | None:
    env = api._load_env(config.PROJECT_ROOT / ".env")
    return env.get("NTFY_TOPIC") or os.environ.get("NTFY_TOPIC")

PRAYERS = ["Fajr", "Zohar", "Asr", "Maghrib", "Isha"]
STREAK_RISK = 7

_LABELS = {
    "Surah Mulk": "Surah Mulk", "500 ": "500 Lā ḥawla", "tasbeeh fatima": "Tasbeeh Fatima",
    "11 Times Muhammad": "11× Muhammad", "Quran Hakeem": "Quran Hakeem",
    "313 darood": "313 Darood", "Quran Every Jummah": "Quran (Jummah)",
}


def label(text: str) -> str:
    for k, v in _LABELS.items():
        if k in text:
            return v
    return text.strip()[:18]


# ─── nudges ───  each takes the tasks dict and returns display lines.
def nudge_prayers_not_logged(tasks: dict) -> list[str]:
    missing = [h["text"].strip() for h in tasks.get("habits", [])
               if any(p in h.get("text", "") for p in PRAYERS)
               and (h.get("counterUp", 0) + h.get("counterDown", 0)) == 0]
    return ["🕌 Prayers not logged: " + ", ".join(missing)] if missing else []


def nudge_recitations_not_done(tasks: dict) -> list[str]:
    missing = [label(d["text"]) for d in tasks.get("dailys", [])
               if config.classify_section(d.get("text", "")) and d.get("isDue") and not d.get("completed")]
    return ["📿 Not done: " + ", ".join(missing)] if missing else []


def nudge_streak_at_risk(tasks: dict) -> list[str]:
    risk = [f"{label(d['text'])} ({d['streak']})" for d in tasks.get("dailys", [])
            if config.classify_section(d.get("text", "")) and d.get("isDue")
            and not d.get("completed") and d.get("streak", 0) >= STREAK_RISK]
    return ["🔥 Streak at risk: " + ", ".join(risk)] if risk else []  # 🔥 = urgent


# Add new nudges here — e.g. a to-do nudge — and they just work.
NUDGES = [nudge_prayers_not_logged, nudge_recitations_not_done, nudge_streak_at_risk]


def send(topic: str, title: str, body: str, priority: str, tags: str) -> None:
    net.request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
                headers={"Title": title, "Priority": priority, "Tags": tags})


def main() -> int:
    tasks = api.fetch_export_like()["tasks"]

    lines: list[str] = []
    for nudge in NUDGES:
        try:
            lines += nudge(tasks)
        except Exception as e:                      # one bad nudge never breaks the run
            print(f"[warn] {nudge.__name__} failed: {e}")

    urgent = any(line.startswith("🔥") for line in lines)
    if not lines:
        title, body, priority, tags = "Habitica - all logged", "Everything's done for today. Nice work!", "default", "white_check_mark"
    else:
        title, body = "Habitica - before midnight", "\n".join(lines)
        priority, tags = ("high", "warning") if urgent else ("default", "bell")

    topic = ntfy_topic()
    if not topic:
        print(f"[dry-run — set NTFY_TOPIC to push]\n\n{title}\n{body}")
        return 0
    send(topic, title, body, priority, tags)
    print(f"pushed to ntfy.sh/{topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
