"""Analytics helpers: parameterised SQL returning pandas DataFrames.

These are the building blocks the notebook calls so that every figure traces
back to an auditable query. Keeping the SQL here (not scattered in notebook
cells) makes the analysis reproducible and testable.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


def events(conn: sqlite3.Connection) -> pd.DataFrame:
    """All daily events joined to task text + category, PKT fields parsed."""
    df = q(conn, """
        SELECT e.event_id, e.task_id, t.text AS task_text, c.category,
               e.event_ts_utc, e.event_date_pkt, e.event_hour_pkt, e.event_weekday,
               e.value, e.value_delta, e.observed_action, e.confidence
        FROM daily_events e
        JOIN tasks t ON t.task_id = e.task_id
        LEFT JOIN task_classifications c ON c.task_id = e.task_id
    """)
    df["event_date_pkt"] = pd.to_datetime(df["event_date_pkt"])
    df["weekday_name"] = df["event_weekday"].map(dict(enumerate(WEEKDAY_NAMES)))
    return df


def adherence_by_task(conn: sqlite3.Connection) -> pd.DataFrame:
    """Per-daily completed/missed/undetermined counts and two adherence rates.

    rate_determinable = completed / (completed+missed)   [excludes flats]
    rate_conservative = completed / (completed+missed+undetermined)  [flats as non-done]
    """
    df = q(conn, """
        SELECT t.task_id, t.text AS task_text, t.streak, t.value,
               SUM(e.observed_action='completed')     AS completed,
               SUM(e.observed_action='missed')        AS missed,
               SUM(e.observed_action='undetermined')  AS undetermined,
               COUNT(*)                                AS events,
               MIN(e.event_date_pkt) AS first_event,
               MAX(e.event_date_pkt) AS last_event
        FROM tasks t JOIN daily_events e ON e.task_id=t.task_id
        WHERE t.task_type='daily'
        GROUP BY t.task_id
    """)
    det = (df["completed"] + df["missed"]).replace(0, pd.NA)
    df["rate_determinable"] = (df["completed"] / det).astype(float)
    df["rate_conservative"] = (df["completed"] / df["events"]).astype(float)
    return df.sort_values("rate_determinable", ascending=False)


def weekday_profile(conn: sqlite3.Connection) -> pd.DataFrame:
    df = events(conn)
    det = df[df["observed_action"].isin(["completed", "missed"])].copy()
    g = (det.assign(done=(det["observed_action"] == "completed").astype(int))
            .groupby("weekday_name")
            .agg(events=("done", "size"), completed=("done", "sum")))
    g["rate"] = g["completed"] / g["events"]
    return g.reindex(WEEKDAY_NAMES)


def timeofday_profile(conn: sqlite3.Connection) -> pd.DataFrame:
    """Hour-of-day (PKT) distribution of COMPLETED events only (meaningful ts)."""
    df = events(conn)
    done = df[df["observed_action"] == "completed"]
    return (done.groupby("event_hour_pkt").size()
               .reindex(range(24), fill_value=0)
               .rename("completions").to_frame())


def daily_activity(conn: sqlite3.Connection) -> pd.DataFrame:
    """Per local-day: events, completions, active flag — for calendar/streaks."""
    df = events(conn)
    g = (df.assign(done=(df["observed_action"] == "completed").astype(int))
            .groupby("event_date_pkt")
            .agg(events=("done", "size"), completions=("done", "sum")))
    return g.sort_index()


def value_trajectory(conn: sqlite3.Connection) -> pd.DataFrame:
    """Per-task running `value` over time (the Habitica momentum curve)."""
    df = events(conn)[["task_text", "event_date_pkt", "value", "observed_action"]]
    return df.sort_values(["task_text", "event_date_pkt"])


def daily_load(conn: sqlite3.Connection) -> pd.DataFrame:
    """Per local-day: how many distinct dailies were completed vs missed.

    Supports 'bad day' / 'perfect day' detection. Uses determinable events only.
    """
    df = events(conn)
    det = df[df["observed_action"].isin(["completed", "missed"])].copy()
    det["done"] = (det["observed_action"] == "completed").astype(int)
    g = det.groupby("event_date_pkt").agg(
        due_tasks=("task_id", "nunique"),
        decided_events=("done", "size"),
        completed=("done", "sum"),
    )
    g["missed"] = g["decided_events"] - g["completed"]
    g["day_rate"] = g["completed"] / g["decided_events"]
    return g.sort_index()


def recovery_after_miss(conn: sqlite3.Connection) -> dict:
    """Per task, probability the NEXT determinable event is completed, split by
    whether the current event was a miss or a completion. Tests 'do misses
    snowball?'. Returns overall transition probabilities + per-task table.
    """
    df = events(conn)
    det = df[df["observed_action"].isin(["completed", "missed"])].copy()
    det = det.sort_values(["task_id", "event_date_pkt"])
    det["is_done"] = (det["observed_action"] == "completed").astype(int)
    det["next_done"] = det.groupby("task_id")["is_done"].shift(-1)
    pairs = det.dropna(subset=["next_done"])
    after_miss = pairs[pairs["is_done"] == 0]["next_done"]
    after_done = pairs[pairs["is_done"] == 1]["next_done"]
    per_task = (pairs.groupby(["task_text", "is_done"])["next_done"]
                     .mean().unstack().rename(columns={0: "p_done_after_miss",
                                                        1: "p_done_after_done"}))
    return {
        "p_done_after_miss": float(after_miss.mean()) if len(after_miss) else float("nan"),
        "p_done_after_done": float(after_done.mean()) if len(after_done) else float("nan"),
        "n_after_miss": int(len(after_miss)),
        "n_after_done": int(len(after_done)),
        "per_task": per_task,
    }


def honeymoon_decay(conn: sqlite3.Connection, first_days: int = 7) -> pd.DataFrame:
    """Per task: adherence in the first N days of events vs the rest.

    Tests whether new practices start strong and decay ('novelty effect').
    """
    df = events(conn)
    det = df[df["observed_action"].isin(["completed", "missed"])].copy()
    det["done"] = (det["observed_action"] == "completed").astype(int)
    out = []
    for name, g in det.groupby("task_text"):
        g = g.sort_values("event_date_pkt")
        start = g["event_date_pkt"].min()
        early = g[g["event_date_pkt"] < start + pd.Timedelta(days=first_days)]
        late = g[g["event_date_pkt"] >= start + pd.Timedelta(days=first_days)]
        out.append({
            "task_text": name,
            "early_rate": early["done"].mean() if len(early) else float("nan"),
            "early_n": len(early),
            "late_rate": late["done"].mean() if len(late) else float("nan"),
            "late_n": len(late),
        })
    return pd.DataFrame(out)


def miss_cooccurrence(conn: sqlite3.Connection) -> pd.DataFrame:
    """Day x task matrix of outcomes (1=done, 0=miss, NaN=not decided) so we can
    see whether tasks are missed TOGETHER (systemic bad days) or independently.
    """
    df = events(conn)
    det = df[df["observed_action"].isin(["completed", "missed"])].copy()
    det["done"] = (det["observed_action"] == "completed").astype(int)
    return det.pivot_table(index="event_date_pkt", columns="task_text",
                           values="done", aggfunc="max")


def todo_latency(conn: sqlite3.Connection) -> pd.DataFrame:
    df = q(conn, """
        SELECT task_id, text, created_at_utc, date_completed_utc, completed
        FROM tasks WHERE task_type='todo'
    """)
    c = pd.to_datetime(df["created_at_utc"], utc=True)
    d = pd.to_datetime(df["date_completed_utc"], utc=True)
    df["latency_hours"] = (d - c).dt.total_seconds() / 3600.0
    return df
