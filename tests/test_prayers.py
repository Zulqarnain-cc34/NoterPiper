"""Locks the "remind 30 min before each prayer ends" logic (offline, no network)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import schedule_prayers as sp  # noqa: E402

PKT = timezone(timedelta(hours=5))
TIMINGS = {  # sample prayer times (HH:MM, local)
    "Fajr": "05:00", "Sunrise": "06:30", "Dhuhr": "12:00", "Asr": "15:30",
    "Maghrib": "17:30", "Isha": "19:00", "Midnight": "00:00",
}


def test_remind_is_30_min_before_window_ends():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=PKT)  # 10:00
    plan = dict(sp.plan_reminders(TIMINGS, now, 30))
    assert plan["Zohar"] == datetime(2026, 11, 16, 15, 0, tzinfo=PKT)   # Asr 15:30 − 30
    assert plan["Asr"] == datetime(2026, 11, 16, 17, 0, tzinfo=PKT)     # Maghrib 17:30 − 30
    assert plan["Maghrib"] == datetime(2026, 11, 16, 18, 30, tzinfo=PKT)  # Isha 19:00 − 30


def test_past_prayer_rolls_to_next_day():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=PKT)
    plan = dict(sp.plan_reminders(TIMINGS, now, 30))
    # Fajr ended at sunrise 06:30 (past) → tomorrow 06:00
    assert plan["Fajr"] == datetime(2026, 11, 17, 6, 0, tzinfo=PKT)


def test_isha_uses_midnight_end():
    now = datetime(2026, 11, 16, 20, 0, tzinfo=PKT)  # after Isha starts
    plan = dict(sp.plan_reminders(TIMINGS, now, 30))
    # Isha ends at Islamic midnight 00:00 (tomorrow) → remind 23:30 today
    assert plan["Isha"] == datetime(2026, 11, 16, 23, 30, tzinfo=PKT)


def test_lead_time_is_configurable():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=PKT)
    plan = dict(sp.plan_reminders(TIMINGS, now, 15))
    assert plan["Zohar"] == datetime(2026, 11, 16, 15, 15, tzinfo=PKT)  # 15 before 15:30
