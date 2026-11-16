"""Phase 5 — HabiticaSource: the nightly-nudge plugin.

Same gating as before (configured + enabled + at the set time) and the same grouped
message, now behind the Source contract. A stable title gives it robust once-per-day
dedup under the ~2-minute engine. Habitica is mocked."""
from datetime import datetime, timedelta, timezone

from noterpiper.engine import Source
from noterpiper.plugins.habitica import HabiticaSource

TZ = timezone(timedelta(hours=5))
AT_NUDGE = datetime(2026, 11, 16, 21, 34, tzinfo=TZ)      # within the default window of 21:30
BEFORE = datetime(2026, 11, 16, 20, 0, tzinfo=TZ)
CONFIG = {"time": "21:30", "enabled": True}
TASKS = {"habits": [{"text": "Fajr", "counterUp": 0, "counterDown": 0}],
         "dailys": [{"text": "Mulk", "isDue": True, "completed": False, "streak": 50}],
         "todos": [], "rewards": []}


def _ready(monkeypatch, tasks=TASKS):
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: True)
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tasks_by_type", lambda: tasks)


def test_habiticasource_satisfies_the_Source_contract():
    assert isinstance(HabiticaSource(), Source)
    assert HabiticaSource().id == "habitica"


def test_no_nudge_when_habitica_is_not_configured(monkeypatch):
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: False)
    assert HabiticaSource().check(AT_NUDGE, CONFIG) == []


def test_no_nudge_when_disabled(monkeypatch):
    _ready(monkeypatch)
    assert HabiticaSource().check(AT_NUDGE, {"time": "21:30", "enabled": False}) == []


def test_no_nudge_before_the_set_time(monkeypatch):
    _ready(monkeypatch)
    assert HabiticaSource().check(BEFORE, CONFIG) == []


def test_nudge_at_time_is_one_notification_with_a_stable_dedup_title(monkeypatch):
    _ready(monkeypatch)
    notes = HabiticaSource().check(AT_NUDGE, CONFIG)
    assert len(notes) == 1
    n = notes[0]
    assert n.dedup_key == n.title                 # stable title == dedup key → cache dedup works
    assert "midnight" in n.body.lower()           # the count summary now lives in the body
    assert "Fajr" in n.body and "Mulk" in n.body  # the grouped detail survives


def test_window_from_config_is_honored(monkeypatch):
    _ready(monkeypatch)
    now = datetime(2026, 11, 16, 21, 45, tzinfo=TZ)      # 15 min after 21:30
    assert HabiticaSource().check(now, {"time": "21:30", "enabled": True, "window": 30}) != []
    assert HabiticaSource().check(now, {"time": "21:30", "enabled": True, "window": 10}) == []


def test_task_fetch_failure_sends_nothing(monkeypatch):
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: True)
    def boom():
        raise RuntimeError("habitica down")
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tasks_by_type", boom)
    assert HabiticaSource().check(AT_NUDGE, CONFIG) == []


def test_force_sends_even_when_off_and_out_of_time(monkeypatch):
    """The on-demand 'send now' button: fire regardless of the enabled flag or the
    clock, and with no dedup key so it always delivers."""
    _ready(monkeypatch)
    forced = {"time": "21:30", "enabled": False, "force": True}
    notes = HabiticaSource().check(BEFORE, forced)       # disabled + wrong time, but forced
    assert len(notes) == 1
    assert notes[0].dedup_key is None                    # forced → no dedup, always delivers


def test_todos_due_and_overdue_appear_with_overdue_marked(monkeypatch):
    tasks = {"habits": [], "dailys": [], "rewards": [], "todos": [
        {"text": "Submit report", "date": "2026-11-14T00:00:00.000Z"},   # overdue
        {"text": "Call dentist", "date": "2026-11-16T00:00:00.000Z"},    # due today
        {"text": "Future plan", "date": "2026-11-20T00:00:00.000Z"},     # not due yet
        {"text": "Someday"}]}                                            # no due date
    _ready(monkeypatch, tasks)
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "To-dos · 2" in body                          # only the due + overdue counted
    assert "Submit report (overdue)" in body
    assert "Call dentist" in body
    assert "Future plan" not in body and "Someday" not in body


