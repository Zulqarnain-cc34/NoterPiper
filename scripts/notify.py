#!/usr/bin/env python3
"""Notifications via ntfy.sh — no server, free, phone push.

Pulls live Habitica data (read-only), checks what's not logged yet today and
which streaks are at risk, and pushes a single notification to your ntfy topic.

Usage:  python scripts/notify.py
Set the topic in .env:  NTFY_TOPIC=your-secret-topic   (else it prints a dry-run)
Subscribe to that topic in the free ntfy app to receive the push.
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from habitica_etl import api, config  # noqa: E402

PRAYERS = ["Fajr", "Zohar", "Asr", "Maghrib", "Isha"]
STREAK_RISK = 7  # warn when a streak this long is unticked

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


def ntfy_topic() -> str | None:
    env = api._load_env(config.PROJECT_ROOT / ".env")
    return env.get("NTFY_TOPIC") or os.environ.get("NTFY_TOPIC")


def send(topic: str, title: str, body: str, priority: str, tags: str) -> None:
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={"Title": title, "Priority": priority, "Tags": tags},
    )
    urllib.request.urlopen(req, timeout=15)


def main() -> int:
    tasks = api.fetch_export_like()["tasks"]

    prayers_missing = [
        h["text"].strip() for h in tasks.get("habits", [])
        if any(p in h.get("text", "") for p in PRAYERS)
        and (h.get("counterUp", 0) + h.get("counterDown", 0)) == 0
    ]

    recit_missing, streak_risk = [], []
    for d in tasks.get("dailys", []):
        if not config.classify_section(d.get("text", "")):
            continue
        if d.get("isDue") and not d.get("completed"):
            recit_missing.append(label(d["text"]))
            if d.get("streak", 0) >= STREAK_RISK:
                streak_risk.append(f"{label(d['text'])} ({d['streak']})")

    lines = []
    if prayers_missing:
        lines.append("🕌 Prayers not logged: " + ", ".join(prayers_missing))
    if recit_missing:
        lines.append("📿 Not done: " + ", ".join(recit_missing))
    if streak_risk:
        lines.append("🔥 Streak at risk: " + ", ".join(streak_risk))

    # Title must be ASCII (HTTP header); emoji come from the Tags header + body.
    if not lines:
        title, body = "Habitica - all logged", "Everything's done for today. Nice work!"
        priority, tags = "default", "white_check_mark"
    else:
        title = "Habitica - before midnight"
        body = "\n".join(lines)
        priority = "high" if streak_risk else "default"
        tags = "warning" if streak_risk else "bell"

    topic = ntfy_topic()
    if not topic:
        print(f"[dry-run — set NTFY_TOPIC in .env to actually push]\n\n{title}\n{body}")
        return 0
    send(topic, title, body, priority, tags)
    print(f"pushed to ntfy.sh/{topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
