"""HabiticaSource — the tag-driven nightly nudge.

Same gating as before (configured + enabled + at the set time), but categorisation is
now by the user's tags, reading only Habitica's structured fields — never a title's
wording. Habitica (tasks + tags) is mocked; `now` is engine-supplied."""

import shutil
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from noterpiper.engine import Source
from noterpiper.plugins.habitica import AUTH_FAIL_TITLE, NUDGE_TITLE, WEEKLY_TITLE, HabiticaSource

TZ = timezone(timedelta(hours=5))
AT_NUDGE = datetime(2026, 11, 16, 21, 34, tzinfo=TZ)  # within the default window of 21:30
BEFORE = datetime(2026, 11, 16, 20, 0, tzinfo=TZ)
TODAY_ISO = "2026-11-16T00:00:00.000Z"  # a to-do due today (== AT_NUDGE's date)
CONFIG = {"time": "21:30", "enabled": True}
TAGS = {"tP": "prayer", "tQ": "quran", "tA": "Archived"}  # tag-id → name


def _tasks(habits=(), dailys=(), todos=()):
    return {"habits": list(habits), "dailys": list(dailys), "todos": list(todos), "rewards": []}


def _ready(monkeypatch, tasks, tags=TAGS):
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


# ─── gating (unchanged behaviour) ───


def test_satisfies_the_Source_contract():
    assert isinstance(HabiticaSource(), Source)
    assert HabiticaSource().id == "habitica"


def test_no_nudge_when_habitica_is_not_configured(monkeypatch):
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: False)
    assert HabiticaSource().check(AT_NUDGE, CONFIG) == []


def test_no_nudge_when_disabled(monkeypatch):
    _ready(monkeypatch, _tasks())
    assert HabiticaSource().check(AT_NUDGE, {"time": "21:30", "enabled": False}) == []


def test_no_nudge_before_the_set_time(monkeypatch):
    _ready(monkeypatch, _tasks())
    assert HabiticaSource().check(BEFORE, CONFIG) == []


def test_window_from_config_is_honored(monkeypatch):
    _ready(monkeypatch, _tasks())
    now = datetime(2026, 11, 16, 21, 45, tzinfo=TZ)
    assert HabiticaSource().check(now, {"time": "21:30", "enabled": True, "window": 30}) != []
    assert HabiticaSource().check(now, {"time": "21:30", "enabled": True, "window": 10}) == []


def test_force_sends_even_when_off_and_out_of_time(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("X")]))
    notes = HabiticaSource().check(BEFORE, {"time": "21:30", "enabled": False, "force": True})
    assert len(notes) == 1 and notes[0].dedup_key is None


def test_fetch_failure_sends_nothing(monkeypatch):
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: True)
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tags", dict)

    def boom():
        raise RuntimeError("habitica down")

    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tasks_by_type", boom)
    assert HabiticaSource().check(AT_NUDGE, CONFIG) == []


def test_stable_dedup_title(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("X")]))
    n = HabiticaSource().check(AT_NUDGE, CONFIG)[0]
    assert n.dedup_key == n.title == NUDGE_TITLE


# ─── auth failure is surfaced, not swallowed (B3) ───


def _auth_fails(monkeypatch, code):
    """Habitica configured + due, but the API rejects the credentials with `code`."""
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: True)
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tags", dict)

    def boom():
        raise urllib.error.HTTPError("https://habitica.com", code, "err", None, None)

    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tasks_by_type", boom)


def test_bad_credentials_send_a_deduped_warning(monkeypatch):
    _auth_fails(monkeypatch, 401)
    notes = HabiticaSource().check(AT_NUDGE, CONFIG)
    assert len(notes) == 1
    n = notes[0]
    assert n.title == AUTH_FAIL_TITLE
    assert n.dedup_key == n.title  # once/day dedup matches on the title
    assert n.priority == "high"


def test_403_is_also_an_auth_failure(monkeypatch):
    _auth_fails(monkeypatch, 403)
    assert HabiticaSource().check(AT_NUDGE, CONFIG)[0].title == AUTH_FAIL_TITLE


def test_other_http_errors_still_send_nothing(monkeypatch):
    _auth_fails(monkeypatch, 500)  # server blip, not a credential problem
    assert HabiticaSource().check(AT_NUDGE, CONFIG) == []


