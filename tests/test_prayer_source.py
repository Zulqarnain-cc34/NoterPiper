"""Phase 4 — PrayerSource: the prayer-reminder plugin.

Same reminder logic as before, now behind the Source contract: given `now` and its
config slice, return the prayers due right now as Notifications. Aladhan is mocked."""
from datetime import datetime, timedelta, timezone

from muezzin.engine import Notification, Source
from muezzin.plugins.prayer import PrayerSource

TZ = timezone(timedelta(hours=5))
TIMINGS = {"Fajr": "05:00", "Sunrise": "06:30", "Dhuhr": "12:00", "Asr": "15:30",
           "Maghrib": "18:00", "Isha": "19:30", "Midnight": "00:00"}
CONFIG = {"city": "Makkah", "country": "Saudi Arabia", "method": "4",
          "reminders": {"Fajr": {"after_start": 5}, "Maghrib": {"before_end": 30}}}


def _patch(monkeypatch, timings=TIMINGS):
    monkeypatch.setattr("muezzin.plugins.prayer.fetch_timings", lambda c, co, m: timings)


def test_prayersource_satisfies_the_Source_contract():
    assert isinstance(PrayerSource(), Source)
    assert PrayerSource().id == "prayer"


def test_a_due_prayer_becomes_a_max_priority_notification(monkeypatch):
    _patch(monkeypatch)
    now = datetime(2026, 11, 16, 5, 6, tzinfo=TZ)        # Fajr after_start 5 → 05:05, due at 05:06
    notes = PrayerSource().check(now, CONFIG)
    assert [n.title for n in notes] == ["Fajr"]
    n = notes[0]
    assert n.priority == "max"
    assert n.tags == ("mosque",)
    assert n.dedup_key == "Fajr"                          # dedup_key == title → ntfy dedup matches
    assert "ends" in n.body


def test_nothing_due_returns_empty(monkeypatch):
    _patch(monkeypatch)
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    assert PrayerSource().check(now, CONFIG) == []


def test_before_end_rule_fires_before_the_window_closes(monkeypatch):
    _patch(monkeypatch)
    now = datetime(2026, 11, 16, 19, 1, tzinfo=TZ)        # Maghrib ends at Isha 19:30; −30 → 19:00
    assert [n.title for n in PrayerSource().check(now, CONFIG)] == ["Maghrib"]


def test_a_broken_timing_skips_only_that_prayer(monkeypatch):
    broken = {k: v for k, v in TIMINGS.items() if k != "Dhuhr"}   # Zohar's start missing
    _patch(monkeypatch, broken)
    now = datetime(2026, 11, 16, 5, 6, tzinfo=TZ)
    config = {**CONFIG, "reminders": {"Fajr": {"after_start": 5}, "Zohar": {"after_start": 5}}}
    assert [n.title for n in PrayerSource().check(now, config)] == ["Fajr"]
