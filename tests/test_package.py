"""The package exposes a version + a plugin-API major, so plugins can pin a stable contract."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import noterpiper  # noqa: E402


def test_exposes_a_version_string():
    assert isinstance(noterpiper.__version__, str) and noterpiper.__version__


def test_plugin_api_major_matches_the_version():
    assert noterpiper.PLUGIN_API_MAJOR == int(noterpiper.__version__.split(".")[0]) == 1