def test_forced_auth_failure_always_delivers(monkeypatch):
    _auth_fails(monkeypatch, 401)
    n = HabiticaSource().check(BEFORE, {"time": "21:30", "enabled": False, "force": True})[0]
    assert n.title == AUTH_FAIL_TITLE and n.dedup_key is None


# ─── handles any setup: no convention required (A1 habits, A2 dividers) ───


def test_untagged_habit_shows_under_a_Habits_fallback(monkeypatch):
    # habits must behave like dailies/to-dos: untagged ones fall back, never vanish silently.
    _ready(monkeypatch, _tasks(habits=[_habit("Pushups")]))  # untagged, daily, up, untapped
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Habits" in body and "Pushups" in body


def test_tagged_habit_still_uses_its_tag_section(monkeypatch):
    _ready(monkeypatch, _tasks(habits=[_habit("Surah", tags=["tQ"])]))  # tQ → "quran"
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Quran" in body and "Surah" in body


def test_markdown_header_tasks_are_skipped_as_dividers(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("#### Morning"), _daily("Real one")]))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Morning" not in body and "Real one" in body


def test_separator_rule_tasks_are_skipped_as_dividers(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("--------"), _todo("Buy milk", date=TODAY_ISO)]))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Buy milk" in body and "--------" not in body


def test_a_hash_without_a_space_is_a_real_task(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("#1 goal")]))  # not a markdown header
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "#1 goal" in body


def test_all_logged_is_a_calm_all_done(monkeypatch):
    _ready(monkeypatch, _tasks())
    assert "All done" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


# ─── tag-driven categorisation ───


def test_dailies_group_under_their_tag(monkeypatch):
    _ready(
        monkeypatch, _tasks(dailys=[_daily("Surah Mulk", tags=["tQ"]), _daily("Fajr", tags=["tP"])])
    )
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Quran · 1" in body and "Surah Mulk" in body
    assert "Prayer · 1" in body and "Fajr" in body


def test_untagged_daily_falls_back_to_type(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Random daily")]))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Dailies · 1" in body and "Random daily" in body


def test_due_today_todo_falls_back_to_type(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("Buy milk", date=TODAY_ISO)]))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "To-dos · 1" in body and "Buy milk" in body


def test_habits_group_by_tag_and_untagged_fall_back(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            habits=[
                _habit("Quran Fajr", tags=["tQ"]),  # → Quran section
                _habit("Drink water"),  # untagged → Habits section (no longer dropped)
            ]
        ),
    )
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Quran" in body and "Quran Fajr" in body
    assert "Habits" in body and "Drink water" in body


def test_non_daily_habit_is_ignored(monkeypatch):
    _ready(monkeypatch, _tasks(habits=[_habit("Weekly thing", tags=["tQ"], frequency="weekly")]))
    assert "All done" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


def test_tapped_habit_is_not_shown(monkeypatch):
    _ready(monkeypatch, _tasks(habits=[_habit("Quran Fajr", tags=["tQ"], counterUp=1)]))
    assert "All done" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


def test_archived_tasks_are_skipped(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("#### Divider", tags=["tA"])]))
    assert "All done" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


def test_completed_daily_is_not_shown(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Done one", tags=["tQ"], completed=True)]))
    assert "All done" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


# ─── urgency, overdue, scaling ───


def test_at_risk_streak_is_cross_cut_and_first(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(dailys=[_daily("Surah Mulk", streak=52, tags=["tQ"]), _daily("Walk", streak=2)]),
    )
    n = HabiticaSource().check(AT_NUDGE, CONFIG)[0]
    assert "at risk 🔥" in n.body.splitlines()[0]
    assert "At risk · 1" in n.body and "Surah Mulk · 52" in n.body
    assert "Quran" not in n.body  # pulled out of its section into At risk
    assert n.priority == "high"
    assert n.body.index("Surah Mulk") < n.body.index("Walk")


def test_streak_risk_threshold_is_configurable(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Walk", streak=5)]))
    assert "At risk" not in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "At risk" in HabiticaSource().check(AT_NUDGE, {**CONFIG, "streak_risk": 3})[0].body


def test_overdue_todo_gets_its_own_urgent_block(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("Report", date="2026-11-14T00:00:00.000Z")]))
    n = HabiticaSource().check(AT_NUDGE, CONFIG)[0]
    assert "Overdue · 1" in n.body and "Report" in n.body and n.priority == "high"


