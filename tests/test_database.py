"""Ingestion tests — structural & idempotency, against the live source."""
import pytest

from habitica_etl import config, database, loaders, validation

SRC = config.DATA_DIR / "habitica-live.json"
if not SRC.exists():
    SRC = config.RAW_JSON


@pytest.fixture
def built_conn(tmp_path):
    user = loaders.load_user_json(SRC)
    conn = database.connect(tmp_path / "test.db")
    database.create_schema(conn)
    database.ingest_user(conn, user, json_path=SRC)
    yield conn
    conn.close()


def test_has_dailies_and_events(built_conn):
    r = validation.integrity_checks(built_conn)
    assert r["n_dailies"] > 0
    assert r["n_events"] > 0


def test_no_fk_violations_or_orphans(built_conn):
    r = validation.integrity_checks(built_conn)
    assert r["foreign_key_violations"] == []
    assert r["orphan_events"] == 0


def test_actions_are_valid(built_conn):
    bd = validation.integrity_checks(built_conn)["action_breakdown"]
    assert set(bd) <= {config.ACTION_COMPLETED, config.ACTION_MISSED, config.ACTION_UNDETERMINED}


def test_ingestion_is_idempotent(tmp_path):
    user = loaders.load_user_json(SRC)
    conn = database.connect(tmp_path / "idem.db")
    database.create_schema(conn)
    database.ingest_user(conn, user, json_path=SRC)
    n1 = conn.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0]
    database.ingest_user(conn, user, json_path=SRC)  # re-run
    n2 = conn.execute("SELECT COUNT(*) FROM daily_events").fetchone()[0]
    assert n1 == n2 and n1 > 0
    conn.close()


def test_pre_window_events_excluded(built_conn):
    bad = built_conn.execute(
        "SELECT COUNT(*) FROM daily_events WHERE event_date_pkt < ?",
        (config.ANALYSIS_START_DATE,),
    ).fetchone()[0]
    assert bad == 0
