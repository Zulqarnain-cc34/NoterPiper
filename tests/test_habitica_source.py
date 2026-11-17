"""HabiticaSource — the tag-driven nightly nudge.

Same gating as before (configured + enabled + at the set time), but categorisation is
now by the user's tags, reading only Habitica's structured fields — never a title's
wording. Habitica (tasks + tags) is mocked; `now` is engine-supplied."""

import urllib.error
from datetime import datetime, timedelta, timezone

from noterpiper.engine import Source
from noterpiper.plugins.habitica import AUTH_FAIL_TITLE, NUDGE_TITLE, HabiticaSource

TZ = timezone(timedelta(hours=5))
AT_NUDGE = datetime(2026, 11, 16, 21, 34, tzinfo=TZ)  # within the default window of 21:30
BEFORE = datetime(2026, 11, 16, 20, 0, tzinfo=TZ)
CONFIG = {"time": "21:30", "enabled": True}
TAGS = {"tP": "prayer", "tQ": "quran", "tA": "Archived"}  # tag-id → name


def _tasks(habits=(), dailys=(), todos=()):
    return {"habits": list(habits), "dailys": list(dailys), "todos": list(todos), "rewards": []}


def _ready(monkeypatch, tasks, tags=TAGS):
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: True)
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tasks_by_type", lambda: tasks)
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tags", lambda: tags)


def _daily(text, streak=1, tags=(), isDue=True, completed=False):
    return {
        "text": text,
        "isDue": isDue,
        "completed": completed,
        "streak": streak,
        "tags": list(tags),
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


def _todo(text, tags=(), completed=False, date=None):
    return {"text": text, "completed": completed, "date": date, "tags": list(tags)}


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
    _ready(monkeypatch, _tasks(todos=[_todo("--------"), _todo("Buy milk")]))
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


def test_untagged_todo_falls_back_to_type(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("Buy milk")]))
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


def test_overdue_todo_is_flagged_and_urgent(monkeypatch):
    _ready(monkeypatch, _tasks(todos=[_todo("Report", date="2026-11-14T00:00:00.000Z")]))
    n = HabiticaSource().check(AT_NUDGE, CONFIG)[0]
    assert "Report (overdue)" in n.body and n.priority == "high"


def test_future_and_undated_todos_show_without_overdue(monkeypatch):
    _ready(
        monkeypatch,
        _tasks(todos=[_todo("Future", date="2026-11-20T00:00:00.000Z"), _todo("Someday")]),
    )
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "To-dos · 2" in body and "overdue" not in body


def test_long_lists_are_capped_but_count_stays_true(monkeypatch):
    many = [_daily(f"D{i}") for i in range(9)]
    _ready(monkeypatch, _tasks(dailys=many))
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Dailies · 9" in body and "+4 more" in body


def test_titles_are_header_safe(monkeypatch):
    _ready(monkeypatch, _tasks(dailys=[_daily("X")]))
    HabiticaSource().check(AT_NUDGE, CONFIG)[0].title.encode("latin-1")  # must not raise
