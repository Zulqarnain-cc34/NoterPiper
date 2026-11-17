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
RETRY_AFTER_CAP = 60  # seconds — honor a 429's Retry-After, but never hang a run longer than this


def _retry_after(err: urllib.error.HTTPError, fallback: float) -> float:
    """Seconds to wait after a 429, from its Retry-After header (seconds form,
    clamped to [0, RETRY_AFTER_CAP]); `fallback` if it's absent or an HTTP-date."""
    raw = err.headers.get("Retry-After") if err.headers else None
    try:
        return min(max(int(raw), 0), RETRY_AFTER_CAP)
    except (TypeError, ValueError):
        return fallback


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
            # 429 is a 4xx but transient — the server says come back; honor Retry-After.
            if e.code == 429:
                last = e
                if attempt < retries - 1:
                    time.sleep(_retry_after(e, backoff ** (attempt + 1)))
                continue
            # other 4xx are our fault (bad token/topic) — don't retry; 5xx are transient.
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
