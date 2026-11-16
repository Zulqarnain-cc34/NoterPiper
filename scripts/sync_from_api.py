#!/usr/bin/env python3
"""Live Sync — one command:
    pull current Habitica data via the API (read-only)
    → rebuild the database
    → regenerate the dashboard (static HTML in site/)

Usage:  python scripts/sync_from_api.py
Reads the token from .env / env (never printed). Strips secrets before saving.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from habitica_etl import api, config, database, validation  # noqa: E402

SECRET_KEYS = {"apiToken", "_subSignature"}


def sanitize(user: dict) -> dict:
    for k in SECRET_KEYS:
        user.pop(k, None)
    user.get("auth", {}).pop("local", None)  # drop email/username
    return user


def main() -> int:
    print("① Pulling live data (read-only)…")
    user = sanitize(api.fetch_export_like())
    live = config.DATA_DIR / "habitica-live.json"
    live.write_text(json.dumps(user, ensure_ascii=False, indent=2))
    print(f"   saved {live.name} (secrets stripped)")

    print("② Rebuilding database…")
    conn = database.connect(config.DB_PATH)
    database.create_schema(conn)
    database.ingest_user(conn, user, json_path=live)
    integ = validation.integrity_checks(conn)
    print(f"   {integ['n_dailies']} dailies · {integ['n_events']} events · FK ok={not integ['foreign_key_violations']}")
    conn.close()

    print("③ Regenerating dashboard…")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_recitations_dashboard.py")], check=True)
    subprocess.run([
        sys.executable, "-m", "jupyter", "nbconvert", "--to", "html", "--execute",
        "--no-input", "--output", "index", "--output-dir", str(ROOT / "site"),
        str(ROOT / "notebooks" / "recitations_dashboard.ipynb"),
    ], check=True)
    print("   dashboard → site/index.html")
    print("\n✓ Sync complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
