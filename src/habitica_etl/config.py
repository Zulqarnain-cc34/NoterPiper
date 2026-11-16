"""Settings for the Habitica Salah reminder/nudge scripts."""
from __future__ import annotations

from datetime import timedelta, timezone
from pathlib import Path

# --- Paths -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_JSON = DATA_DIR / "habitica-live.json"  # optional local snapshot (User-ID fallback)

# --- Timezone ----------------------------------------------------------------
# Account timezone is UTC+5 = Asia/Karachi (Pakistan). No DST.
ANALYSIS_TZ = timezone(timedelta(hours=5))

# --- Which recitations the nightly nudge watches ----------------------------
# Matched by a substring of the task text (handles Arabic suffixes in the names).
DAILY_RECITATIONS = [
    "Surah Mulk", "500 ", "tasbeeh fatima", "11 Times Muhammad", "Quran Hakeem",
]
WEEKLY_RECITATIONS = ["313 darood", "Quran Every Jummah"]  # Friday-only


def classify_section(task_text: str) -> str | None:
    """Return 'daily_recitation' / 'weekly_recitation', or None if not watched."""
    t = task_text or ""
    for key in WEEKLY_RECITATIONS:
        if key in t:
            return "weekly_recitation"
    for key in DAILY_RECITATIONS:
        if key in t:
            return "daily_recitation"
    return None
