# Plugins & Channels

NoterPiper is a small **engine** with two kinds of plug-in parts:

- **Sources** (plugins) decide *what* to notify, and *when*.
- **Channels** decide *how* to deliver.

The engine asks every source "anything due now?", then fans each notification out to
every channel. It depends only on the `Source` and `Channel` *interfaces* — so you add
a new reminder type or a new delivery method **without touching the engine**.

```
   SOURCES (plugins)          THE ENGINE                 CHANNELS           Your phone /
   decide WHAT to send   →    ask each source       →    deliver it    →    Discord / email …
   • prayer                   "anything due now?",        • ntfy
   • habitica                 dedupe, fan out             • webhook
```

---

## What ships today

| Kind | Name | What it does | Docs |
|---|---|---|---|
| Source | **prayer** | Rings for each of the five daily prayers | [readme](src/noterpiper/plugins/prayer/README.md) |
| Source | **habitica** | Optional evening nudge + morning brief & weekly digest | [readme](src/noterpiper/plugins/habitica/README.md) |
| Channel | **ntfy** | Push to an ntfy topic (dedups via its cache) | [readme](src/noterpiper/channels/README.md) |
| Channel | **webhook** | POST to any URL — Discord, Slack, Home Assistant, … | [readme](src/noterpiper/channels/README.md) |

---

## The two contracts

Everything a plug-in author touches is three tiny types in `noterpiper.engine`:

```python
@dataclass(frozen=True)
class Notification:          # the thing to deliver
    title: str; body: str
    priority: str = "default"; tags: tuple[str, ...] = (); dedup_key: str | None = None

class Source(Protocol):      # a plugin
    id: str
    def check(self, now, config) -> list[Notification]: ...

class Channel(Protocol):     # a delivery method
    def send(self, notification) -> None: ...
    def already_sent(self, dedup_key, now) -> bool: ...   # best-effort; False if you can't check
```

---

## Write a source (a new reminder type)

Say you want **gym** reminders. One file:

```python
# src/noterpiper/plugins/gym/__init__.py
from ...engine import Notification

class GymSource:
    id = "gym"                                   # also its config-slice key
    def check(self, now, config):
        if is_gym_time(now, config):
            return [Notification("Gym", "Leg day 💪", priority="high")]
        return []
```

Register it in `scripts/run_engine.py` (`SOURCES = [PrayerSource(), HabiticaSource(), GymSource()]`)
and give it a slice in `build_config`. The engine never changes.

**Dedup:** set `dedup_key` to a stable string (e.g. the title) and ntfy will deliver it
at most once per day. Leave it `None` to send every time it's due.

---

## Write a channel (a new delivery method)

```python
# src/noterpiper/channels/telegram.py
from .. import net
class TelegramChannel:
    def __init__(self, token, chat_id): ...
    def send(self, notification):
        net.request(f"https://api.telegram.org/bot{self.token}/sendMessage",
                    data=..., headers={"Content-Type": "application/json"})
    def already_sent(self, dedup_key, now):
        return False                              # no cache → best-effort
```

Add it to the `channels` list in `run_engine.py` (usually gated on its secret being set).
Each notification then also goes there.

---

## How it all runs

`scripts/run_engine.py` (triggered every ~2 min) loads settings, builds each plug-in's
config slice, and runs `Engine(channels, sources).run(now, config)`. Failures are
isolated at every level — one source or channel breaking never stops the others. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the full picture.
