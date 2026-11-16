"""The ntfy delivery channel — the one concrete Channel that ships today.

It delivers a Notification as an ntfy push, and uses ntfy's own recent-message cache
as the "already sent today" store — so dedup works with no database on a stateless,
serverless run. This consolidates what used to live twice (the prayer script's
`send_live` + `already_sent` and the nudge script's `send`).
"""
from __future__ import annotations

import json
from datetime import datetime

from .. import net
from ..engine import Notification

NTFY = "https://ntfy.sh"


class NtfyChannel:
    def __init__(self, topic: str):
        self.topic = topic

    def send(self, notification: Notification) -> None:
        headers = {"Title": notification.title, "Priority": notification.priority}
        if notification.tags:
            headers["Tags"] = ",".join(notification.tags)
        net.request(f"{NTFY}/{self.topic}",
                    data=notification.body.encode("utf-8"), headers=headers)

    def already_sent(self, dedup_key: str, now: datetime) -> bool:
        """True if a message whose title equals `dedup_key` already went out since
        local midnight, read back from ntfy's cache. On any poll failure, returns
        False — we'd rather risk a duplicate than silently drop a reminder."""
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since = int(midnight.timestamp())
        try:
            raw = net.request(f"{NTFY}/{self.topic}/json?poll=1&since={since}").decode()
        except Exception:
            return False
        for line in raw.splitlines():
            if not line.strip():
                continue
            msg = json.loads(line)
            if msg.get("event") == "message" and msg.get("title") == dedup_key:
                return True
        return False
