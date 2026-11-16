"""Locks the reminder-timing logic (offline, no network)."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import schedule_prayers as sp  # noqa: E402
from muezzin import settings  # noqa: E402

TZ = timezone(timedelta(hours=5))
TIMINGS = {  # sample prayer times (HH:MM, local)
    "Fajr": "05:00", "Sunrise": "06:30", "Dhuhr": "12:00", "Asr": "15:30",
    "Maghrib": "17:30", "Isha": "19:00", "Midnight": "00:00",
}


def test_before_end_is_30_min_before_window_closes():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    rules = {"Zohar": {"before_end": 30}, "Asr": {"before_end": 30}}
    plan = dict(sp.plan_reminders(TIMINGS, now, rules))
    assert plan["Zohar"] == datetime(2026, 11, 16, 15, 0, tzinfo=TZ)   # Asr 15:30 − 30
    assert plan["Asr"] == datetime(2026, 11, 16, 17, 0, tzinfo=TZ)     # Maghrib 17:30 − 30


def test_after_start_rule():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    rules = {"Isha": {"after_start": 60}}
    plan = dict(sp.plan_reminders(TIMINGS, now, rules))
    assert plan["Isha"] == datetime(2026, 11, 16, 20, 0, tzinfo=TZ)    # Isha 19:00 + 60


def test_missing_rule_defaults_to_30_before_end():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    plan = dict(sp.plan_reminders(TIMINGS, now, {}))        # no rules → default
    assert plan["Maghrib"] == datetime(2026, 11, 16, 18, 30, tzinfo=TZ)  # Isha 19:00 − 30


def test_past_reminder_rolls_to_next_day():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    plan = dict(sp.plan_reminders(TIMINGS, now, {}))
    # Fajr window ended at sunrise 06:30 (past) → tomorrow 06:00
    assert plan["Fajr"] == datetime(2026, 11, 17, 6, 0, tzinfo=TZ)


def test_repo_config_loads_a_valid_rule_per_prayer():
    """The shipped config.json parses and yields a usable reminder rule for every
    prayer. Asserts the structure, not the offset values — those are personal and
    change whenever settings are edited, so pinning them here just makes CI brittle."""
    reminders = settings.load_settings().reminders
    for prayer in ("Fajr", "Zohar", "Asr", "Maghrib", "Isha"):
        rule = reminders[prayer]
        assert isinstance(rule, dict), f"{prayer} rule must be an object"
        key = "after_start" if "after_start" in rule else "before_end"
        assert key in rule, f"{prayer} needs after_start or before_end"
        assert isinstance(rule[key], int) and rule[key] >= 0, f"{prayer} offset must be a non-negative int"


def test_bad_response_error_points_to_config(monkeypatch):
    monkeypatch.setattr(sp.net, "get_json", lambda url: {})   # malformed Aladhan response
    with pytest.raises(RuntimeError, match="config.json"):
        sp.fetch_timings("Nowhere", "Nowhere", "1")


def test_main_reads_location_from_config_json(tmp_path, monkeypatch):
    # config.json (not .env) should decide the location sent to Aladhan.
    monkeypatch.setattr(sp.config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sp.config, "ENV_FILE", tmp_path / "absent.env")
    for k in ("PRAYER_CITY", "PRAYER_COUNTRY", "PRAYER_METHOD", "PRAYER_TIMEZONE", "NTFY_TOPIC"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "config.json").write_text(json.dumps(
        {"city": "Istanbul", "country": "Turkey", "method": "5",
         "reminders": {"Isha": {"after_start": 60}}}))
    seen = {}
    monkeypatch.setattr(sp, "fetch_timings",
                        lambda c, co, m: (seen.update(city=c, country=co, method=m) or (TIMINGS, "Europe/Istanbul")))
    assert sp.main() == 0                       # no NTFY_TOPIC → dry run
    assert seen == {"city": "Istanbul", "country": "Turkey", "method": "5"}


def test_bad_rule_skips_only_that_prayer():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    rules = {"Asr": {"before_end": "oops"}}         # typo an end-user could make on their phone
    plan = dict(sp.plan_reminders(TIMINGS, now, rules))
    assert "Asr" not in plan                          # the bad one is skipped
    assert "Maghrib" in plan and "Zohar" in plan      # the others still schedule


def test_missing_timing_skips_only_that_prayer():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    partial = {k: v for k, v in TIMINGS.items() if k != "Maghrib"}  # Aladhan dropped one
    plan = dict(sp.plan_reminders(partial, now, {}))
    assert "Asr" not in plan                          # Asr's window end (Maghrib) is gone → skipped
    assert "Zohar" in plan and "Isha" in plan         # unaffected prayers survive


def test_all_timings_garbage_plans_nothing():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    plan = sp.plan_reminders({}, now, {})             # e.g. polar city / malformed response
    assert plan == []                                  # empty plan → main() then exits non-zero (alerts you)


def test_reminder_dt_before_end_and_after_start():
    now = datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    assert sp.reminder_dt("Asr", TIMINGS, now, {"Asr": {"before_end": 30}}) == datetime(2026, 11, 16, 17, 0, tzinfo=TZ)   # Maghrib 17:30 − 30
    assert sp.reminder_dt("Isha", TIMINGS, now, {"Isha": {"after_start": 60}}) == datetime(2026, 11, 16, 20, 0, tzinfo=TZ)  # Isha 19:00 + 60


def test_due_only_inside_the_window():
    r = datetime(2026, 11, 16, 17, 0, tzinfo=TZ)
    assert sp.due(r, datetime(2026, 11, 16, 17, 0, tzinfo=TZ)) is True     # exactly due
    assert sp.due(r, datetime(2026, 11, 16, 17, 15, tzinfo=TZ)) is True    # within 20-min window
    assert sp.due(r, datetime(2026, 11, 16, 17, 25, tzinfo=TZ)) is False   # window missed
    assert sp.due(r, datetime(2026, 11, 16, 16, 55, tzinfo=TZ)) is False   # not yet


def test_already_sent_matches_by_title(monkeypatch):
    now = datetime(2026, 11, 16, 17, 0, tzinfo=TZ)
    feed = '{"event":"message","title":"Asr","message":"x"}\n{"event":"open"}\n{"event":"message","title":"Fajr","message":"y"}'
    monkeypatch.setattr(sp.net, "request", lambda url, **kw: feed.encode())
    assert sp.already_sent("topic", "Asr", now) is True        # found in today's cache
    assert sp.already_sent("topic", "Maghrib", now) is False   # not sent yet
