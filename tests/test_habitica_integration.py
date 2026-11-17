"""Integration tests for Habitica plugin — verifying all phases work together.

These tests ensure phases 1–4 interact correctly, edge cases are handled,
and complex scenarios (many filters, multiple notifications, state persistence)
work as expected.
"""

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from noterpiper.plugins.habitica import MORNING_TITLE, NUDGE_TITLE, WEEKLY_TITLE, HabiticaSource

TZ = timezone(timedelta(hours=5))
AT_NUDGE = datetime(2026, 11, 16, 21, 34, tzinfo=TZ)


def _tasks(habits=(), dailys=(), todos=()):
    return {"habits": list(habits), "dailys": list(dailys), "todos": list(todos), "rewards": []}


def _ready(monkeypatch, tasks, tags=None):
    if tags is None:
        tags = {"tP": "prayer", "tQ": "quran", "tA": "Archived"}
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: True)
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tasks_by_type", lambda: tasks)
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tags", lambda: tags)


def _daily(text, streak=1, tags=(), isDue=True, completed=False, priority=1):
    return {
        "text": text,
        "isDue": isDue,
        "completed": completed,
        "streak": streak,
        "tags": list(tags),
        "priority": priority,
    }


def _habit(text, tags=(), frequency="daily", up=True, counterUp=0):
    return {
        "text": text,
        "frequency": frequency,
        "up": up,
        "counterUp": counterUp,
        "counterDown": 0,
        "tags": list(tags),
    }


def _todo(text, tags=(), completed=False, date=None, priority=1):
    return {
        "text": text,
        "completed": completed,
        "date": date,
        "tags": list(tags),
        "priority": priority,
    }


@pytest.fixture(autouse=True)
def cleanup_state():
    """Clean up state dir before and after each test."""
    state_dir = Path(".noterpiper_state")
    if state_dir.exists():
        shutil.rmtree(state_dir)
    yield
    if state_dir.exists():
        shutil.rmtree(state_dir)


# ─── Phase 1 + 2: Filtering edge cases ───


def test_phase1_phase2_all_filters_off_nothing_shown(monkeypatch):
    """With all notification types disabled, only overdue todos show."""
    _ready(
        monkeypatch,
        _tasks(
            dailys=[_daily("Daily 1")],
            habits=[_habit("Habit 1")],
            todos=[
                _todo("Overdue", date="2026-11-10"),  # overdue = urgent, always shown
                _todo("Today", date="2026-11-16"),
            ],
        ),
    )
    config = {
        "enabled": True,
        "time": "21:30",
        "notify_dailies": False,
        "notify_habits": False,
        "notify_todos": False,
    }
    notes = HabiticaSource().check(AT_NUDGE, config)
    body = notes[0].body if notes else ""
    assert "Daily 1" not in body and "Habit 1" not in body and "Today" not in body
    # Overdue still shows (always urgent)
    assert "Overdue" in body


def test_phase1_phase2_tag_whitelist_with_mixed_types(monkeypatch):
    """Tag whitelist filters all task types (dailies, habits, todos)."""
    _ready(
        monkeypatch,
        _tasks(
            dailys=[
                _daily("Prayer daily", tags=["tP"]),
                _daily("Quran daily", tags=["tQ"]),
            ],
            habits=[
                _habit("Prayer habit", tags=["tP"]),
                _habit("Quran habit", tags=["tQ"]),
            ],
            todos=[
                _todo("Prayer todo", tags=["tP"], date="2026-11-16"),
                _todo("Quran todo", tags=["tQ"], date="2026-11-16"),
            ],
        ),
    )
    config = {
        "enabled": True,
        "time": "21:30",
        "tag_whitelist": ["prayer"],
    }
    notes = HabiticaSource().check(AT_NUDGE, config)
    body = notes[0].body if notes else ""
    # Only prayer tasks show
    assert "Prayer" in body
    assert "Quran" not in body