def test_future_and_undated_todos_collapse_to_a_backlog_count(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(todos=[_todo("Future", date="2026-11-20T00:00:00.000Z"), _todo("Someday")]),
    )
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "2 open to-do" in body  # neither is owed tonight → one honest count line
    assert "Future" not in body and "Someday" not in body
    assert "overdue" not in body.lower()


def test_backlog_is_excluded_from_the_headline_count(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(dailys=[_daily("Pray")], todos=[_todo("Someday A"), _todo("Someday B")]),
    )
    n = HabiticaSource().check(AT_NUDGE, CONFIG)[0]
    assert n.body.splitlines()[0].startswith("1 to do before midnight")  # counts only time-bound
    assert "2 open to-do" in n.body and "Someday A" not in n.body


def test_all_done_still_mentions_the_backlog(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("Someday")]))  # nothing owed tonight, 1 in backlog
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "All done" in body and "1 open to-do" in body


def test_hard_tasks_lead_within_a_section(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(dailys=[_daily("Trivial thing", priority=0.1), _daily("Hard thing", priority=2)]),
    )
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert body.index("Hard thing") < body.index("Trivial thing")


def test_long_lists_are_capped_but_count_stays_true(monkeypatch):
    many = [_daily(f"D{i}") for i in range(9)]
    _ready(monkeypatch, _tasks(dailys=many))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Dailies · 9" in body and "+4 more" in body


def test_titles_are_header_safe(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("X")]))
    HabiticaSource().check(AT_NUDGE, CONFIG)[0].title.encode("latin-1")  # must not raise


# ─── recurrence / frequency: every case (dailies via isDue, habits daily-only) ───


def test_a_daily_not_due_today_is_skipped(monkeypatch):
    # a weekly/monthly/yearly daily on an off day → Habitica sets isDue=False → not owed tonight
    _ready(monkeypatch, _tasks(dailys=[_daily("Weekly chore", isDue=False)]))
    assert "All done" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


def test_a_due_daily_is_shown_regardless_of_frequency(monkeypatch):
    # frequency is irrelevant for dailies — isDue is authoritative
    yearly = {"text": "Renew passport", "isDue": True, "completed": False, "streak": 1,
              "tags": [], "priority": 1, "frequency": "yearly"}  # fmt: skip
    _ready(monkeypatch, _tasks(dailys=[yearly]))
    assert "Renew passport" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


def test_a_monthly_habit_is_ignored(monkeypatch):
    _ready(monkeypatch, _tasks(habits=[_habit("Monthly review", tags=["tQ"], frequency="monthly")]))
    assert "All done" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


def test_a_down_only_bad_habit_is_ignored(monkeypatch):
    _ready(monkeypatch, _tasks(habits=[_habit("No sugar", tags=["tQ"], up=False)]))
    assert "All done" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


def test_a_habit_without_a_frequency_is_treated_as_daily(monkeypatch):
    bare = {"text": "Stretch", "up": True, "counterUp": 0, "counterDown": 0, "tags": []}
    _ready(monkeypatch, _tasks(habits=[bare]))
    assert "Stretch" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body


# ─── filtering: type toggles & tag whitelist ───


def test_notify_dailies_off_hides_all_dailies(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Morning prayer")]))
    config = {**CONFIG, "notify_dailies": False}
    assert "All done" in HabiticaSource().check(AT_NUDGE, config)[0].body


def test_notify_habits_off_hides_all_habits(monkeypatch):
    _ready(monkeypatch, _tasks(habits=[_habit("Meditation")]))
    config = {**CONFIG, "notify_habits": False}
    assert "All done" in HabiticaSource().check(AT_NUDGE, config)[0].body


def test_notify_todos_off_hides_today_todos(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("Write email", date=TODAY_ISO)]))
    config = {**CONFIG, "notify_todos": False}
    body = HabiticaSource().check(AT_NUDGE, config)[0].body
    assert "Write email" not in body


def test_tag_whitelist_shows_only_allowed_tags(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            dailys=[
                _daily("Prayer 1", tags=["tP"]),  # prayer tag
                _daily("Quran", tags=["tQ"]),  # quran tag
            ]
        ),
    )
    config = {**CONFIG, "tag_whitelist": ["prayer"]}  # only prayer allowed
    body = HabiticaSource().check(AT_NUDGE, config)[0].body
    assert "Prayer 1" in body and "Quran" not in body


