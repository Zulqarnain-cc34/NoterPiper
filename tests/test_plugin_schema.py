"""The config-UI schema generator: collect each plugin's declared controls + defaults into
one JSON the config page renders from — so a new plugin never edits the app's JS."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import gen_plugin_schema  # noqa: E402
from noterpiper import plugins  # noqa: E402
from noterpiper.engine.registry import discover_all  # noqa: E402


def test_schema_includes_auto_generated_plugins_with_fields_and_defaults():
    schema = gen_plugin_schema.build_schema(discover_all(plugins))
    assert "dates" in schema
    assert any(f["key"] == "items" for f in schema["dates"]["fields"])
    assert schema["dates"]["defaults"]["lead_days"] == 3       # default travels with the fields


def test_hand_built_cards_are_not_auto_generated():
    # prayer/habitica/ramadan have bespoke cards in docs/index.html; they declare no
    # config_schema, so the generator must not emit them (no duplicate/competing controls).
    schema = gen_plugin_schema.build_schema(discover_all(plugins))
    assert "habitica" not in schema
    assert "ramadan" not in schema
    assert "prayer" not in schema


def test_a_plugin_without_a_schema_is_omitted():
    class Bare:
        id = "bare"
        defaults = {"x": 1}
        def check(self, now, config): return []
    assert "bare" not in gen_plugin_schema.build_schema([Bare()])


def test_every_field_declares_key_type_and_label():
    schema = gen_plugin_schema.build_schema(discover_all(plugins))
    for plugin in schema.values():
        for field in plugin["fields"]:
            assert {"key", "type", "label"} <= set(field)
            assert field["type"] in {"toggle", "stepper", "time", "text", "select", "list"}


def test_committed_schema_file_is_in_sync_with_the_generator():
    # The generator is run by hand, so the committed JSON can silently go stale. This guard
    # (run in CI) fails if someone edits a plugin's config_schema without regenerating:
    #     python scripts/gen_plugin_schema.py
    committed = json.loads((ROOT / "docs" / "plugins.schema.json").read_text())
    generated = gen_plugin_schema.build_schema(discover_all(plugins))
    assert committed == generated, "docs/plugins.schema.json is stale — run gen_plugin_schema.py"
