"""SQLite schema definition and transaction-safe, idempotent ingestion.

Design goals (per project spec):
  * Primary & foreign keys, indexes, referential integrity (PRAGMA enforced).
  * Idempotent ingestion — re-running never duplicates rows (deterministic
    event ids + INSERT OR REPLACE semantics inside a single transaction).
  * Source lineage — every import is recorded with filename + SHA-256 checksum.
  * The raw exports remain the source of truth; this DB is the clean store.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import config, loaders, transform

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS import_batches (
    import_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source_filename  TEXT NOT NULL,
    source_checksum  TEXT NOT NULL,
    import_timestamp TEXT NOT NULL,
    record_count     INTEGER NOT NULL,
    import_status    TEXT NOT NULL,
    UNIQUE (source_filename, source_checksum)
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id          TEXT PRIMARY KEY,
    task_type        TEXT NOT NULL,              -- 'daily' | 'todo'
    text             TEXT NOT NULL,              -- verbatim user text
    notes            TEXT,                       -- verbatim user notes
    priority         REAL,                       -- Habitica difficulty
    value            REAL,                       -- current running value
    streak           INTEGER,                    -- dailies only
    created_at_utc   TEXT,
    updated_at_utc   TEXT,
    start_date_utc   TEXT,                       -- dailies only
    completed        INTEGER,                    -- 0/1
    date_completed_utc TEXT,                     -- todos only
    recurrence_json  TEXT,                       -- decoded current config (dailies)
    source           TEXT NOT NULL,
    data_quality_flag TEXT
);

CREATE TABLE IF NOT EXISTS daily_events (
    event_id        TEXT PRIMARY KEY,            -- deterministic (task_id+ts)
    task_id         TEXT NOT NULL,
    event_ts_utc    TEXT NOT NULL,
    event_date_pkt  TEXT NOT NULL,               -- local calendar date
    event_hour_pkt  INTEGER NOT NULL,
    event_weekday   INTEGER NOT NULL,            -- 0=Mon .. 6=Sun (PKT)
    value           REAL NOT NULL,
    value_delta     REAL NOT NULL,
    observed_action TEXT NOT NULL,               -- completed|missed|undetermined
    confidence      TEXT NOT NULL,
    source_file     TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    UNIQUE (task_id, event_ts_utc)
);

CREATE TABLE IF NOT EXISTS task_classifications (
    task_id     TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    confidence  TEXT NOT NULL,
    method      TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    issue_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    scope       TEXT NOT NULL,     -- table/entity
    ref_id      TEXT,              -- task_id/event_id if applicable
    issue_type  TEXT NOT NULL,
    detail      TEXT
);

CREATE INDEX IF NOT EXISTS ix_events_task_date
    ON daily_events(task_id, event_date_pkt);
CREATE INDEX IF NOT EXISTS ix_events_action
    ON daily_events(observed_action);
CREATE INDEX IF NOT EXISTS ix_tasks_type
    ON tasks(task_type);
"""