def test_tag_whitelist_null_allows_all_tags(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            dailys=[
                _daily("Prayer 1", tags=["tP"]),
                _daily("Quran", tags=["tQ"]),
            ]
        ),
    )
    config = {**CONFIG, "tag_whitelist": None}  # explicit None = no filtering
    body = HabiticaSource().check(AT_NUDGE, config)[0].body
    assert "Prayer 1" in body and "Quran" in body


def test_tag_whitelist_respects_at_risk_dailies(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            dailys=[
                _daily("At-risk prayer", streak=50, tags=["tP"]),  # prayer tag, at-risk
                _daily("At-risk quran", streak=50, tags=["tQ"]),  # quran tag, at-risk
            ]
        ),
    )
    config = {**CONFIG, "tag_whitelist": ["prayer"]}  # only prayer allowed
    body = HabiticaSource().check(AT_NUDGE, config)[0].body
    assert "At-risk prayer" in body and "At-risk quran" not in body


def test_notify_dailies_off_hides_at_risk_too(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("At-risk task", streak=50)]))
    config = {**CONFIG, "notify_dailies": False}
    assert "All done" in HabiticaSource().check(AT_NUDGE, config)[0].body


# ─── to-dos due today as full sections (Phase 2) ───


def test_todos_due_today_in_sections(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("Write email", date=TODAY_ISO)]))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Write email" in body and "To-dos" in body


def test_todos_in_sections_sorted_by_priority(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            todos=[
                _todo("Trivial task", date=TODAY_ISO, priority=0.1),
                _todo("Hard task", date=TODAY_ISO, priority=2),
            ]
        ),
    )
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert body.index("Hard task") < body.index("Trivial task")


def test_todos_in_sections_capped(monkeypatch):
    many_todos = [_todo(f"Task {i}", date=TODAY_ISO) for i in range(9)]
    _ready(monkeypatch, _tasks(todos=many_todos))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "To-dos · 9" in body and "+4 more" in body


def test_todos_capped_shows_plus_n(monkeypatch):
    many_todos = [_todo(f"T{i}", date=TODAY_ISO) for i in range(7)]
    _ready(monkeypatch, _tasks(todos=many_todos))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "+2 more" in body


def test_todos_section_after_at_risk_and_overdue(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            dailys=[_daily("At-risk daily", streak=50)],
            todos=[
                _todo("Overdue", date="2026-11-10"),  # past
                _todo("Today", date=TODAY_ISO),  # today
            ],
        ),
    )
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    # Order: At risk → Overdue → Sections
    assert body.index("At-risk daily") < body.index("Overdue") < body.index("Today")


def test_todos_with_tags_appear_under_tag_section(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(todos=[_todo("Work email", tags=["tP"], date=TODAY_ISO)]),
    )
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    # Tag "tP" = "prayer", so section should be "Prayer"
    assert "Work email" in body and "Prayer" in body


def test_untagged_todos_fallback_to_todos_section(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("Untagged", date=TODAY_ISO, tags=[])]))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Untagged" in body and "To-dos" in body


def test_todos_respect_phase1_whitelist_filter(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            todos=[
                _todo("Prayer task", tags=["tP"], date=TODAY_ISO),
                _todo("Quran task", tags=["tQ"], date=TODAY_ISO),
            ]
        ),
    )
    config = {**CONFIG, "tag_whitelist": ["prayer"]}
    body = HabiticaSource().check(AT_NUDGE, config)[0].body
    assert "Prayer task" in body and "Quran task" not in body


# ─── morning & evening nudges (Phase 3) ───


