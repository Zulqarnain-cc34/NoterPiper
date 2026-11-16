"""Phase 1 — the engine's core contracts: Notification, Source, Channel.

These are the entire public surface a plugin author touches. The value object must
be immutable (so it can't be mutated mid-flight), and the two protocols must be
runtime-checkable (so the engine can reason about conformance)."""
import dataclasses
from datetime import datetime

import pytest

from noterpiper.engine import Channel, Notification, Source


def test_notification_requires_title_and_body():
    n = Notification(title="Fajr", body="Time to pray")
    assert n.title == "Fajr"
    assert n.body == "Time to pray"


def test_notification_has_sensible_defaults():
    n = Notification("Fajr", "Time to pray")
    assert n.priority == "default"
    assert n.tags == ()
    assert n.dedup_key is None


def test_notification_carries_every_field():
    n = Notification("Maghrib", "ends 5:03 PM", priority="max",
                     tags=("mosque",), dedup_key="prayer:Maghrib:2026-11-16")
    assert n.priority == "max"
    assert n.tags == ("mosque",)
    assert n.dedup_key == "prayer:Maghrib:2026-11-16"


def test_notification_is_immutable():
    n = Notification("Fajr", "Time to pray")
    with pytest.raises(dataclasses.FrozenInstanceError):
        n.title = "Isha"          # a frozen value object: no mid-flight mutation


def test_a_class_with_id_and_check_is_a_Source():
    class Gym:
        id = "gym"
        def check(self, now: datetime, config: dict) -> list:
            return []
    assert isinstance(Gym(), Source)


def test_a_class_missing_the_contract_is_not_a_Source():
    class NotReally:
        pass
    assert not isinstance(NotReally(), Source)


def test_a_class_with_send_and_already_sent_is_a_Channel():
    class FakeNtfy:
        def send(self, notification) -> None: ...
        def already_sent(self, dedup_key) -> bool:
            return False
    assert isinstance(FakeNtfy(), Channel)


def test_a_half_channel_is_not_a_Channel():
    class Halfway:
        def send(self, notification) -> None: ...   # no already_sent
    assert not isinstance(Halfway(), Channel)
