"""Pure, deterministic transformation functions.

Every function here is small, side-effect free, and unit-testable. These encode
the project's analytical *interpretations* (timezone conversion, value-delta
decode, text categorisation) and are the place to audit how a raw export record
becomes an analytical fact.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Optional

from . import config


# --- Timestamps --------------------------------------------------------------
def epoch_ms_to_utc(ms: int | float) -> datetime:
    """Convert epoch milliseconds (UTC) to a tz-aware UTC datetime."""
    return datetime.fromtimestamp(ms / 1000.0, tz=config.UTC)


def parse_iso_utc(s: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 string (…Z) into a tz-aware UTC datetime, or None."""
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(config.UTC)


def parse_csv_naive_utc(s: str) -> datetime:
    """Parse a CSV 'YYYY-MM-DD HH:MM:SS' string, which is naive UTC, to aware UTC."""
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=config.UTC)


def to_pkt(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert any tz-aware datetime to Asia/Karachi (UTC+5)."""
    if dt is None:
        return None
    return dt.astimezone(config.ANALYSIS_TZ)


def local_date_str(dt: Optional[datetime]) -> Optional[str]:
    """Local (PKT) calendar date as 'YYYY-MM-DD' — the unit for daily metrics."""
    pkt = to_pkt(dt)
    return pkt.date().isoformat() if pkt else None


# --- Deterministic identities ------------------------------------------------
def daily_event_id(task_id: str, epoch_ms: int | float) -> str:
    """Stable event id from (task_id, exact timestamp) for idempotent ingest."""
    key = f"{task_id}|{int(round(float(epoch_ms)))}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


# --- Daily value-delta decode ------------------------------------------------
def classify_daily_history(
    history: list[dict[str, Any]],
    *,
    start_value: float = config.DAILY_START_VALUE,
    epsilon: float = config.VALUE_EPSILON,
) -> list[dict[str, Any]]:
    """Turn a daily's raw ``history`` into ordered, classified events.

    Rule: compare each entry's ``value`` to the previous entry (first entry is
    compared to ``start_value``=0). Positive delta -> completed; negative ->
    missed; |delta| <= epsilon -> UNDETERMINED (flat; not silently assigned).

    Returns a list (chronological) of dicts with keys:
    epoch_ms, value, value_delta, observed_action, confidence.
    """
    ordered = sorted(history, key=lambda e: e["date"])
    out: list[dict[str, Any]] = []
    prev = start_value
    for e in ordered:
        value = float(e["value"])
        delta = value - prev
        if delta > epsilon:
            action, conf = config.ACTION_COMPLETED, "high"
        elif delta < -epsilon:
            action, conf = config.ACTION_MISSED, "high"
        else:
            action, conf = config.ACTION_UNDETERMINED, "low"
        out.append(
            {
                "epoch_ms": int(e["date"]),
                "value": value,
                "value_delta": delta,
                "observed_action": action,
                "confidence": conf,
            }
        )
        prev = value
    return out


# --- Text normalisation & categorisation ------------------------------------
_WS = re.compile(r"\s+")


def normalize_text(text: Optional[str]) -> str:
    """Collapse whitespace and trim. Preserves original wording/characters.

    Used only for grouping/matching — the raw `text` is always stored verbatim.
    """
    if not text:
        return ""
    return _WS.sub(" ", text).strip()


# Rule-based categories tuned to THIS account's vocabulary (inspected from the
# data: the tasks are Islamic spiritual practices + Urdu poetry/reading).
# Each category is (label, keyword-regex). First match wins; order matters.
_CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("Salah / Namaz", re.compile(r"\b(namaz|salah|jammat|jamaat|fajar|fajr|qaza)\b", re.I)),
    ("Quran recitation", re.compile(r"\b(quran|qur'?an|surah|mulk|hakeem|القرآن|قرآن)\b", re.I)),
    ("Darood / Salawat", re.compile(r"\b(darood|durood|muhammad|salawat|صلى)\b", re.I)),
    ("Dhikr / Tasbeeh", re.compile(r"\b(tasbeeh|tasbih|darood|dhikr|zikr|times|لا\s*حول|حول)\b", re.I)),
    ("Charity / Sadaqa", re.compile(r"\b(sadaqa|sadaqah|charity|zakat)\b", re.I)),
    ("Poetry memorisation", re.compile(r"\b(poem|bang-?e-?dra|ghalib|deewan|diwan|qatra)\b", re.I)),
    ("Reading / Books", re.compile(r"\b(hadaiq|tazkira|hadiaq|bakshish|book|read|dotfiles|sakura)\b", re.I)),
]


def classify_category(text: Optional[str], notes: Optional[str] = None) -> dict[str, Any]:
    """Assign a coarse category by keyword rules. Returns label/confidence/method.

    There are NO user tags in this export, so categories are text-derived. This
    is intentionally simple and auditable; low confidence where nothing matches.
    """
    hay = f"{text or ''} {notes or ''}"
    for label, pattern in _CATEGORY_RULES:
        if pattern.search(hay):
            return {"category": label, "confidence": "medium", "method": "rule:keyword"}
    return {"category": "Uncategorised", "confidence": "low", "method": "rule:fallback"}


def decode_recurrence(task: dict[str, Any]) -> dict[str, Any]:
    """Summarise a daily's CURRENT recurrence config (snapshot, not historical).

    WARNING: the exported config is a present-day snapshot and does not
    reliably reconstruct historical cadence (e.g. a task marked 'yearly/Friday'
    has 51 history entries). Stored for reference; adherence denominators are
    taken from OBSERVED history entries, not from this config.
    """
    repeat = task.get("repeat", {}) or {}
    active_days = [d for d, on in repeat.items() if on]
    return {
        "frequency": task.get("frequency"),
        "every_x": task.get("everyX"),
        "active_weekdays": ",".join(active_days),
        "start_date": task.get("startDate"),
    }
