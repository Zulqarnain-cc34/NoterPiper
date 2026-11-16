"""The delivery contract: a Channel sends notifications and remembers what it sent.

One concrete channel ships today (ntfy). The engine depends only on this interface,
so a second channel (email, Telegram, …) could be added later without touching it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from .types import Notification


@runtime_checkable
class Channel(Protocol):
    """How notifications reach the user."""

    def send(self, notification: Notification) -> None:
        ...

    def already_sent(self, dedup_key: str, now: datetime) -> bool:
        """True if a notification with this dedup key already went out *today*, so the
        engine can enforce 'send at most once per day'. `now` is the timezone-aware
        current time, used to scope what 'today' means."""
        ...
