"""Phase 3 — the Engine: orchestrates sources + a channel.

The engine knows nothing about prayers or Habitica — only the Source and Channel
contracts. Driven here with fakes so the loop's behavior is pinned exactly."""
from datetime import datetime, timedelta, timezone

from muezzin.engine import Notification
from muezzin.engine.engine import Engine

TZ = timezone(timedelta(hours=5))
NOW = datetime(2026, 11, 16, 17, 30, tzinfo=TZ)


class FakeChannel:
    def __init__(self, already=()):
        self.sent = []
        self._already = set(already)

    def send(self, n):
        self.sent.append(n)

    def already_sent(self, dedup_key, now):
        return dedup_key in self._already


class StubSource:
    def __init__(self, id, notifications, *, seen_config=None, boom=False):
        self.id = id
        self._notes = notifications
        self._seen_config = seen_config
        self._boom = boom

    def check(self, now, config):
        if self._seen_config is not None:
            self._seen_config.append(config)
        if self._boom:
            raise RuntimeError("source exploded")
        return self._notes


def test_engine_delivers_every_sources_notifications():
    ch = FakeChannel()
    sources = [StubSource("a", [Notification("A1", "x")]),
               StubSource("b", [Notification("B1", "y"), Notification("B2", "z")])]
    sent = Engine(ch, sources).run(NOW, {})
    assert sent == 3
    assert [n.title for n in ch.sent] == ["A1", "B1", "B2"]


def test_engine_skips_a_dedup_key_already_sent_today():
    ch = FakeChannel(already={"prayer:Maghrib"})
    src = StubSource("prayer", [Notification("Maghrib", "x", dedup_key="prayer:Maghrib")])
    sent = Engine(ch, [src]).run(NOW, {})
    assert sent == 0
    assert ch.sent == []


def test_engine_always_sends_when_there_is_no_dedup_key():
    ch = FakeChannel(already={"anything"})
    src = StubSource("x", [Notification("Hi", "there")])     # dedup_key is None
    sent = Engine(ch, [src]).run(NOW, {})
    assert sent == 1


def test_engine_hands_each_source_its_own_config_slice():
    seen = []
    src = StubSource("prayer", [], seen_config=seen)
    config = {"prayer": {"city": "Makkah"}, "habitica": {"nudge_time": "21:30"}}
    Engine(FakeChannel(), [src]).run(NOW, config)
    assert seen == [{"city": "Makkah"}]        # only prayer's slice, not the whole thing


def test_engine_isolates_a_failing_source():
    ch = FakeChannel()
    sources = [StubSource("bad", [], boom=True),
               StubSource("good", [Notification("G", "ok")])]
    sent = Engine(ch, sources).run(NOW, {})     # bad source must not stop good source
    assert sent == 1
    assert [n.title for n in ch.sent] == ["G"]
