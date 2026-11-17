"""The read-only Habitica client — the thin bits worth pinning.

Habitica's contract (v3): GET /tags → {"data": [{"id","name"}, …]}. We map it to
{id: name} so tasks' `tags` UUIDs can be resolved to section names."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noterpiper import api


def test_get_raises_a_clear_error_on_a_failed_envelope(monkeypatch):
    # Habitica wraps responses as {success, data}. On success:false there may be no data —
    # surface the message instead of a bare KeyError.
    monkeypatch.setattr(api, "_creds", lambda: ("uid", "token"))
    monkeypatch.setattr(
        api.net,
        "get_json",
        lambda url, **kw: {"success": False, "message": "Missing authentication headers."},
    )
    with pytest.raises(RuntimeError, match="Missing authentication"):
        api._get("/tasks/user")


def test_get_returns_data_on_success(monkeypatch):
    monkeypatch.setattr(api, "_creds", lambda: ("uid", "token"))
    monkeypatch.setattr(api.net, "get_json", lambda url, **kw: {"success": True, "data": [1, 2]})
    assert api._get("/x") == [1, 2]


def test_fetch_tags_maps_id_to_name(monkeypatch):
    monkeypatch.setattr(api, "_creds", lambda: ("uid", "token"))
    monkeypatch.setattr(
        api.net,
        "get_json",
        lambda url, **kw: {
            "data": [{"id": "a1", "name": "prayer"}, {"id": "b2", "name": "Archived"}]
        },
    )
    assert api.fetch_tags() == {"a1": "prayer", "b2": "Archived"}


def test_fetch_tags_skips_malformed_entries(monkeypatch):
    monkeypatch.setattr(api, "_creds", lambda: ("uid", "token"))
    monkeypatch.setattr(
        api.net,
        "get_json",
        lambda url, **kw: {
            "data": [{"id": "a1", "name": "quran"}, {"name": "no id"}, {"id": "c3"}]
        },
    )
    assert api.fetch_tags() == {"a1": "quran", "c3": ""}  # no-id dropped; missing name → ""
