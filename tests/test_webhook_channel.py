"""Multi-channel Phase 3 — WebhookChannel: POST a notification to any URL.

Covers every "POST to a webhook" service at once (Discord, Slack, Teams, Home
Assistant, IFTTT, Zapier, a custom endpoint). The payload carries both a human
text/content line and the structured fields, so chat services render it directly."""
import json
from datetime import datetime, timedelta, timezone

from noterpiper.channels.webhook import WebhookChannel
from noterpiper.engine import Channel, Notification

TZ = timezone(timedelta(hours=5))


def test_webhookchannel_satisfies_the_Channel_contract():
    assert isinstance(WebhookChannel("https://hook.test/x"), Channel)


def test_send_posts_the_notification_as_json(monkeypatch):
    seen = {}
    def fake(url, *, data=None, headers=None, **kw):
        seen.update(url=url, data=data, headers=headers)
        return b""
    monkeypatch.setattr("noterpiper.channels.webhook.net.request", fake)

    WebhookChannel("https://hook.test/x").send(
        Notification("Maghrib", "Time to pray", priority="max", tags=("mosque",)))

    assert seen["url"] == "https://hook.test/x"
    assert seen["headers"]["Content-Type"] == "application/json"
    payload = json.loads(seen["data"])
    assert payload["title"] == "Maghrib"
    assert payload["body"] == "Time to pray"
    assert payload["priority"] == "max"
    assert payload["tags"] == ["mosque"]
    # same human line under both keys so Slack ('text') and Discord ('content') render it
    assert "Maghrib" in payload["text"] and payload["content"] == payload["text"]


def test_already_sent_is_false_because_a_webhook_has_no_cache():
    # per-channel best-effort: a plain webhook can't check 'sent today', so it never
    # claims it has (the engine will deliver whenever the source says a notice is due).
    assert WebhookChannel("x").already_sent("k", datetime.now(TZ)) is False
