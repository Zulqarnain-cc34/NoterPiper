"""Locks the reminder-timing logic (offline, no network)."""
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


def test_before_end_is_30_min_before_window_closes():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=PKT)
    rules = {"Zohar": {"before_end": 30}, "Asr": {"before_end": 30}}
    plan = dict(sp.plan_reminders(TIMINGS, now, rules))
    assert plan["Zohar"] == datetime(2026, 11, 16, 15, 0, tzinfo=PKT)   # Asr 15:30 − 30
    assert plan["Asr"] == datetime(2026, 11, 16, 17, 0, tzinfo=PKT)     # Maghrib 17:30 − 30


def test_after_start_rule():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=PKT)
    rules = {"Isha": {"after_start": 60}}
    plan = dict(sp.plan_reminders(TIMINGS, now, rules))
    assert plan["Isha"] == datetime(2026, 11, 16, 20, 0, tzinfo=PKT)    # Isha 19:00 + 60


def test_missing_rule_defaults_to_30_before_end():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=PKT)
    plan = dict(sp.plan_reminders(TIMINGS, now, {}))        # no rules → default
    assert plan["Maghrib"] == datetime(2026, 11, 16, 18, 30, tzinfo=PKT)  # Isha 19:00 − 30


def test_past_reminder_rolls_to_next_day():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=PKT)
    plan = dict(sp.plan_reminders(TIMINGS, now, {}))
    # Fajr window ended at sunrise 06:30 (past) → tomorrow 06:00
    assert plan["Fajr"] == datetime(2026, 11, 17, 6, 0, tzinfo=PKT)


def test_editable_config_loads():
    rules = sp.load_rules()  # reads the repo's reminders.json
    assert rules["Isha"] == {"after_start": 60}
