"""Per-plugin config — a plugin owns its defaults; the user overrides them.

Each Source declares `defaults` (a dict) and optionally `wants_location = True` to also
receive the shared location (city/country/method/timezone). A plugin's config slice is a
layered merge, highest priority last:

    plugin `defaults`  ←  shared location (if wanted)  ←  user `config[id]`

This is the pydantic-settings / VS Code `contributes.configuration` pattern. Adding a
plugin needs **zero wiring** here: it declares `defaults`, and reads its slice in
`check()`. `config.json` is keyed by plugin id, so `config[id]` is the user's overrides.
"""
from __future__ import annotations


def slice_for(source, raw: dict, location: dict, force_id: str | None = None) -> dict:
    """Build one plugin's resolved config slice."""
    cfg = dict(getattr(source, "defaults", {}))                 # 1. plugin defaults
    if getattr(source, "wants_location", False):
        cfg.update(location)                                    # 2. shared location (opt-in)
    cfg.update(raw.get(source.id, {}) or {})                    # 3. user overrides (config.json[id])
    cfg["force"] = force_id == source.id                        # on-demand 'send now'
    return cfg


def build(sources, raw: dict, location: dict, force_id: str | None = None) -> dict:
    """Map every source id → its resolved config slice."""
    return {s.id: slice_for(s, raw, location, force_id) for s in sources}
