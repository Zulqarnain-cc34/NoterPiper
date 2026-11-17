"""The delivery contract: a Channel sends notifications and remembers what it sent.

Two concrete channels ship today (ntfy, webhook). The engine depends only on this
interface, so further channels (email, Telegram, …) can be added without touching it.

Dedup contract: `already_sent` answers "did a push for this key already go out
today?". How a channel matches the key is its own business — NtfyChannel matches it
against the delivered (latin-1-safe) title, so sources should keep title == dedup_key.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from .types import Notification


@runtime_checkable
class Channel(Protocol):
    """How notifications reach the user."""

    def send(self, notification: Notification) -> None: ...

    def already_sent(self, dedup_key: str, now: datetime) -> bool:
        """True if a notification with this dedup key already went out *today*, so the
        engine can enforce 'send at most once per day'. `now` is the timezone-aware
        current time, used to scope what 'today' means."""
        ...
