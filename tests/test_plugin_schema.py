"""The config-UI schema generator: collect each plugin's declared controls + defaults into
one JSON the config page renders from — so a new plugin never edits the app's JS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import gen_plugin_schema  # noqa: E402
from noterpiper import plugins  # noqa: E402
from noterpiper.engine.registry import discover_all  # noqa: E402


def test_schema_includes_declaring_plugins_with_fields_and_defaults():
    schema = gen_plugin_schema.build_schema(discover_all(plugins))
    assert "habitica" in schema and "ramadan" in schema
    assert any(f["key"] == "streak_risk" for f in schema["habitica"]["fields"])
    assert schema["habitica"]["defaults"]["streak_risk"] == 7      # default travels with the field


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
            assert field["type"] in {"toggle", "stepper", "time", "text", "select"}
