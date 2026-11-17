#!/usr/bin/env python3
"""Generate docs/plugins.schema.json from each plugin's declared config UI.

A plugin declares its config controls as a `config_schema` (list of field specs) plus its
`defaults`. This script collects them from every discovered plugin into one JSON file that
the config page renders controls from — so adding a plugin needs **zero app wiring**.

Run it whenever a plugin's config UI changes:

    python scripts/gen_plugin_schema.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from noterpiper import plugins  # noqa: E402
from noterpiper.engine.registry import discover_all  # noqa: E402

OUT = ROOT / "docs" / "plugins.schema.json"


def build_schema(sources) -> dict:
    """{plugin_id: {"fields": [...], "defaults": {...}}} for every plugin that declares a
    config_schema. Plugins without one are omitted (no auto-generated controls)."""
    out: dict = {}
    for s in sources:
        fields = getattr(s, "config_schema", None)
        if not fields:
            continue
        out[s.id] = {"fields": list(fields), "defaults": dict(getattr(s, "defaults", {}))}
    return out


def main() -> int:
    schema = build_schema(discover_all(plugins))
    OUT.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(schema)} plugins: {', '.join(sorted(schema))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
