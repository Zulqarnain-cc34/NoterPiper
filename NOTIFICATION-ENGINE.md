# NoterPiper as a Notification Engine — Architecture & Path Forward

> The direction: NoterPiper is a **serverless notification engine** — a small, stable
> core plus **pluggable sources**. Two plugins ship today (prayer reminders, Habitica
> nightly nudge); the engine is built so more can be added *without touching the core*.
> The model to aim for is how LangChain treats integrations: a clear interface, a
> registry, and plugins that simply plug in.

> **Status: implemented.** Phases 1–6 are done — the contracts, `NtfyChannel`, the
> `Engine`, both plugins, and the `run_engine.py` entry point are live in the codebase.
> The "today / gap" and "phase" sections below are kept as the **rationale**: the
> "today" columns describe the pre-refactor code (now removed), and the phases are the
> record of how it was built (Phase 7 — third-party discovery — is still deferred).

---

## 0. Scope — what we build now, and what we deliberately defer

**The goal (yours):** this is mainly for *you*. You will keep adding your own
notification types — prayer today, **gym** next, more later — and **adding one must
never mean rewriting the core.** Open-sourcing into a real third-party ecosystem is a
*maybe-later*: worth keeping possible, not worth building today.

So we draw the line on purpose — *capable, not over-built*:

**Build now** — the seam that pays off every single time you add a source:
- the `Notification` value object, the `Source` plugin interface, a simple registry, and the `Engine` loop;
- prayer and Habitica ported to plugins; **one** clean ntfy delivery (no duplication).
- Payoff: adding "gym reminders" later = write one ~30-line `Source` and register it. **Zero core changes.**

**Deliberately defer** — foundation kept, machinery not built; each can be added later
*without changing the `Source` interface or any existing plugin*:
- **Pluggable multi-channel delivery** (email / Telegram / …). You only use ntfy, so there is one `NtfyChannel` and no channel-registry. A second channel slots in behind the same seam later — additive, not a rewrite.
- **Third-party plugin discovery** (Python entry points). You are the only author today, so the registry is a plain list. Entry points slot in later behind the same `Source` interface.

The test for every decision below: *could you add a brand-new reminder type by writing
one small file, without editing anything that already works?* If yes, the seam is right.

---

## 1. How notification engines are actually built

Every serious notification system separates into **three decoupled layers**. Naming
them is half the battle:

| Layer | Also called | Responsibility | In NoterPiper |
|---|---|---|---|
| **Sources** | producers, triggers, plugins | Decide *what* to notify and *when* | prayer reminders, Habitica nudge |
| **Engine** | dispatcher, orchestrator, core | On each run, ask every source "anything due?", collect, route, de-duplicate | the new `engine` module |
| **Channels** | sinks, providers, transports | Decide *how* to deliver | ntfy today; email / Telegram later |

The golden rule that makes it an *ecosystem* and not a tangle:

> **The engine depends on interfaces, never on concrete plugins.**
> Plugins depend on the engine's interface, never on each other.

That is the **Dependency Inversion Principle** — and it is exactly what we are missing
today.

---

## 2. The core contracts (the interfaces)

Three small, stable types are the entire public surface a plugin author needs. In
Python these are `Protocol`s / `dataclass`es — zero dependencies, consistent with the
project's ethos.

```python
# engine/types.py — the common currency
@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    priority: str = "default"          # ntfy priority
    tags: tuple[str, ...] = ()
    dedup_key: str | None = None        # "send at most once" marker


# engine/plugin.py — what every source implements (the plugin contract)
class Source(Protocol):
    id: str                             # "prayer", "habitica" — also its config namespace
    def check(self, now: datetime, config: dict) -> list[Notification]:
        """Given the current time and this plugin's own config slice,
        return any notifications due right now (empty list = nothing)."""


# engine/channel.py — how notifications are delivered (a strategy)
class Channel(Protocol):
    def send(self, n: Notification) -> None: ...
    def already_sent(self, dedup_key: str) -> bool: ...
```

That is the whole interface. A plugin is "anything with an `id` and a `check()`." A
channel is "anything that can `send()` and remember what it already sent."

---

## 3. The engine (the orchestrator)

```python
# engine/engine.py
class Engine:
    def __init__(self, channel: Channel, sources: list[Source]):
        self.channel, self.sources = channel, sources

    def run(self, now: datetime, config: dict) -> int:
        sent = 0
        for src in self.sources:                       # iterate registered plugins
            for n in src.check(now, config.get(src.id, {})):
                if n.dedup_key and self.channel.already_sent(n.dedup_key):
                    continue                           # once-only guarantee lives here
                self.channel.send(n)
                sent += 1
        return sent
```

One loop. It knows nothing about prayers or Habitica — only about the `Source` and
`Channel` interfaces. Adding a plugin never changes this file (**Open/Closed
Principle**).

**Scheduling stays simple:** the engine runs on the existing ~2-minute trigger, and
each plugin decides internally whether anything is due (prayer: most runs; Habitica:
only at the nightly time). One trigger, one entry point — no per-plugin cron sprawl.

---

## 4. Where the project is lacking today (honest gap analysis)

