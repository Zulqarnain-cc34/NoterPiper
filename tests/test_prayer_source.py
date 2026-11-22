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


# ─── madhab: one setting drives Asr school AND Isha's end together ───


def test_fetch_timings_defaults_to_the_hanafi_school(monkeypatch):
    seen = {}

    def fake_get_json(url):
        seen["url"] = url
        return {"data": {"timings": {"Asr": "15:24"}}}

    monkeypatch.setattr("noterpiper.plugins.prayer.net.get_json", fake_get_json)
    fetch_timings("Lahore", "Pakistan", "1")  # school omitted → must still default right
    assert "school=1" in seen["url"]


def test_default_madhab_is_hanafi_asr_school_and_isha_ends_at_fajr(monkeypatch):
    """Choosing nothing (the default) must fix BOTH axes together: the Hanafi Asr
    school is requested from Aladhan, and Isha's displayed end is Fajr, not midnight."""
    seen = {}

    def fake_fetch(city, country, method, school):
        seen["school"] = school
        return TIMINGS

    monkeypatch.setattr("noterpiper.plugins.prayer.fetch_timings", fake_fetch)
    config = {**CONFIG, "reminders": {**CONFIG["reminders"], "Isha": {"after_start": 60}}}
    now = datetime(2026, 11, 16, 20, 31, tzinfo=TZ)  # Isha 19:30 + 60 → 20:30, due at 20:31
    notes = PrayerSource().check(now, config)
    assert seen["school"] == "1"
    assert [n.title for n in notes] == ["Isha"]
    assert "ends 5:00 AM" in notes[0].body  # TIMINGS["Fajr"] = "05:00", not Midnight ("00:00")


def test_standard_madhab_is_shafii_asr_school_and_isha_ends_at_midnight(monkeypatch):
    """The 'standard' choice must fix BOTH axes together the other way: Aladhan's
    Shafi'i/standard Asr school, and Isha's displayed end reverts to midnight."""
    seen = {}

    def fake_fetch(city, country, method, school):
        seen["school"] = school
        return TIMINGS

    monkeypatch.setattr("noterpiper.plugins.prayer.fetch_timings", fake_fetch)
    config = {
        **CONFIG,
        "madhab": "standard",
        "reminders": {**CONFIG["reminders"], "Isha": {"after_start": 60}},
    }
    now = datetime(2026, 11, 16, 20, 31, tzinfo=TZ)
    notes = PrayerSource().check(now, config)
    assert seen["school"] == "0"
    assert [n.title for n in notes] == ["Isha"]
    assert "ends 12:00 AM" in notes[0].body  # TIMINGS["Midnight"] = "00:00"


def test_isha_before_end_fallback_also_follows_the_madhab(monkeypatch):
    """The before_end default (no explicit Isha rule) must use the SAME madhab-driven
    end as the display — ends_at backs both the shown text and this fallback's math."""
    _patch(monkeypatch)
    now = datetime(2026, 11, 16, 4, 31, tzinfo=TZ)  # Fajr 05:00 − 30 (DEFAULT_RULE) → 04:30
    notes = PrayerSource().check(now, CONFIG)  # CONFIG has no Isha-specific rule, default madhab
    assert [n.title for n in notes] == ["Isha"]
    assert "ends 5:00 AM" in notes[0].body


def test_an_unrecognized_madhab_falls_back_to_the_default_instead_of_crashing(monkeypatch):
    seen = {}

    def fake_fetch(city, country, method, school):
        seen["school"] = school
        return TIMINGS

    monkeypatch.setattr("noterpiper.plugins.prayer.fetch_timings", fake_fetch)
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    PrayerSource().check(now, {**CONFIG, "madhab": "not-a-real-madhab"})
    assert seen["school"] == "1"  # fell back to Hanafi, didn't raise


def test_prayer_can_be_disabled_like_every_other_plugin(monkeypatch):
    called = []
    monkeypatch.setattr(
        "noterpiper.plugins.prayer.fetch_timings", lambda *a: called.append(1) or {}
    )
    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    assert PrayerSource().check(now, {"enabled": False}) == []
    assert called == []  # disabled → not even a fetch
