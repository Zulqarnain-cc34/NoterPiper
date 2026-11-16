"""Locks the nightly-nudge gating: on/off flag + fire only at the set time (offline)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import notify  # noqa: E402
from muezzin import settings  # noqa: E402

TZ = timezone(timedelta(hours=5))


def test_due_now_true_at_the_mark():
    assert notify.due_now(datetime(2026, 11, 16, 21, 30, tzinfo=TZ), "21:30", 30) is True


def test_due_now_true_within_window():
    assert notify.due_now(datetime(2026, 11, 16, 21, 45, tzinfo=TZ), "21:30", 30) is True


def test_due_now_false_outside_window():
    assert notify.due_now(datetime(2026, 11, 16, 20, 0, tzinfo=TZ), "21:30", 30) is False


def _settings(**kw):
    base = dict(city="Istanbul", country="Turkey", method="4",
                reminders=settings.DEFAULT_REMINDERS, nudge_time="21:30",
                nudge_enabled=True, timezone="Europe/Istanbul")
    base.update(kw)
    return settings.Settings(**base)


def _stub(monkeypatch, *, enabled=True, tz="Europe/Istanbul", event="schedule"):
    """Isolate notify from the network/.env and record whether Habitica was hit."""
    seen = {"fetched": False}

    def fake_fetch():
        seen["fetched"] = True
        return {"dailys": [], "todos": [], "habits": [], "rewards": []}

    monkeypatch.setattr(notify.api, "configured", lambda: True)
    monkeypatch.setattr(notify.api, "fetch_tasks_by_type", fake_fetch)
    monkeypatch.setattr(notify.settings, "load_settings",
                        lambda: _settings(nudge_enabled=enabled, timezone=tz))
    monkeypatch.setattr(notify.config, "ENV_FILE", Path("/nonexistent/.env"))
    monkeypatch.delenv("NTFY_TOPIC", raising=False)          # no topic → dry run, no real send
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    return seen


def test_disabled_nudge_sends_nothing(monkeypatch):
    seen = _stub(monkeypatch, enabled=False)
    assert notify.main() == 0
    assert seen["fetched"] is False


def test_bad_timezone_does_not_crash(monkeypatch):
    seen = _stub(monkeypatch, tz="Not/AZone")
    assert notify.main() == 0
    assert seen["fetched"] is False


def test_manual_dispatch_sends_even_when_disabled(monkeypatch):
    # the on-demand "send now" button must work as an alive-test even if the
    # nightly nudge is toggled off.
    seen = _stub(monkeypatch, enabled=False, event="workflow_dispatch")
    assert notify.main() == 0
    assert seen["fetched"] is True


def test_collect_extracts_prayers_and_due_dailies():
    tasks = {
        "habits": [{"text": "Zohar", "counterUp": 0, "counterDown": 0},
                   {"text": "Asr", "counterUp": 1, "counterDown": 0}],   # Asr logged
        "dailys": [{"text": "Mulk", "isDue": True, "completed": False, "streak": 52},
                   {"text": "Done", "isDue": True, "completed": True, "streak": 5}],
        "todos": [], "rewards": [],
    }
    prayers, dailies = notify.collect(tasks)
    assert prayers == ["Zohar"]
    assert dailies == [("Mulk", 52)]


def test_build_message_dedups_and_groups():
    title, body, prio, tags = notify.build_message(
        ["Zohar", "Asr", "Maghrib", "Isha"],
        [("Surah Mulk", 52), ("Tasbeeh Fatima", 52), ("Morning walk", 3)])
    assert title == "7 left before midnight"
    assert "Zohar, Asr, Maghrib, Isha" in body
    assert body.count("Surah Mulk") == 1                 # listed once, not in two sections
    assert "Surah Mulk · 52 🔥" in body                  # at risk → name · streak, flame trailing
    assert "Morning walk" in body and "Morning walk 🔥" not in body   # not at risk → plain name
    assert "• " not in body and "* " not in body         # no mismatched leading markers
    assert prio == "high" and tags == "warning"


def test_build_message_all_done():
    title, body, prio, tags = notify.build_message([], [])
    assert title == "All done today" and prio == "low"


def test_build_message_no_urgent_is_default():
    title, body, prio, tags = notify.build_message(["Fajr"], [("Walk", 2)])
    assert prio == "default" and "🔥" not in body
