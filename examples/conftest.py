"""Make the examples runnable from inside this monorepo.

In a real plugin repo you wouldn't need this — `noterpiper` would be a pip-installed
dependency. Here it lives in ../src, so put that (and examples/ itself) on the path
before any example package imports `noterpiper`. This file sits *outside* the example
packages so it loads before they're imported."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))  # noterpiper
sys.path.insert(0, str(HERE))  # examples/ → `import plugin_template`
