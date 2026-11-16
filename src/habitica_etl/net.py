"""Resilient HTTP — the single network layer everything else uses.

Every external call (Habitica, Aladhan, ntfy) goes through here, so transient
failures (timeouts, blips, 5xx) are retried with backoff instead of crashing a
run. Standard library only — no dependency to rot over 5 years.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

RETRYABLE = (urllib.error.URLError, TimeoutError, OSError)


def request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
    timeout: int = 20,
    retries: int = 4,
    backoff: float = 1.5,
) -> bytes:
    """GET/POST with retries + exponential backoff. Raises the last error if all
    attempts fail (callers decide whether that's fatal)."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # 4xx are our fault (bad token/topic) — don't retry; 5xx are transient.
            if e.code < 500:
                raise
            last = e
        except RETRYABLE as e:
            last = e
        if attempt < retries - 1:
            time.sleep(backoff ** (attempt + 1))
    assert last is not None
    raise last


def get_json(url: str, **kw: Any) -> Any:
    return json.loads(request(url, **kw))
