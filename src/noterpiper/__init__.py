"""noterpiper — shared library for the reminder/nudge scripts.

config   — settings (env/.env) + helpers
settings — one config.json (location, offsets, nudge) → typed Settings
net      — resilient HTTP (retries + backoff) used by everything
api      — read-only Habitica client (optional)
"""

from importlib.metadata import PackageNotFoundError  # stdlib (Python >= 3.10)
from importlib.metadata import version as _version

from . import api, config, net, settings  # noqa: F401

try:  # the installed package version, if pip-installed
    __version__ = _version("noterpiper")
except PackageNotFoundError:  # running from a source checkout
    __version__ = "1.0.0"

# The plugin contract (`Source`: `id` + `check(now, config) -> [Notification]`) is stable
# within a major version — NoterPiper follows SemVer, so a breaking change to the contract
# bumps the major. Plugin authors can pin `noterpiper>=1,<2`. See PLUGIN-AUTHORING.md.
PLUGIN_API_MAJOR = int(__version__.split(".")[0])

__all__ = ["config", "net", "api", "settings", "__version__", "PLUGIN_API_MAJOR"]