The current code is two *programs*, not a plugin system. The seams are implicit:

| Gap | Today | Target |
|---|---|---|
| **No shared interface** | `schedule_prayers.py` and `notify.py` are separate scripts | both implement the `Source` contract |
| **No engine** | two workflows run two scripts | one engine runs all registered sources |
| **Duplicated delivery** | `send_live()` *and* `send()` both build ntfy calls | one `NtfyChannel.send()` |
| **De-dup trapped in one place** | `already_sent()` lives inside the prayer script | a `Channel` capability any plugin gets free |
| **Flat config** | `config.json` mixes everyone's settings | namespaced: `plugins.prayer`, `plugins.habitica` |
| **No registry** | plugins are "whatever script the workflow calls" | an explicit registry the engine iterates |

None of this is wrong *as an app* — it's just not yet an *engine*. The refactor below
closes each gap one PR at a time.

---

## 5. The target shape

```
config.json
  └─ plugins:
       prayer:   { city, offsets, ... }      ← each plugin owns its config slice
       habitica: { nudge_time, enabled }

run_engine.py            ← one entry point
  └─ Engine(channel = NtfyChannel(topic),
            sources = REGISTRY)              ← [PrayerSource(), HabiticaSource()]
        .run(now, config)
             │
             ├─ PrayerSource.check()   → [Notification("Maghrib", ...)]
             └─ HabiticaSource.check() → [Notification("3 left before midnight", ...)]
                        │
                        └─ NtfyChannel.send()  (with already_sent de-dup)
```

A plugin registers itself into the `REGISTRY` (an explicit list, or a `@register`
decorator). Later, third-party plugins can register via Python **entry points** — the
same mechanism LangChain and pytest use for external integrations.

---

## 6. How a plugin looks (the contract in practice)

```python
# plugins/prayer.py
class PrayerSource:
    id = "prayer"
    def check(self, now, config):
        timings, _ = fetch_timings(config["city"], config["country"], config["method"])
        due = []
        for prayer in PRAYERS:
            remind = reminder_dt(prayer, timings, now, config["reminders"])
            if is_due(remind, now):
                due.append(Notification(
                    title=prayer, body=f"Time to pray · ends {...}",
                    priority="max", tags=("mosque",), dedup_key=f"prayer:{prayer}:{now:%F}"))
        return due

# plugins/habitica.py
class HabiticaSource:
    id = "habitica"
    def check(self, now, config):
        if not due_now(now, config["nudge_time"]):   # only at nudge time
            return []
        ...
        return [Notification(title, body, priority, tags, dedup_key=f"habitica:{now:%F}")]
```

Both are ~30 lines. The prayer and Habitica *logic already exists* — the refactor
mostly **moves it behind the interface**, it doesn't rewrite it.

---

## 7. The path forward — phased, each step a PR

Each phase is independently testable and mergeable, so `main` (and your live cron)
is never broken mid-flight. **Phases 1–6 are the "for you" core** — after them, a new
source (gym, etc.) is a one-file job. **Phase 7 is the "if it takes off" step** —
deferred until you actually open-source.

1. **Core contracts** — `Notification`, `Source`, `Channel`. Pure types + tests. *(no behavior change)*
2. **`NtfyChannel`** — extract the two scripts' ntfy calls + `already_sent` into one channel. Tests.
3. **`Engine`** — the registry + `run()` loop. Tested against a fake channel + fake sources.
4. **`PrayerSource`** — port `schedule_prayers` behind the interface; its old tests now drive the plugin.
5. **`HabiticaSource`** — port `notify` behind the interface.
6. **One entry point + namespaced config** — `run_engine.py`; migrate `config.json` to `plugins.*`; update the workflow to call the engine. *(This is the only step that touches the live trigger — ship it last, verify on the branch first.)*
7. **(Only when you open-source) Plugin guide + entry-point discovery** — document the contract and add entry-point loading so third parties can ship plugins. Deferred until there's real demand; nothing in phases 1–6 has to change to add it.

---

## 8. Principles we are applying (the vocabulary)

- **Separation of Concerns** — sources decide *what*, the engine decides *when to route*, channels decide *how*.
- **Dependency Inversion** — the engine depends on `Source`/`Channel` abstractions, not concretes.
- **Open/Closed** — add plugins/channels without editing the engine.
- **Strategy pattern** — channels are interchangeable delivery strategies.
- **Registry / plugin discovery** — explicit list → decorator → entry points (progressive).
- **Value object** — `Notification` is immutable data, the lingua franca between layers.
- **Loose coupling, high cohesion** — each plugin is self-contained; the engine is thin.

---

## 9. What this unlocks

- **New sources** (weather, calendar, RSS, a standup reminder) with zero engine changes.
- **New channels** (email, Telegram, SMS) — notifications flow unchanged.
- **Third-party plugins** — anyone can publish a NoterPiper plugin and register it.
- **The same quiet, free, serverless promise** — the engine is tiny; plugins are optional.

> NoterPiper stops being "a prayer app with a Habitica feature" and becomes **a free,
> serverless notification engine that happens to ship two excellent plugins.**
