"""Per-plugin config — a plugin owns its defaults; the user overrides them.

Each Source declares `defaults` (a dict) and optionally `wants_location = True` to also
receive the shared location (city/country/method/timezone). A plugin's config slice is a
layered merge, highest priority last:

    plugin `defaults`  ←  shared location (if wanted)  ←  user `config[id]`

Dict-valued defaults merge one level deep: a user writing `{"morning": {"enabled":
true}}` keeps the default `morning.time` instead of wiping the whole section.

This is the pydantic-settings / VS Code `contributes.configuration` pattern. Adding a
plugin needs **zero wiring** here: it declares `defaults`, and reads its slice in
`check()`. `config.json` is keyed by plugin id, so `config[id]` is the user's overrides.
"""

from __future__ import annotations


def slice_for(
    source, raw: dict, location: dict, force_id: str | None = None, force_kind: str | None = None
) -> dict:
    """Build one plugin's resolved config slice."""
    defaults = dict(getattr(source, "defaults", {}))
    cfg = dict(defaults)  # 1. plugin defaults
    if getattr(source, "wants_location", False):
        cfg.update(location)  # 2. shared location (opt-in)
    for key, val in (raw.get(source.id, {}) or {}).items():  # 3. user overrides
        if isinstance(val, dict) and isinstance(defaults.get(key), dict):
            cfg[key] = {**defaults[key], **val}  # partial section keeps its defaults
        else:
            cfg[key] = val
    cfg["force"] = force_id == source.id  # on-demand 'send now'
    if cfg["force"] and force_kind:
        cfg["force_kind"] = force_kind  # which format the forced send uses (plugin-defined)
    return cfg


def build(
    sources, raw: dict, location: dict, force_id: str | None = None, force_kind: str | None = None
) -> dict:
    """Map every source id → its resolved config slice."""
    return {s.id: slice_for(s, raw, location, force_id, force_kind) for s in sources}
