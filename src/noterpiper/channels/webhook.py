"""Generic webhook channel — POST each notification as JSON to a URL.

One channel for everything that accepts an HTTP POST: Discord, Slack, Microsoft
Teams, Google Chat, Home Assistant, IFTTT, Zapier, or your own endpoint. Point it at
the destination with the WEBHOOK_URL setting.

The payload carries the notification's structured fields plus the same human line
under both `text` (Slack and most) and `content` (Discord), so those services render
it directly and custom endpoints still get the full structure.

Dedup: a plain webhook has no message cache to poll (unlike ntfy), so under the
per-channel best-effort policy it does not de-duplicate — `already_sent` is always
False, and the engine delivers whenever the source reports a notification due. Keep
the source's window tight if repeats would matter, or pair it with ntfy as primary.
"""
from __future__ import annotations

import json
from datetime import datetime

from .. import net
from ..engine import Notification


class WebhookChannel:
    def __init__(self, url: str):
        self.url = url

    def send(self, notification: Notification) -> None:
        text = f"{notification.title}\n{notification.body}"
        payload = json.dumps({
            "text": text,          # Slack, Mattermost, Google Chat, many others
            "content": text,       # Discord
            "title": notification.title,
            "body": notification.body,
            "priority": notification.priority,
            "tags": list(notification.tags),
        }).encode("utf-8")
        net.request(self.url, data=payload, headers={"Content-Type": "application/json"})

    def already_sent(self, dedup_key: str, now: datetime) -> bool:
        return False               # no serverless cache for a plain webhook
