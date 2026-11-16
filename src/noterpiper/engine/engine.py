"""The engine — the orchestrator.

On each run it asks every registered source "anything due right now?", enforces the
once-per-day dedup via the channel, and delivers. It depends only on the Source and
Channel contracts, so adding a plugin never changes this file (Open/Closed).
"""
from __future__ import annotations

from datetime import datetime

from .channel import Channel
from .plugin import Source


class Engine:
    def __init__(self, channel: Channel, sources: list[Source]):
        self.channel = channel
        self.sources = sources

    def run(self, now: datetime, config: dict) -> int:
        """Run every source once; deliver what's due. Returns how many were sent.

        A source or a single delivery that raises is isolated — it never stops the
        others (prayer reminders and the nudge stay independent)."""
        sent = 0
        for src in self.sources:
            try:
                due = src.check(now, config.get(src.id, {}))
            except Exception as e:
                print(f"[warn] source {src.id!r} failed: {e}")
                continue
            for n in due:
                try:
                    if n.dedup_key and self.channel.already_sent(n.dedup_key, now):
                        continue
                    self.channel.send(n)
                    sent += 1
                except Exception as e:
                    print(f"[warn] delivering {n.title!r} from {src.id!r} failed: {e}")
        return sent
