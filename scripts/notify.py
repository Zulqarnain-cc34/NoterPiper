#!/usr/bin/env python3
"""Nightly Habitica nudge via ntfy.sh — a single end-of-day check.

OPTIONAL: if Habitica credentials aren't set, this does nothing (prayer reminders
work without Habitica). Nudges are a plug-in list — each is a small function over
the task groups returning lines; one failing never stops the others.

Settings (env / .env):  NTFY_TOPIC, HABITICA_API_TOKEN, HABITICA_USER_ID.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muezzin import api, config, net  # noqa: E402

PRAYERS = ("Fajr", "Zohar", "Asr", "Maghrib", "Isha")  # standard prayer names
STREAK_RISK = 7  # warn when a streak this long is unticked


# ─── nudges ───  each takes grouped tasks and returns display lines.
def nudge_prayers_not_logged(t: dict) -> list[str]:
    missing = [h["text"].strip() for h in t.get("habits", [])
               if any(p in h.get("text", "") for p in PRAYERS)
               and (h.get("counterUp", 0) + h.get("counterDown", 0)) == 0]
    return ["🕌 Prayers not logged: " + ", ".join(missing)] if missing else []


def nudge_dailies_not_done(t: dict) -> list[str]:
    due = [d["text"].strip() for d in t.get("dailys", [])
           if d.get("isDue") and not d.get("completed")]
    return ["📋 Not done today: " + ", ".join(due)] if due else []


def nudge_streaks_at_risk(t: dict) -> list[str]:
    risk = [f"{d['text'].strip()} ({d['streak']})" for d in t.get("dailys", [])
            if d.get("isDue") and not d.get("completed") and d.get("streak", 0) >= STREAK_RISK]
    return ["🔥 Streak at risk: " + ", ".join(risk)] if risk else []  # 🔥 = urgent


NUDGES = [nudge_prayers_not_logged, nudge_dailies_not_done, nudge_streaks_at_risk]


def send(topic: str, title: str, body: str, priority: str, tags: str) -> None:
    net.request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
                headers={"Title": title, "Priority": priority, "Tags": tags})


def main() -> int:
    if not api.configured():
        print("[skip] Habitica not configured — nightly nudge is optional.")
        return 0

    tasks = api.fetch_tasks_by_type()
    lines: list[str] = []
    for nudge in NUDGES:
        try:
            lines += nudge(tasks)
        except Exception as e:                 # one bad nudge never breaks the run
            print(f"[warn] {nudge.__name__} failed: {e}")

    urgent = any(line.startswith("🔥") for line in lines)
    if not lines:
        title, body, priority, tags = "Habitica - all logged", "Everything's done for today. Nice work!", "default", "white_check_mark"
    else:
        title, body = "Habitica - before midnight", "\n".join(lines)
        priority, tags = ("high", "warning") if urgent else ("default", "bell")

    topic = config.env("NTFY_TOPIC")
    if not topic:
        print(f"[dry-run — set NTFY_TOPIC to push]\n\n{title}\n{body}")
        return 0
    send(topic, title, body, priority, tags)
    print(f"pushed to ntfy.sh/{topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