def test_phase1_phase2_untagged_tasks_always_pass_whitelist(monkeypatch):
    """Untagged tasks pass through whitelist (they're not excluded)."""
    _ready(
        monkeypatch,
        _tasks(
            dailys=[_daily("Untagged daily", tags=[])],
            habits=[_habit("Untagged habit", tags=[])],
            todos=[_todo("Untagged todo", tags=[], date="2026-11-16")],
        ),
    )
    config = {
        "enabled": True,
        "time": "21:30",
        "tag_whitelist": ["prayer"],  # restrict to prayer only
    }
    notes = HabiticaSource().check(AT_NUDGE, config)
    body = notes[0].body if notes else ""
    # Untagged items still appear (they fall back to defaults)
    assert "Untagged" in body


# ─── Phase 3: Multiple nudges in one run ───


def test_phase3_morning_and_evening_both_fire_same_window(monkeypatch):
    """When both times fall in the same window, both notifications fire."""
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    # 6:03 AM — within window for both 6:00 AM morning and 6:00 AM evening (hypothetical)
    time = datetime(2026, 11, 16, 6, 3, tzinfo=TZ)
    config = {
        "enabled": True,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": True, "time": "06:00"},
    }
    notes = HabiticaSource().check(time, config)
    titles = [n.title for n in notes]
    assert MORNING_TITLE in titles and NUDGE_TITLE in titles


def test_phase3_morning_respects_window(monkeypatch):
    """Morning nudge respects the window config (default 5 min)."""
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    # 6:04 AM (outside default 5-min window from 6:00)
    time_outside = datetime(2026, 11, 16, 6, 4, tzinfo=TZ)
    config = {
        "enabled": True,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": False},
    }
    notes = HabiticaSource().check(time_outside, config)
    # Still within 5 min window (window is 5, so 0-4 min is ok, 6:04 is 4 min after 6:00)
    assert any(n.title == MORNING_TITLE for n in notes)
    # 6:06 AM (definitely outside)
    time_outside2 = datetime(2026, 11, 16, 6, 6, tzinfo=TZ)
    notes2 = HabiticaSource().check(time_outside2, config)
    assert not any(n.title == MORNING_TITLE for n in notes2)


# ─── Phase 4: State persistence and weekly ───


def test_phase4_weekly_accumulates_across_multiple_runs(monkeypatch):
    """Weekly state accumulates dailies over the week."""
    _ready(
        monkeypatch,
        _tasks(
            dailys=[_daily("Daily", streak=5)],
        ),
    )
    config = {
        "enabled": True,
        "time": "21:30",
        "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"},
    }
    # Monday run
    monday = datetime(2026, 11, 17, 21, 34, tzinfo=TZ)
    HabiticaSource().check(monday, config)
    # Tuesday run
    tuesday = datetime(2026, 11, 18, 21, 34, tzinfo=TZ)
    HabiticaSource().check(tuesday, config)
    # Verify 2 runs in state
    from noterpiper import state as state_module

    ws = state_module.load_weekly_state()
    assert len(ws["day_runs"]) == 2


def test_phase4_weekly_does_not_duplicate_same_day(monkeypatch):
    """Running the engine twice on same day doesn't duplicate that day."""
    _ready(monkeypatch, _tasks(dailys=[_daily("Daily")]))
    config = {
        "enabled": True,
        "time": "21:30",
        "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"},
    }
    monday = datetime(2026, 11, 17, 21, 34, tzinfo=TZ)
    # Run twice on Monday
    HabiticaSource().check(monday, config)
    HabiticaSource().check(monday, config)
    # Should have only 1 day
    from noterpiper import state as state_module

    ws = state_module.load_weekly_state()
    assert len(ws["day_runs"]) == 1


def test_phase4_weekly_respects_day_of_week(monkeypatch):
    """Weekly digest only fires on the configured day."""
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    config = {
        "enabled": True,
        "time": "21:30",
        "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"},
    }
    # Friday 7:03 PM (not Sunday)
    friday = datetime(2026, 11, 20, 19, 3, tzinfo=TZ)
    notes = HabiticaSource().check(friday, config)
    assert not any(n.title == WEEKLY_TITLE for n in notes)
    # Sunday 7:03 PM
    sunday = datetime(2026, 11, 22, 19, 3, tzinfo=TZ)
    notes = HabiticaSource().check(sunday, config)
    assert any(n.title == WEEKLY_TITLE for n in notes)


