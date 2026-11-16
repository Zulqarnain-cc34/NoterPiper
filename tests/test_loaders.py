"""Loader tests — structural, against whichever data source is present."""
from habitica_etl import config, loaders

SRC = config.DATA_DIR / "habitica-live.json"
if not SRC.exists():
    SRC = config.RAW_JSON


def test_json_loads_and_has_tasks():
    u = loaders.load_user_json(SRC)
    assert u.get("id") or u.get("_id")
    assert loaders.extract_dailies(u)  # at least some dailies


def test_account_facts_timezone():
    facts = loaders.account_facts(loaders.load_user_json(SRC))
    assert facts["timezone_offset_min"] == -300  # UTC+5 Asia/Karachi


def test_checksum_is_sha256():
    c = loaders.file_checksum(SRC)
    assert len(c) == 64


def test_checksum_missing_file_is_safe():
    # must not raise when the file is absent (lineage records a placeholder)
    assert len(loaders.file_checksum(config.DATA_DIR / "does-not-exist.json")) == 64
