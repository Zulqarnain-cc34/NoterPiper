"""DateRemindersSource — birthdays / bills / expiries from a list, pure date math."""
from datetime import datetime, timedelta, timezone

from noterpiper.engine import Source
from noterpiper.plugins.dates import DateRemindersSource, next_occurrence

TZ = timezone(timedelta(hours=5))
AT = datetime(2026, 11, 17, 9, 2, tzinfo=TZ)        # within the 09:00 window
BEFORE = datetime(2026, 11, 17, 7, 0, tzinfo=TZ)


def _cfg(items, **over):
    return {"enabled": True, "time": "09:00", "window": 5, "lead_days": 3, "items": items, **over}


def test_satisfies_the_Source_contract():
    assert isinstance(DateRemindersSource(), Source)
    assert DateRemindersSource().id == "dates"


def test_reminds_for_a_one_off_within_lead():
    n = DateRemindersSource().check(AT, _cfg([{"label": "Electricity bill", "date": "2026-11-19"}]))
    assert len(n) == 1
    assert n[0].title == "Electricity bill" and n[0].body == "in 2 days"


def test_says_today_on_the_day():
    n = DateRemindersSource().check(AT, _cfg([{"label": "Rent", "date": "2026-11-17"}]))
    assert n[0].body == "today"


def test_recurring_mm_dd_birthday():
    n = DateRemindersSource().check(AT, _cfg([{"label": "Mom's birthday", "date": "11-18"}]))
    assert n and n[0].body == "in 1 day"


def test_past_one_off_is_dropped():
    assert DateRemindersSource().check(AT, _cfg([{"label": "Old bill", "date": "2026-11-10"}])) == []


def test_beyond_lead_is_not_yet_reminded():
    assert DateRemindersSource().check(AT, _cfg([{"label": "Eid", "date": "2026-12-25"}])) == []


def test_disabled_sends_nothing():
    assert DateRemindersSource().check(AT, _cfg([{"label": "X", "date": "2026-11-17"}], enabled=False)) == []


def test_not_at_the_set_time_sends_nothing():
    assert DateRemindersSource().check(BEFORE, _cfg([{"label": "X", "date": "2026-11-17"}])) == []


def test_force_bypasses_enabled_and_time():
    cfg = _cfg([{"label": "Visa", "date": "2026-11-18"}], enabled=False, force=True)
    n = DateRemindersSource().check(BEFORE, cfg)
    assert n and n[0].title == "Visa"


def test_lead_days_is_configurable():
    far = _cfg([{"label": "Trip", "date": "2026-11-25"}], lead_days=10)
    assert DateRemindersSource().check(AT, far)[0].body == "in 8 days"


def test_junk_and_unlabeled_items_are_skipped():
    items = [{"label": "", "date": "2026-11-17"}, {"date": "2026-11-17"}, {"label": "Ok", "date": "nope"}]
    assert DateRemindersSource().check(AT, _cfg(items)) == []


def test_next_occurrence_rolls_a_passed_birthday_to_next_year():
    today = datetime(2026, 11, 17).date()
    assert next_occurrence("01-05", today).year == 2027     # Jan already passed this year
    assert next_occurrence("12-25", today).year == 2026     # still ahead


def test_title_is_header_safe():
    DateRemindersSource().check(AT, _cfg([{"label": "Bill", "date": "2026-11-17"}]))[0].title.encode("latin-1")