# ─── All phases together: Complex scenarios ───


def test_all_phases_complex_scenario(monkeypatch):
    """All 4 phases active: filtering + todos + multiple nudges + weekly."""
    _ready(
        monkeypatch,
        _tasks(
            dailys=[
                _daily("Prayer daily", tags=["tP"], streak=50),  # at-risk
                _daily("Quran daily", tags=["tQ"]),
            ],
            habits=[
                _habit("Prayer habit", tags=["tP"]),
                _habit("Quran habit", tags=["tQ"]),
            ],
            todos=[
                _todo("Prayer todo", tags=["tP"], date="2026-11-16"),
                _todo("Quran todo", tags=["tQ"], date="2026-11-16"),
                _todo("Overdue", date="2026-11-10"),
            ],
        ),
    )
    config = {
        "enabled": True,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": True, "time": "21:30"},
        "tag_whitelist": ["prayer"],  # only prayer tag
        "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"},
    }
    # Morning time (6:03 AM on Monday)
    monday_morning = datetime(2026, 11, 17, 6, 3, tzinfo=TZ)
    notes = HabiticaSource().check(monday_morning, config)
    # Should have morning nudge
    assert any(n.title == MORNING_TITLE for n in notes)
    # Morning shows count + at-risk flag
    morning_note = next(n for n in notes if n.title == MORNING_TITLE)
    # Should show at risk (Prayer daily has streak 50 > threshold 7)
    assert "at risk" in morning_note.body or "🔥" in morning_note.body

    # Evening time (9:34 PM on Monday)
    monday_evening = datetime(2026, 11, 17, 21, 34, tzinfo=TZ)
    notes = HabiticaSource().check(monday_evening, config)
    # Should have evening nudge
    assert any(n.title == NUDGE_TITLE for n in notes)
    # Only "Prayer" tasks
    evening_note = next(n for n in notes if n.title == NUDGE_TITLE)
    assert "Prayer" in evening_note.body

    # Sunday weekly digest (7:03 PM)
    sunday = datetime(2026, 11, 22, 19, 3, tzinfo=TZ)
    notes = HabiticaSource().check(sunday, config)
    # Should have weekly digest
    assert any(n.title == WEEKLY_TITLE for n in notes)


def test_all_phases_error_resilience(monkeypatch):
    """Phases fail gracefully when API returns bad data."""
    # Empty response
    _ready(monkeypatch, _tasks(dailys=[], habits=[], todos=[]))
    config = {
        "enabled": True,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": True, "time": "21:30"},
        "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"},
    }
    morning_time = datetime(2026, 11, 17, 6, 3, tzinfo=TZ)
    notes = HabiticaSource().check(morning_time, config)
    # Should complete without error, with "all done" messages
    assert len(notes) >= 1
    # All should say "all done" or similar
    for n in notes:
        assert "All done" in n.body or "nothing" in n.body.lower()


# ─── Dedup keys remain distinct ───


def test_dedup_keys_all_distinct(monkeypatch):
    """Each notification type has its own dedup key."""
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    config = {
        "enabled": True,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": True, "time": "06:00"},
        "weekly": {"enabled": True, "day": "Sunday", "time": "06:00"},
    }
    time = datetime(2026, 11, 22, 6, 3, tzinfo=TZ)  # Sunday 6:03 AM
    notes = HabiticaSource().check(time, config)
    dedup_keys = [n.dedup_key for n in notes]
    # All should be distinct
    assert len(set(dedup_keys)) == len(dedup_keys), f"Duplicate dedup keys: {dedup_keys}"
    # All should match their titles
    for n in notes:
        if n.title == MORNING_TITLE:
            assert n.dedup_key == MORNING_TITLE
        elif n.title == NUDGE_TITLE:
            assert n.dedup_key == NUDGE_TITLE
        elif n.title == WEEKLY_TITLE:
            assert n.dedup_key == WEEKLY_TITLE
