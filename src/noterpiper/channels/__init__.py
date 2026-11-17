"""noterpiper.channels — concrete delivery channels for the engine.

Each satisfies `noterpiper.engine.Channel`, so the engine can deliver through any
combination of them without change.

  NtfyChannel     — push to an ntfy topic (dedups via ntfy's message cache)
  WebhookChannel  — POST to any URL (Discord, Slack, Home Assistant, your endpoint…)
"""

from .ntfy import NtfyChannel
from .webhook import WebhookChannel

__all__ = ["NtfyChannel", "WebhookChannel"]
