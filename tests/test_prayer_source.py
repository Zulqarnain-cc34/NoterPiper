"""Phase 4 — PrayerSource: the prayer-reminder plugin.

Same reminder logic as before, now behind the Source contract: given `now` and its
config slice, return the prayers due right now as Notifications. Aladhan is mocked."""

from datetime import datetime, timedelta, timezone

from noterpiper.engine import Source
from noterpiper.plugins.prayer import PrayerSource, fetch_timings

TZ = timezone(timedelta(hours=5))
TIMINGS = {
    "Fajr": "05:00",
    "Sunrise": "06:30",
    "Dhuhr": "12:00",
    "Asr": "15:30",
    "Maghrib": "18:00",
    "Isha": "19:30",
    "Midnight": "00:00",
}
CONFIG = {
    "city": "Makkah",
    "country": "Saudi Arabia",
    "method": "4",
    "reminders": {"Fajr": {"after_start": 5}, "Maghrib": {"before_end": 30}},
}


def _patch(monkeypatch, timings=TIMINGS):
    monkeypatch.setattr("noterpiper.plugins.prayer.fetch_timings", lambda c, co, m, s: timings)


def test_prayersource_satisfies_the_Source_contract():
    assert isinstance(PrayerSource(), Source)
    assert PrayerSource().id == "prayer"


def test_a_due_prayer_becomes_a_max_priority_notification(monkeypatch):
    _patch(monkeypatch)
    now = datetime(2026, 11, 16, 5, 6, tzinfo=TZ)  # Fajr after_start 5 → 05:05, due at 05:06
    notes = PrayerSource().check(now, CONFIG)
    assert [n.title for n in notes] == ["Fajr"]
    n = notes[0]
    assert n.priority == "max"
    assert n.tags == ("mosque",)
    assert n.dedup_key == "Fajr"  # dedup_key == title → ntfy dedup matches
    assert "ends" in n.body


def test_nothing_due_returns_empty(monkeypatch):
    _patch(monkeypatch)
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    assert PrayerSource().check(now, CONFIG) == []


def test_before_end_rule_fires_before_the_window_closes(monkeypatch):
    _patch(monkeypatch)
    now = datetime(2026, 11, 16, 19, 1, tzinfo=TZ)  # Maghrib ends at Isha 19:30; −30 → 19:00
    assert [n.title for n in PrayerSource().check(now, CONFIG)] == ["Maghrib"]


def test_window_from_config_is_honored(monkeypatch):
    _patch(monkeypatch)
    now = datetime(2026, 11, 16, 5, 10, tzinfo=TZ)  # Fajr reminder 05:05 → 5 min ago
    assert [n.title for n in PrayerSource().check(now, {**CONFIG, "window": 20})] == ["Fajr"]
    assert PrayerSource().check(now, {**CONFIG, "window": 3}) == []  # 5 min > 3-min window


def test_a_broken_timing_skips_only_that_prayer(monkeypatch):
    broken = {k: v for k, v in TIMINGS.items() if k != "Dhuhr"}  # Zohar's start missing
    _patch(monkeypatch, broken)
    now = datetime(2026, 11, 16, 5, 6, tzinfo=TZ)
    config = {**CONFIG, "reminders": {"Fajr": {"after_start": 5}, "Zohar": {"after_start": 5}}}
    assert [n.title for n in PrayerSource().check(now, config)] == ["Fajr"]


def test_fetch_timings_defaults_to_the_hanafi_school(monkeypatch):
    """Without an explicit school, Aladhan defaults to the earlier Shafi'i-style
    Asr — wrong for a Hanafi follower by 40+ minutes, and it also skews Zohar's
    displayed end (= Asr's start) by the same amount. Our default must be Hanafi."""
    seen = {}

    def fake_get_json(url):
        seen["url"] = url
        return {"data": {"timings": {"Asr": "15:24"}}}

    monkeypatch.setattr("noterpiper.plugins.prayer.net.get_json", fake_get_json)
    fetch_timings("Lahore", "Pakistan", "1")  # school omitted → must still default right
    assert "school=1" in seen["url"]


def test_fetch_timings_honors_an_explicit_school(monkeypatch):
    """Not everyone is Hanafi — the school must be a real, overridable parameter,
    not hardcoded, so a Shafi'i/Maliki/Hanbali user (or a fork) can set school=0."""
    seen = {}

    def fake_get_json(url):
        seen["url"] = url
        return {"data": {"timings": {"Asr": "14:42"}}}

    monkeypatch.setattr("noterpiper.plugins.prayer.net.get_json", fake_get_json)
    fetch_timings("Lahore", "Pakistan", "1", "0")
    assert "school=0" in seen["url"]


def test_check_passes_the_configured_school_through_to_aladhan(monkeypatch):
    """End-to-end: an explicit config['school'] must actually reach fetch_timings,
    and the default (no 'school' key at all) must still resolve to Hanafi."""
    seen = {}
    monkeypatch.setattr(
        "noterpiper.plugins.prayer.fetch_timings",
        lambda c, co, m, s: (seen.__setitem__("school", s), TIMINGS)[1],
    )
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    PrayerSource().check(now, CONFIG)  # no 'school' key in CONFIG at all
    assert seen["school"] == "1"
    PrayerSource().check(now, {**CONFIG, "school": "0"})
    assert seen["school"] == "0"


def test_prayer_can_be_disabled_like_every_other_plugin(monkeypatch):
    called = []
    monkeypatch.setattr(
        "noterpiper.plugins.prayer.fetch_timings", lambda *a: called.append(1) or {}
    )
    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    assert PrayerSource().check(now, {"enabled": False}) == []
    assert called == []  # disabled → not even a fetch
