"""noterpiper.engine — the notification engine's core contracts.

  Notification — the immutable value object every layer passes around
  Source       — the plugin contract (decide what to notify, and when)
  Channel      — the delivery contract (decide how to send)

The engine orchestrates Sources and a Channel; it depends on these abstractions,
never on a concrete plugin — which is what lets new sources plug in untouched.
"""
from .channel import Channel
from .plugin import Source
from .types import Notification

__all__ = ["Notification", "Source", "Channel"]
