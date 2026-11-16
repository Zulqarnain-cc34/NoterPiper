"""muezzin.channels — concrete delivery channels for the engine.

Today there is one: ntfy. Each channel satisfies `muezzin.engine.Channel`, so the
engine can deliver through any of them without change.
"""
from .ntfy import NtfyChannel

__all__ = ["NtfyChannel"]
