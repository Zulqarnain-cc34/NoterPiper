"""Post-ingestion validation and integrity checks."""
from __future__ import annotations

import sqlite3
from typing import Any


def integrity_checks(conn: sqlite3.Connection) -> dict[str, Any]:
    """Run referential-integrity and basic sanity checks. Returns a report dict."""
    report: dict[str, Any] = {}
    report["foreign_key_violations"] = conn.execute("PRAGMA foreign_key_check").fetchall()
    report["n_tasks"] = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    report["n_dailies"] = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE task_type='daily'").fetchone()[0]
    report["n_todos"] = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE task_type='todo'").fetchone()[0]
    report["n_events"] = conn.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0]
    report["orphan_events"] = conn.execute(
        "SELECT COUNT(*) FROM daily_events e LEFT JOIN tasks t ON e.task_id=t.task_id WHERE t.task_id IS NULL"
    ).fetchone()[0]
    report["action_breakdown"] = dict(
        conn.execute(
            "SELECT observed_action, COUNT(*) FROM daily_events GROUP BY observed_action"
        ).fetchall()
    )
    return report
