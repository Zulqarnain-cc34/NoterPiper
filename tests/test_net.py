"""net.request retry policy — especially honoring a 429's Retry-After.

A 429 is a 4xx, but unlike other client errors it is transient and the server
tells us when to come back. It must be retried (respecting Retry-After), not
raised like a 404. Habitica's 30-req/min limit is the real-world case.
"""

import sys
import urllib.error
from email.message import Message
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noterpiper import net


class _Resp:
    def __init__(self, body: bytes):
        self._b = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._b


def _http_error(code: int, retry_after=None) -> urllib.error.HTTPError:
    hdrs = Message()
    if retry_after is not None:
        hdrs["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("https://x.test", code, "err", hdrs, None)


def test_retries_on_429_and_honors_retry_after(monkeypatch):
    calls = {"n": 0}
    slept: list[float] = []

    def urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(429, retry_after=2)
        return _Resp(b"ok")

    monkeypatch.setattr(net.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(net.time, "sleep", lambda s: slept.append(s))
    assert net.request("https://x.test") == b"ok"
    assert calls["n"] == 2  # retried after the 429 instead of raising
    assert slept == [2]  # waited exactly Retry-After, not the exponential backoff


def test_429_without_retry_after_falls_back_to_backoff(monkeypatch):
    calls = {"n": 0}
    slept: list[float] = []

    def urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(429)  # no Retry-After header
        return _Resp(b"ok")

    monkeypatch.setattr(net.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(net.time, "sleep", lambda s: slept.append(s))
    assert net.request("https://x.test", backoff=1.5) == b"ok"
    assert slept == [1.5]  # backoff ** (attempt + 1) == 1.5 ** 1


def test_retry_after_is_capped(monkeypatch):
    calls = {"n": 0}
    slept: list[float] = []

    def urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(429, retry_after=9999)
        return _Resp(b"ok")

    monkeypatch.setattr(net.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(net.time, "sleep", lambda s: slept.append(s))
    net.request("https://x.test")
    assert slept == [net.RETRY_AFTER_CAP]  # capped so a run never hangs on a long wait


def test_other_4xx_raises_immediately(monkeypatch):
    calls = {"n": 0}

    def urlopen(req, timeout=None):
        calls["n"] += 1
        raise _http_error(404)

    monkeypatch.setattr(net.urllib.request, "urlopen", urlopen)
    with pytest.raises(urllib.error.HTTPError) as ei:
        net.request("https://x.test")
    assert ei.value.code == 404
    assert calls["n"] == 1  # a real client error is not retried
