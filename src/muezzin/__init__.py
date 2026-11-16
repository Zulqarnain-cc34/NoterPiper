"""muezzin — shared library for the reminder/nudge scripts.

  config  — settings (env/.env) + helpers
  net     — resilient HTTP (retries + backoff) used by everything
  api     — read-only Habitica client (optional)
"""
from . import api, config, net  # noqa: F401

__all__ = ["config", "net", "api"]
