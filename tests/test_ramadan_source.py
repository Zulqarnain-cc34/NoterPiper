"""RamadanSource — suhoor & iftar reminders during Ramadan.

Fires two reminders a day (suhoor before Fajr, iftar at Maghrib), gated to the Hijri
month of Ramadan — unless forced by the config page's 'send now' test, which previews
today's times any time of year. Aladhan is mocked; `now` is engine-supplied."""
from datetime import datetime, timedelta, timezone

from noterpiper.engine import Source
from noterpiper.plugins.ramadan import RamadanSource

TZ = timezone(timedelta(hours=5))
TIMINGS = {"Fajr": "05:12", "Dhuhr": "12:00", "Asr": "15:30", "Maghrib": "18:45", "Isha": "20:00"}
RAMADAN_DAY = {"timings": TIMINGS, "hijri_month": 9}
NORMAL_DAY = {"timings": TIMINGS, "hijri_month": 3}
CONFIG = {"city": "Makkah", "country": "Saudi Arabia", "method": "4",
          "enabled": True, "suhoor_lead": 45, "iftar_lead": 0, "window": 10}


def _ready(monkeypatch, day=RAMADAN_DAY):
    monkeypatch.setattr("noterpiper.plugins.ramadan.fetch_day", lambda c, co, m: day)


def test_satisfies_the_Source_contract():
    assert isinstance(RamadanSource(), Source)
    assert RamadanSource().id == "ramadan"


def test_silent_outside_ramadan(monkeypatch):
    _ready(monkeypatch, NORMAL_DAY)
    now = datetime(2026, 2, 20, 4, 30, tzinfo=TZ)        # would be suhoor time, but not Ramadan
    assert RamadanSource().check(now, CONFIG) == []


def test_suhoor_fires_before_fajr_in_ramadan(monkeypatch):
    _ready(monkeypatch)
    now = datetime(2026, 3, 20, 4, 30, tzinfo=TZ)        # Fajr 05:12, lead 45 → remind 04:27; 04:30 is in-window
    notes = RamadanSource().check(now, CONFIG)
    assert len(notes) == 1
    assert "Suhoor" in notes[0].title
    assert "5:12" in notes[0].body                       # shows the Fajr deadline
    assert notes[0].dedup_key == "suhoor"


def test_iftar_fires_at_maghrib_in_ramadan(monkeypatch):
    _ready(monkeypatch)
    now = datetime(2026, 3, 20, 18, 47, tzinfo=TZ)       # Maghrib 18:45, lead 0 → remind 18:45; 18:47 in-window
    notes = RamadanSource().check(now, CONFIG)
    assert len(notes) == 1
    assert "Iftar" in notes[0].title
    assert "6:45" in notes[0].body
    assert notes[0].dedup_key == "iftar"


def test_nothing_due_between_the_two_times(monkeypatch):
    _ready(monkeypatch)
    now = datetime(2026, 3, 20, 12, 0, tzinfo=TZ)        # midday — neither suhoor nor iftar
    assert RamadanSource().check(now, CONFIG) == []


def test_disabled_sends_nothing(monkeypatch):
    _ready(monkeypatch)
    now = datetime(2026, 3, 20, 18, 47, tzinfo=TZ)
    assert RamadanSource().check(now, {**CONFIG, "enabled": False}) == []


def test_titles_are_header_safe(monkeypatch):
    # ntfy puts the title in an HTTP header (latin-1 only); an emoji there makes send()
    # raise and the engine silently drops the notification — so titles must be ASCII.
    _ready(monkeypatch)
    at = [datetime(2026, 3, 20, 4, 30, tzinfo=TZ),      # suhoor
          datetime(2026, 3, 20, 18, 47, tzinfo=TZ)]     # iftar
    notes = [n for t in at for n in RamadanSource().check(t, CONFIG)]
    notes += RamadanSource().check(datetime(2026, 3, 20, 12, 0, tzinfo=TZ), {**CONFIG, "force": True})
    assert len(notes) == 3
    for n in notes:
        n.title.encode("latin-1")                       # must not raise (header-safe)


def test_force_previews_todays_times_any_month(monkeypatch):
    _ready(monkeypatch, NORMAL_DAY)                      # not Ramadan, nudge disabled, midday
    now = datetime(2026, 2, 20, 12, 0, tzinfo=TZ)
    notes = RamadanSource().check(now, {**CONFIG, "enabled": False, "force": True})
    assert len(notes) == 1
    assert "5:12" in notes[0].body and "6:45" in notes[0].body   # both of today's times previewed
    assert notes[0].dedup_key is None                    # forced → always delivers
