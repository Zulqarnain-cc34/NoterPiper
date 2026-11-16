"""Phase 5 — HabiticaSource: the nightly-nudge plugin.

Same gating as before (configured + enabled + at the set time) and the same grouped
message, now behind the Source contract. A stable title gives it robust once-per-day
dedup under the ~2-minute engine. Habitica is mocked."""
from datetime import datetime, timedelta, timezone

from noterpiper.engine import Source
from noterpiper.plugins.habitica import HabiticaSource

TZ = timezone(timedelta(hours=5))
AT_NUDGE = datetime(2026, 11, 16, 21, 35, tzinfo=TZ)      # within [21:30, 22:00)
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


def test_task_fetch_failure_sends_nothing(monkeypatch):
    monkeypatch.setattr("noterpiper.plugins.habitica.api.configured", lambda: True)
    def boom():
        raise RuntimeError("habitica down")
    monkeypatch.setattr("noterpiper.plugins.habitica.api.fetch_tasks_by_type", boom)
    assert HabiticaSource().check(AT_NUDGE, CONFIG) == []
