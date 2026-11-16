"""Central configuration and constants for the Habitica ETL pipeline.

Everything that is an analytical *choice* (timezone, classification epsilon,
file locations) lives here so it is explicit, documented, and testable.
"""
from __future__ import annotations

from datetime import timedelta, timezone
from pathlib import Path

# --- Paths -------------------------------------------------------------------
# Resolve project root as two levels up from this file: src/habitica_etl/ -> root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_JSON = DATA_DIR / "habitica-user-data.json"  # legacy export fallback
DB_PATH = PROJECT_ROOT / "database" / "habitica_productivity.db"

# --- Timezone ----------------------------------------------------------------
# Habitica stores all history dates in UTC (epoch ms in JSON; naive-UTC strings
# in the CSV export — verified: epoch 1771483887882 -> "2026-02-19 06:51:27").
# The account's preferences.timezoneOffset = -300 (JS getTimezoneOffset),
# i.e. UTC+5 = Asia/Karachi (Pakistan Standard Time), matching the user's
# stated analytical timezone. dayStart = 0 (calendar day boundary at midnight).
UTC = timezone.utc
ANALYSIS_TZ_NAME = "Asia/Karachi"
ANALYSIS_TZ = timezone(timedelta(hours=5))  # UTC+5, no DST in Pakistan
DAY_START_HOUR = 0  # Habitica preferences.dayStart

# --- Analysis window ---------------------------------------------------------
# The owner stopped using Habitica for ~months, then restarted. Per explicit
# instruction, the analysis is scoped to the restart onward: all daily history
# events with a LOCAL (PKT) date before ANALYSIS_START_DATE are excluded at
# ingest. (This drops a single lone 2026-02-19 event.) The raw exports are
# untouched; the database is the in-window clean store.
ANALYSIS_START_DATE = "2026-09-05"   # inclusive, PKT local date
ANALYSIS_END_DATE = "2026-11-15"     # inclusive, informational (last observed)

# --- Daily-event decode ------------------------------------------------------
# A daily's embedded history records the task's running `value` after each
# processed day. value rises on completion, falls on a miss. We classify the
# direction by the sign of the delta between consecutive entries (first entry is
# compared against a baseline of 0, the Habitica default starting value).
# |delta| <= VALUE_EPSILON is treated as UNDETERMINED (not silently assigned),
# because near the value asymptote (very negative/positive) a genuine
# completion or miss can round to no change, and some entries are flat for
# reasons the export does not disambiguate.
VALUE_EPSILON = 1e-6
DAILY_START_VALUE = 0.0

# Event-action vocabulary (stored in daily_events.observed_action)
ACTION_COMPLETED = "completed"
ACTION_MISSED = "missed"
ACTION_UNDETERMINED = "undetermined"

# Priority (Habitica "difficulty") labels, for readability only.
PRIORITY_LABELS = {0.1: "trivial", 1.0: "easy", 1.5: "medium", 2.0: "hard"}

# --- Project scope (locked 2026-11-16) --------------------------------------
# The project is exactly three sections. Prayers are new habits with no data yet,
# so analysis currently covers the recitations only. Tasks are matched by a
# substring of their text (handles the Arabic suffixes in the names).
DAILY_RECITATIONS = [
    "Surah Mulk", "500 ", "tasbeeh fatima", "11 Times Muhammad", "Quran Hakeem",
]
WEEKLY_RECITATIONS = ["313 darood", "Quran Every Jummah"]  # Friday-only


def classify_section(task_text: str) -> str | None:
    """Map a task's text to its project section, or None if out of scope.

    Out of scope: Namaz & Jamaat (now prayers-as-habits, no data), Qaza 2 Fajr,
    #### Quran, Sadaqa, and all to-dos.
    """
    t = task_text or ""
    for key in WEEKLY_RECITATIONS:
        if key in t:
            return "weekly_recitation"
    for key in DAILY_RECITATIONS:
        if key in t:
            return "daily_recitation"
    return None
