"""The plugin contract: a Source decides *what* to notify and *when*.

Adding a new reminder type (prayer, gym, anything) is exactly: write one class that
satisfies this protocol, and register it. Nothing in the engine changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from .types import Notification


@runtime_checkable
class Source(Protocol):
    """A notification source (a plugin).

    id      a short, stable name ("prayer", "habitica", "gym"). Also the key for
            this source's slice of config.
    check   given the current time and this source's own config, return the
            notifications due right now (an empty list means nothing is due).
    """

    id: str

    def check(self, now: datetime, config: dict) -> list[Notification]: ...
