"""Phase 2 — NtfyChannel: the one concrete delivery channel.

It satisfies the Channel contract, delivers a Notification's fields as the right ntfy
headers/body, and uses ntfy's own recent-message cache as the 'already sent today'
store (no database needed on a stateless, serverless run)."""

import json
from datetime import datetime, timedelta, timezone

from noterpiper.channels.ntfy import NtfyChannel
from noterpiper.engine import Channel, Notification

TZ = timezone(timedelta(hours=5))


def test_ntfychannel_satisfies_the_Channel_contract():
    assert isinstance(NtfyChannel("topic"), Channel)


def test_send_maps_fields_to_ntfy_headers_and_body(monkeypatch):
    seen = {}

    def fake_request(url, *, data=None, headers=None, **kw):
        seen.update(url=url, data=data, headers=headers)
        return b""

    monkeypatch.setattr("noterpiper.channels.ntfy.net.request", fake_request)

    NtfyChannel("my-topic").send(
        Notification("Maghrib", "Time to pray", priority="max", tags=("mosque",))
    )

    assert seen["url"] == "https://ntfy.sh/my-topic"
    assert seen["data"] == b"Time to pray"
    assert seen["headers"]["Title"] == "Maghrib"
    assert seen["headers"]["Priority"] == "max"
    assert seen["headers"]["Tags"] == "mosque"


def test_send_omits_tags_header_when_there_are_none(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "noterpiper.channels.ntfy.net.request",
        lambda url, **kw: seen.update(headers=kw.get("headers")) or b"",
    )
    NtfyChannel("t").send(Notification("Hi", "there"))
    assert "Tags" not in seen["headers"]


def test_send_strips_non_latin1_title_so_delivery_never_fails(monkeypatch):
    # HTTP headers are latin-1; an emoji in a Title would raise and silently drop the
    # push. The channel must degrade (keep the text, drop the char) and still deliver.
    seen = {}
    monkeypatch.setattr(
        "noterpiper.channels.ntfy.net.request",
        lambda url, **kw: seen.update(headers=kw.get("headers")) or b"",
    )
    NtfyChannel("t").send(Notification("🌙 Suhoor", "eat up", tags=("crescent_moon",)))
    seen["headers"]["Title"].encode("latin-1")  # header-safe → no raise
    assert seen["headers"]["Title"] == "Suhoor"  # emoji dropped, text kept (emoji is in Tags)


def test_already_sent_true_when_title_is_in_todays_cache(monkeypatch):
    now = datetime(2026, 11, 16, 17, 30, tzinfo=TZ)
    cache = (
        "\n".join(
            [
                json.dumps({"event": "message", "title": "Maghrib", "message": "x"}),
                json.dumps({"event": "message", "title": "Asr", "message": "y"}),
            ]
        )
    ).encode()
    monkeypatch.setattr("noterpiper.channels.ntfy.net.request", lambda url, **kw: cache)
    ch = NtfyChannel("t")
    assert ch.already_sent("Maghrib", now) is True
    assert ch.already_sent("Isha", now) is False


def test_already_sent_polls_since_local_midnight(monkeypatch):
    now = datetime(2026, 11, 16, 17, 30, tzinfo=TZ)
    midnight = int(datetime(2026, 11, 16, 0, 0, tzinfo=TZ).timestamp())
    seen = {}
    monkeypatch.setattr(
        "noterpiper.channels.ntfy.net.request", lambda url, **kw: seen.update(url=url) or b""
    )
    NtfyChannel("t").already_sent("Maghrib", now)
    assert f"since={midnight}" in seen["url"]


def test_already_sent_returns_false_if_the_poll_fails(monkeypatch):
    now = datetime(2026, 11, 16, 17, 30, tzinfo=TZ)

    def boom(url, **kw):
        raise RuntimeError("ntfy unreachable")

    monkeypatch.setattr("noterpiper.channels.ntfy.net.request", boom)
    # can't verify → don't block the send
    assert NtfyChannel("t").already_sent("Maghrib", now) is False