def connect(db_path: str | Path = config.DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_batch(
    conn: sqlite3.Connection, filename: str, checksum: str, count: int, status: str
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO import_batches
           (import_id, source_filename, source_checksum, import_timestamp, record_count, import_status)
           VALUES (
             (SELECT import_id FROM import_batches WHERE source_filename=? AND source_checksum=?),
             ?, ?, ?, ?, ?)""",
        (filename, checksum, filename, checksum, _now_utc_iso(), count, status),
    )


def ingest_user(
    conn: sqlite3.Connection,
    user: dict[str, Any],
    *,
    json_path: str | Path = config.RAW_JSON,
) -> dict[str, int]:
    """Idempotently ingest tasks, daily events, and classifications from JSON.

    Runs in a single transaction. Deterministic ids + INSERT OR REPLACE make
    re-ingestion a no-op on counts.
    """
    dailies = loaders.extract_dailies(user)
    todos = loaders.extract_todos(user)
    counts = {"tasks": 0, "daily_events": 0, "classifications": 0, "quality_issues": 0}

    import json as _json

    with conn:  # transaction
        # --- tasks: dailies ---
        for t in dailies:
            rec = transform.decode_recurrence(t)
            conn.execute(
                """INSERT OR REPLACE INTO tasks
                   (task_id, task_type, text, notes, priority, value, streak,
                    created_at_utc, updated_at_utc, start_date_utc, completed,
                    date_completed_utc, recurrence_json, source, data_quality_flag)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    t["_id"], "daily", t.get("text", ""), t.get("notes"),
                    t.get("priority"), t.get("value"), t.get("streak"),
                    t.get("createdAt"), t.get("updatedAt"), t.get("startDate"),
                    int(bool(t.get("completed"))), None,
                    _json.dumps(rec, ensure_ascii=False), "json:dailys", None,
                ),
            )
            counts["tasks"] += 1

            # classification
            cl = transform.classify_category(t.get("text"), t.get("notes"))
            conn.execute(
                "INSERT OR REPLACE INTO task_classifications (task_id, category, confidence, method) VALUES (?,?,?,?)",
                (t["_id"], cl["category"], cl["confidence"], cl["method"]),
            )
            counts["classifications"] += 1

            # daily events (classify on FULL history for correct value deltas,
            # then keep only events inside the analysis window)
            events = transform.classify_daily_history(t.get("history", []))
            n_undet = 0
            n_excluded = 0
            for e in events:
                dt_utc = transform.epoch_ms_to_utc(e["epoch_ms"])
                dt_pkt = transform.to_pkt(dt_utc)
                if dt_pkt.date().isoformat() < config.ANALYSIS_START_DATE:
                    n_excluded += 1
                    continue  # pre-restart event, excluded by design
                eid = transform.daily_event_id(t["_id"], e["epoch_ms"])
                conn.execute(
                    """INSERT OR REPLACE INTO daily_events
                       (event_id, task_id, event_ts_utc, event_date_pkt, event_hour_pkt,
                        event_weekday, value, value_delta, observed_action, confidence, source_file)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        eid, t["_id"], dt_utc.isoformat(), dt_pkt.date().isoformat(),
                        dt_pkt.hour, dt_pkt.weekday(), e["value"], e["value_delta"],
                        e["observed_action"], e["confidence"], "json:dailys.history",
                    ),
                )
                counts["daily_events"] += 1
                if e["observed_action"] == config.ACTION_UNDETERMINED:
                    n_undet += 1
            if n_undet:
                conn.execute(
                    "INSERT INTO data_quality_issues (scope, ref_id, issue_type, detail) VALUES (?,?,?,?)",
                    ("daily_events", t["_id"], "undetermined_flat_value",
                     f"{n_undet} flat-value history entries could not be decoded to completed/missed"),
                )
                counts["quality_issues"] += 1
            if n_excluded:
                conn.execute(
                    "INSERT INTO data_quality_issues (scope, ref_id, issue_type, detail) VALUES (?,?,?,?)",
                    ("daily_events", t["_id"], "excluded_pre_window",
                     f"{n_excluded} event(s) before {config.ANALYSIS_START_DATE} excluded by design"),
                )
                counts["quality_issues"] += 1

        # --- tasks: todos ---
        for t in todos:
            flag = None
            if not t.get("date"):
                flag = "no_due_date"
            conn.execute(
                """INSERT OR REPLACE INTO tasks
                   (task_id, task_type, text, notes, priority, value, streak,
                    created_at_utc, updated_at_utc, start_date_utc, completed,
                    date_completed_utc, recurrence_json, source, data_quality_flag)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    t["_id"], "todo", t.get("text", ""), t.get("notes"),
                    t.get("priority"), t.get("value"), None,
                    t.get("createdAt"), t.get("updatedAt"), None,
                    int(bool(t.get("completed"))), t.get("dateCompleted"),
                    None, "json:todos", flag,
                ),
            )
            counts["tasks"] += 1
            cl = transform.classify_category(t.get("text"), t.get("notes"))
            conn.execute(
                "INSERT OR REPLACE INTO task_classifications (task_id, category, confidence, method) VALUES (?,?,?,?)",
                (t["_id"], cl["category"], cl["confidence"], cl["method"]),
            )
            counts["classifications"] += 1

        _record_batch(conn, Path(json_path).name,
                      loaders.file_checksum(json_path), counts["tasks"], "success")
    return counts
