"""Unit tests for the pure transformation functions — the analytical core."""
from datetime import datetime, timezone

import pytest

from habitica_etl import config, transform


# --- timestamp handling ------------------------------------------------------
def test_epoch_ms_to_utc_matches_known_point():
    # epoch 1771483887882 ms == 2026-02-19 06:51:27.882 UTC (verified vs CSV)
    dt = transform.epoch_ms_to_utc(1771483887882)
    assert dt.tzinfo == timezone.utc
    assert dt.strftime("%Y-%m-%d %H:%M:%S") == "2026-02-19 06:51:27"


def test_csv_string_is_naive_utc_equals_epoch():
    csv_dt = transform.parse_csv_naive_utc("2026-02-19 06:51:27")
    epoch_dt = transform.epoch_ms_to_utc(1771483887882).replace(microsecond=0)
    assert csv_dt == epoch_dt


def test_to_pkt_is_plus_five():
    dt = datetime(2026, 2, 19, 6, 51, 27, tzinfo=timezone.utc)
    pkt = transform.to_pkt(dt)
    assert pkt.utcoffset().total_seconds() == 5 * 3600
    assert pkt.hour == 11  # 06:51 UTC -> 11:51 PKT


def test_local_date_crosses_midnight_boundary():
    # 21:00 UTC == 02:00 PKT next day -> local date advances
    dt = datetime(2026, 9, 5, 21, 0, 0, tzinfo=timezone.utc)
    assert transform.local_date_str(dt) == "2026-09-06"


# --- deterministic ids -------------------------------------------------------
def test_daily_event_id_is_deterministic_and_ms_stable():
    a = transform.daily_event_id("task-1", 1771483887882)
    b = transform.daily_event_id("task-1", 1771483887882.0)
    assert a == b
    assert a != transform.daily_event_id("task-1", 1771483887883)
    assert a != transform.daily_event_id("task-2", 1771483887882)


# --- value-delta completion decode ------------------------------------------
def test_classify_completed_missed_and_flat():
    hist = [
        {"date": 10, "value": 1.0},    # 0 -> 1.0  : completed
        {"date": 20, "value": 0.5},    # 1.0 -> .5 : missed
        {"date": 30, "value": 0.5},    # flat      : undetermined
        {"date": 40, "value": 2.0},    # .5 -> 2.0 : completed
    ]
    ev = transform.classify_daily_history(hist)
    assert [e["observed_action"] for e in ev] == [
        config.ACTION_COMPLETED, config.ACTION_MISSED,
        config.ACTION_UNDETERMINED, config.ACTION_COMPLETED,
    ]
    assert ev[2]["confidence"] == "low"


def test_classify_first_entry_uses_zero_baseline():
    # A single negative first entry means the first processed day was a miss.
    ev = transform.classify_daily_history([{"date": 1, "value": -0.49}])
    assert ev[0]["observed_action"] == config.ACTION_MISSED


def test_classify_sorts_unordered_history():
    hist = [{"date": 30, "value": 2.0}, {"date": 10, "value": 1.0}]
    ev = transform.classify_daily_history(hist)
    assert [e["epoch_ms"] for e in ev] == [10, 30]


# --- text & categorisation ---------------------------------------------------
def test_normalize_text_preserves_content_collapses_space():
    assert transform.normalize_text("  Surah   Mulk ") == "Surah Mulk"
    assert transform.normalize_text(None) == ""


@pytest.mark.parametrize("text,expected", [
    ("Surah Mulk", "Quran recitation"),
    ("#### Namaz and Jammat", "Salah / Namaz"),
    ("Qaza 2 fajar", "Salah / Namaz"),
    ("Sadaqa", "Charity / Sadaqa"),
    ("Poem #1", "Poetry memorisation"),
    ("11 Times Muhammad", "Darood / Salawat"),
])
def test_classify_category_rules(text, expected):
    assert transform.classify_category(text)["category"] == expected


def test_classify_category_fallback_low_confidence():
    r = transform.classify_category("zzzz random", None)
    assert r["category"] == "Uncategorised"
    assert r["confidence"] == "low"
