"""Per-plugin config: a plugin owns its defaults; the user overrides them.

Layered merge (highest wins): plugin `defaults` ← shared location (if wanted) ←
user `config[id]`. This is how a new plugin's config works with zero wiring —
the pydantic-settings / VS Code contributes.configuration pattern."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noterpiper.engine.config import build, slice_for


class FakeSource:
    def __init__(self, id, defaults, wants_location=False):
        self.id = id
        self.defaults = defaults
        self.wants_location = wants_location

    def check(self, now, config):
        return []


def test_defaults_are_the_baseline():
    s = FakeSource("x", {"a": 1, "b": 2})
    assert slice_for(s, {}, {}) == {"a": 1, "b": 2, "force": False}


def test_user_config_overrides_defaults():
    s = FakeSource("x", {"a": 1, "b": 2})
    assert slice_for(s, {"x": {"b": 9}}, {})["b"] == 9


def test_location_is_injected_only_when_wanted():
    loc = {"city": "Lahore", "method": "1"}
    assert slice_for(FakeSource("p", {}, wants_location=True), {}, loc)["city"] == "Lahore"
    assert "city" not in slice_for(FakeSource("h", {}), {}, loc)


def test_user_config_overrides_location():
    s = FakeSource("p", {}, wants_location=True)
    assert slice_for(s, {"p": {"city": "Cairo"}}, {"city": "Lahore"})["city"] == "Cairo"


def test_force_flag_marks_only_the_forced_plugin():
    s = FakeSource("x", {})
    assert slice_for(s, {}, {}, force_id="x")["force"] is True
    assert slice_for(s, {}, {}, force_id="y")["force"] is False


def test_build_maps_each_source_by_id():
    cfg = build([FakeSource("a", {"k": 1}), FakeSource("b", {"k": 2})], {}, {})
    assert cfg["a"]["k"] == 1 and cfg["b"]["k"] == 2


def test_a_plugin_with_no_defaults_still_works():
    class Bare:
        id = "bare"

        def check(self, now, config):
            return []

    assert slice_for(Bare(), {"bare": {"on": True}}, {}) == {"on": True, "force": False}


def test_dict_defaults_merge_one_level_deep():
    """A partial user section keeps the rest of its defaults — writing
    {"morning": {"enabled": true}} must not wipe the default morning time."""

    class Src:
        id = "x"
        defaults = {"time": "21:30", "morning": {"enabled": False, "time": "06:00"}}

    cfg = slice_for(Src(), {"x": {"morning": {"enabled": True}}}, {})
    assert cfg["morning"] == {"enabled": True, "time": "06:00"}
    assert cfg["time"] == "21:30"


def test_force_kind_rides_along_only_on_the_forced_source():
    class Src:
        id = "x"
        defaults = {}

    forced = slice_for(Src(), {}, {}, force_id="x", force_kind="morning")
    assert forced["force"] is True and forced["force_kind"] == "morning"
    other = slice_for(Src(), {}, {}, force_id="y", force_kind="morning")
    assert other["force"] is False and "force_kind" not in other
