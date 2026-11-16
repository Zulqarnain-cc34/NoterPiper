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
    def __init__(self, channels: list[Channel], sources: list[Source]):
        self.channels = channels
        self.sources = sources

    def run(self, now: datetime, config: dict) -> int:
        """Run every source once; deliver what's due to every channel. Returns the
        number of deliveries made.

        Failures are isolated at every level — a failing source never stops the
        others, and a channel that fails to deliver never stops the rest. Dedup is
        per-channel, so each channel sends a given notification at most once per day."""
        sent = 0
        for src in self.sources:
            try:
                due = src.check(now, config.get(src.id, {}))
            except Exception as e:
                print(f"[warn] source {src.id!r} failed: {e}")
                continue
            for n in due:
                for ch in self.channels:
                    try:
                        if n.dedup_key and ch.already_sent(n.dedup_key, now):
                            continue
                        ch.send(n)
                        sent += 1
                    except Exception as e:
                        print(f"[warn] delivering {n.title!r} from {src.id!r} failed: {e}")
        return sent