def test_at_risk_streaks_surface_at_the_top(monkeypatch):
    tasks = {"habits": [], "rewards": [], "todos": [], "dailys": [
        {"text": "Mulk", "isDue": True, "completed": False, "streak": 52},   # at risk (>=7)
        {"text": "Walk", "isDue": True, "completed": False, "streak": 3}]}   # normal
    _ready(monkeypatch, tasks)
    n = HabiticaSource().check(AT_NUDGE, CONFIG)[0]
    assert "at risk 🔥" in n.body.splitlines()[0]        # headline flags it
    assert "At risk" in n.body
    assert n.body.index("Mulk") < n.body.index("Walk")   # at-risk shown before the normal daily
    assert n.priority == "high"


def test_long_lists_are_capped_but_count_stays_true(monkeypatch):
    many = [{"text": f"Daily{i}", "isDue": True, "completed": False, "streak": 1} for i in range(9)]
    tasks = {"habits": [], "rewards": [], "todos": [], "dailys": many}
    _ready(monkeypatch, tasks)
    body = HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    assert "Dailies · 9" in body                         # the count covers everything
    assert "+4 more" in body                             # but only ~5 names are listed


def test_streak_risk_threshold_is_configurable(monkeypatch):
    tasks = {"habits": [], "rewards": [], "todos": [],
             "dailys": [{"text": "Walk", "isDue": True, "completed": False, "streak": 5}]}
    _ready(monkeypatch, tasks)
    assert "At risk" not in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body      # default 7 → not at risk
    low = HabiticaSource().check(AT_NUDGE, {**CONFIG, "streak_risk": 3})[0].body  # 3 → streak 5 is at risk
    assert "At risk" in low


def test_show_todos_toggle(monkeypatch):
    tasks = {"habits": [], "rewards": [],
             "dailys": [{"text": "Walk", "isDue": True, "completed": False, "streak": 2}],
             "todos": [{"text": "Call dentist", "date": "2026-11-16T00:00:00.000Z"}]}
    _ready(monkeypatch, tasks)
    assert "To-dos" in HabiticaSource().check(AT_NUDGE, CONFIG)[0].body
    off = HabiticaSource().check(AT_NUDGE, {**CONFIG, "show_todos": False})[0].body
    assert "Call dentist" not in off and "Walk" in off   # to-dos hidden, dailies still shown


def test_show_dailies_toggle_also_hides_at_risk(monkeypatch):
    tasks = {"habits": [{"text": "Fajr", "counterUp": 0, "counterDown": 0}], "rewards": [], "todos": [],
             "dailys": [{"text": "Mulk", "isDue": True, "completed": False, "streak": 50}]}
    _ready(monkeypatch, tasks)
    off = HabiticaSource().check(AT_NUDGE, {**CONFIG, "show_dailies": False})[0].body
    assert "Mulk" not in off and "At risk" not in off    # dailies + their at-risk gone
    assert "Fajr" in off                                 # prayers still shown


def test_all_groups_off_sends_nothing(monkeypatch):
    _ready(monkeypatch)                                  # has prayers + a due daily to show
    off = {**CONFIG, "show_todos": False, "show_dailies": False, "show_prayers": False}
    assert HabiticaSource().check(AT_NUDGE, off) == []   # every group hidden → no nudge at all


def test_force_sends_nothing_when_all_groups_off(monkeypatch):
    _ready(monkeypatch)                                  # even 'send now' can't show a hidden-everything nudge
    off = {"time": "21:30", "enabled": False, "force": True,
           "show_todos": False, "show_dailies": False, "show_prayers": False}
    assert HabiticaSource().check(BEFORE, off) == []     # the all-off guard precedes the force path


def test_show_prayers_toggle(monkeypatch):
    tasks = {"habits": [{"text": "Fajr", "counterUp": 0, "counterDown": 0}], "rewards": [], "todos": [],
             "dailys": [{"text": "Walk", "isDue": True, "completed": False, "streak": 2}]}
    _ready(monkeypatch, tasks)
    off = HabiticaSource().check(AT_NUDGE, {**CONFIG, "show_prayers": False})[0].body
    assert "Fajr" not in off and "Walk" in off