def test_morning_enabled_sends_at_time(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    morning_time = datetime(2026, 11, 16, 6, 3, tzinfo=TZ)  # 6:03 AM (within 5-min window of 6:00)
    config = {
        **CONFIG,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": False},
    }
    notes = HabiticaSource().check(morning_time, config)
    assert len(notes) == 1 and notes[0].title == "Habitica morning briefing"


def test_morning_disabled_sends_nothing(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    morning_time = datetime(2026, 11, 16, 6, 3, tzinfo=TZ)
    config = {
        **CONFIG,
        "morning": {"enabled": False, "time": "06:00"},
        "evening": {"enabled": False},
    }
    assert HabiticaSource().check(morning_time, config) == []


def test_both_morning_and_evening_send_when_both_enabled(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    morning_time = datetime(2026, 11, 16, 6, 3, tzinfo=TZ)
    config = {
        **CONFIG,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": True, "time": "06:00"},
    }
    notes = HabiticaSource().check(morning_time, config)
    assert {n.title for n in notes} == {"Habitica morning briefing", "Nightly check-in"}


def test_morning_summary_is_brief(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task 1"), _daily("Task 2")]))
    morning_time = datetime(2026, 11, 16, 6, 3, tzinfo=TZ)
    config = {
        **CONFIG,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": False},
    }
    notes = HabiticaSource().check(morning_time, config)
    body = notes[0].body
    # Morning shows per-type counts, never task names
    assert "2 dailies" in body and "Task 1" not in body and "Task 2" not in body


def test_morning_dedup_separate_from_evening(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    morning_time = datetime(2026, 11, 16, 6, 3, tzinfo=TZ)
    config = {
        **CONFIG,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": True, "time": "06:00"},
    }
    notes = HabiticaSource().check(morning_time, config)
    dedup_keys = [n.dedup_key for n in notes]
    assert "Habitica morning briefing" in dedup_keys
    assert "Nightly check-in" in dedup_keys
    assert dedup_keys[0] != dedup_keys[1]  # distinct dedup keys


def test_morning_respects_all_filters(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            dailys=[
                _daily("Prayer", tags=["tP"]),
                _daily("Quran", tags=["tQ"]),
            ]
        ),
    )
    morning_time = datetime(2026, 11, 16, 6, 3, tzinfo=TZ)
    config = {
        **CONFIG,
        "morning": {"enabled": True, "time": "06:00"},
        "evening": {"enabled": False},
        "tag_whitelist": ["prayer"],
    }
    notes = HabiticaSource().check(morning_time, config)
    body = notes[0].body
    # Only 1 task should be visible (Prayer), so "1 daily"
    assert "1 daily" in body


# ─── weekly digest (Phase 4) ───


@pytest.fixture(autouse=True)
def cleanup_state():
    """Clean up .noterpiper_state/ before and after each test."""
    state_dir = Path(".noterpiper_state")
    if state_dir.exists():
        shutil.rmtree(state_dir)
    yield
    if state_dir.exists():
        shutil.rmtree(state_dir)


def test_weekly_digest_enabled_sends_at_time(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    # Sunday 7:03 PM (within window of 7:00 PM)
    sunday = datetime(2026, 11, 22, 19, 3, tzinfo=TZ)  # Nov 22 is a Sunday
    config = {**CONFIG, "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"}}
    notes = HabiticaSource().check(sunday, config)
    assert any(n.title == WEEKLY_TITLE for n in notes)


def test_weekly_digest_disabled_sends_nothing(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    sunday = datetime(2026, 11, 22, 19, 3, tzinfo=TZ)
    config = {**CONFIG, "weekly": {"enabled": False, "day": "Sunday", "time": "19:00"}}
    notes = HabiticaSource().check(sunday, config)
    assert not any(n.title == WEEKLY_TITLE for n in notes)


def test_weekly_state_appends_daily_runs(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    # First run on Monday
    monday = datetime(2026, 11, 17, 21, 34, tzinfo=TZ)
    config = {**CONFIG, "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"}}
    HabiticaSource().check(monday, config)
    # Second run same day (should not duplicate)
    HabiticaSource().check(monday, config)
    # Verify state has one entry for today
    from noterpiper import state as state_module

    ws = state_module.load_weekly_state()
    assert len(ws["day_runs"]) == 1 and ws["day_runs"][0]["date"] == monday.date().isoformat()


def test_weekly_digest_dedup_key(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    sunday = datetime(2026, 11, 22, 19, 3, tzinfo=TZ)
    config = {**CONFIG, "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"}}
    notes = HabiticaSource().check(sunday, config)
    weekly_notes = [n for n in notes if n.title == WEEKLY_TITLE]
    assert len(weekly_notes) == 1 and weekly_notes[0].dedup_key == WEEKLY_TITLE


def test_weekly_summary_format(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(
            dailys=[
                _daily("Task 1", streak=10),
                _daily("Task 2", streak=50),  # best streak
            ]
        ),
    )
    sunday = datetime(2026, 11, 22, 19, 3, tzinfo=TZ)
    config = {**CONFIG, "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"}}
    notes = HabiticaSource().check(sunday, config)
    weekly_notes = [n for n in notes if n.title == WEEKLY_TITLE]
    body = weekly_notes[0].body
    # Should mention the best streak
    assert "Best streak" in body or "2 item" in body  # either best streak or count


def test_weekly_state_reset_after_send(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    # First run on Monday (accumulate state)
    monday = datetime(2026, 11, 17, 21, 34, tzinfo=TZ)
    config = {**CONFIG, "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"}}
    HabiticaSource().check(monday, config)
    # Verify Monday was added
    from noterpiper import state as state_module

    ws = state_module.load_weekly_state()
    assert len(ws["day_runs"]) == 1
    # Second run on Sunday at digest time
    sunday = datetime(2026, 11, 22, 19, 3, tzinfo=TZ)
    HabiticaSource().check(sunday, config)
    # Verify state was reset after digest
    ws = state_module.load_weekly_state()
    assert len(ws["day_runs"]) == 0  # state cleared after sending digest
    assert ws["last_digest_sent"] is not None


def test_weekly_state_missing_handles_gracefully(monkeypatch):
    # State file doesn't exist yet — should not crash
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    sunday = datetime(2026, 11, 22, 19, 3, tzinfo=TZ)
    config = {**CONFIG, "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"}}
    notes = HabiticaSource().check(sunday, config)
    # Should complete without error
    assert len(notes) >= 1


def test_weekly_digest_wrong_day_no_send(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    # Monday, but expecting Sunday
    monday = datetime(2026, 11, 17, 19, 3, tzinfo=TZ)
    config = {**CONFIG, "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"}}
    notes = HabiticaSource().check(monday, config)
    assert not any(n.title == WEEKLY_TITLE for n in notes)


# ─── regressions: the production bugs the first rewrite shipped ───


def test_user_configured_time_still_drives_the_nudge_with_new_defaults(monkeypatch):
    """The defaults now carry `morning`/`weekly` sections. Merged over a real config
    (top-level time/enabled from the phone page), the user's time must still win —
    the first rewrite ignored it and fired at a hardcoded nested default."""
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    merged = {**HabiticaSource.defaults, "time": "21:00", "enabled": True, "streak_risk": 40}
    at_users_time = datetime(2026, 11, 16, 21, 3, tzinfo=TZ)
    notes = HabiticaSource().check(at_users_time, merged)
    assert [n.title for n in notes] == [NUDGE_TITLE]
    at_default_time = datetime(2026, 11, 16, 21, 34, tzinfo=TZ)  # defaults' 21:30, not the user's
    assert HabiticaSource().check(at_default_time, merged) == []


def test_forced_sends_exactly_one_full_nudge(monkeypatch):
    """'Send now' is one button → one push (the full summary), even with morning and
    weekly enabled — the first rewrite sent several and tripped ntfy's rate limit."""
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    config = {
        **HabiticaSource.defaults,
        "force": True,
        "morning": {"enabled": True, "time": "06:00"},
        "weekly": {"enabled": True, "day": "Sunday", "time": "19:00"},
    }
    notes = HabiticaSource().check(datetime(2026, 11, 22, 19, 3, tzinfo=TZ), config)
    assert len(notes) == 1 and notes[0].title == NUDGE_TITLE and notes[0].dedup_key is None


def test_weekly_invalid_day_never_kills_the_nudge(monkeypatch):
    """A typo'd weekly day must not raise out of check() — that would silence the
    nightly nudge entirely."""
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    config = {**CONFIG, "weekly": {"enabled": True, "day": "Funday", "time": "19:00"}}
    notes = HabiticaSource().check(AT_NUDGE, config)
    assert [n.title for n in notes] == [NUDGE_TITLE]  # evening fine, weekly skipped


def test_tag_whitelist_is_case_insensitive(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Prayer task", tags=["tP"])]))
    notes = HabiticaSource().check(AT_NUDGE, {**CONFIG, "tag_whitelist": ["PRAYER"]})
    assert "Prayer task" in notes[0].body


def test_tag_whitelist_accepts_a_comma_string(monkeypatch):
    """A config text field stores 'prayer, quran' — accept it, not just a list."""
    _ready(
        monkeypatch,
        _tasks(dailys=[_daily("Prayer task", tags=["tP"]), _daily("Quran task", tags=["tQ"])]),
    )
    notes = HabiticaSource().check(AT_NUDGE, {**CONFIG, "tag_whitelist": "prayer, quran"})
    body = notes[0].body
    assert "Prayer task" in body and "Quran task" in body


def test_malformed_time_never_crashes(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("Task")]))
    assert HabiticaSource().check(AT_NUDGE, {"time": "not-a-time", "enabled": True}) == []
