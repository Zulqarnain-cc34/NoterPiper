"""Example test — copy this pattern to test your own Source.

(Lives under examples/, so it's not part of NoterPiper's own suite; run it in your repo.)"""

from datetime import datetime, timedelta, timezone

from noterpiper.engine import Source  # path set up by conftest.py
from plugin_template import ExampleSource

TZ = timezone(timedelta(hours=0))
CONFIG = {"enabled": True, "time": "09:00", "message": "hi"}


def test_satisfies_the_source_contract():
    assert isinstance(ExampleSource(), Source)
    assert ExampleSource().id == "example"


def test_fires_when_enabled_and_due():
    notes = ExampleSource().check(datetime(2026, 1, 1, 9, 2, tzinfo=TZ), CONFIG)
    assert len(notes) == 1 and notes[0].body == "hi"


def test_silent_when_disabled():
    assert (
        ExampleSource().check(datetime(2026, 1, 1, 9, 2, tzinfo=TZ), {**CONFIG, "enabled": False})
        == []
    )


def test_silent_outside_the_window():
    assert ExampleSource().check(datetime(2026, 1, 1, 12, 0, tzinfo=TZ), CONFIG) == []
