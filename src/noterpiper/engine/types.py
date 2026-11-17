"""The value object every layer speaks: an immutable Notification.

Sources produce Notifications; the engine routes them; a channel delivers them.
It is frozen so it can't be mutated in transit between those layers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Notification:
    """One thing to push to the user.

    title / body        what the user sees.
    priority            ntfy priority: min | low | default | high | max | urgent.
    tags                ntfy tags (emoji/icons), e.g. ("mosque",).
    dedup_key           when set, the channel delivers it at most once (per key),
                        so repeated engine runs inside a window don't re-send.
    """

    title: str
    body: str
    priority: str = "default"
    tags: tuple[str, ...] = ()
    dedup_key: str | None = None
