# Writing a NoterPiper plugin

NoterPiper is a tiny notification **engine** with a plugin ecosystem. The architecture is
**Sources → Engine → Channels**: a **Source** (a plugin) decides *what* to tell you and
*when*; the engine routes it; a **Channel** delivers it (ntfy, webhook, …). The engine
depends only on the `Source` / `Channel` *contracts*, never on any concrete plugin — so
**adding a plugin never touches the engine** (dependency inversion + open/closed).

A plugin is **one class**. This guide shows how to write one. The smallest working example
lives in [`examples/plugin_template/`](examples/plugin_template/) — copy it to start.

---

## 1. The contract

A Source satisfies this protocol ([`engine/plugin.py`](src/noterpiper/engine/plugin.py)):

```python
class Source(Protocol):
    id: str                                                   # short, stable, unique
    def check(self, now: datetime, config: dict) -> list[Notification]: ...
```

- **`id`** — e.g. `"weather"`. Also the **key for your config slice** (you get `config` for
  *your* plugin only). Keep it stable; it's used for dedup grouping and config.
- **`check(now, config)`** — called every engine run (~every few minutes) with a
  timezone-aware `now`. Return the notifications **due right now**; return `[]` when
  nothing is due. Pure and testable — all time comes in via `now`.

## 2. The Notification you return

([`engine/types.py`](src/noterpiper/engine/types.py) — an immutable value object.)

```python
Notification(
    title,            # str — ASCII only (ntfy puts it in an HTTP header; emoji there breaks delivery)
    body,             # str — the message (emoji fine here)
    priority="default",   # min | low | default | high | max | urgent
    tags=(),          # ntfy tags → icons, e.g. ("mosque",) or ("crescent_moon",) for 🌙
    dedup_key=None,   # set a stable key → delivered at most once/day; None → always delivered
)
```

> **Emoji rule:** put emoji in the **body** or via **tags**, never in the **title**.

## 3. A minimal plugin

```python
from noterpiper.engine import Notification

class WeatherSource:
    id = "weather"
    def check(self, now, config):
        if not config.get("enabled", False):
            return []
        # … fetch / compute what's due now …
        return [Notification("Weather", "Rain after 3pm — take an umbrella",
                             priority="default", tags=("umbrella",), dedup_key="weather")]
```

Fire only when something is **due** — gate on the time and on `config`. Reuse the
`_due_now(now, "HH:MM")` helper pattern from the template or the prayer/habitica plugins.

## 4. Where it goes — and auto-discovery

Put your package under **`src/noterpiper/plugins/<your_id>/`** with an `__init__.py` that
defines your Source class. That's it — the engine **auto-discovers** every Source in that
folder ([`engine/registry.py`](src/noterpiper/engine/registry.py)); there is **no list to
edit**. Drop the folder in, and it runs on the next cycle.

## 5. Config

The engine hands your `check()` **your slice**: `config` is already `config[your_id]`.
Users set it in `config.json` under your id:

```json
{ "weather": { "enabled": true, "city": "Lahore" } }
```

For now, to give your slice defaults and wire it to the phone config page, add a few lines
in [`scripts/run_engine.py`](scripts/run_engine.py) (`build_config`) and
[`settings.py`](src/noterpiper/settings.py). *(A per-plugin config schema that removes this
last manual step is on the roadmap — your `check()` won't change.)*

Talking to an external API? Keep it **read-only**, keep credentials in **secrets / `.env`**
(never printed or logged), and **respect the service's rate limits** (cache, back off on
`429`). See how the Habitica client does it: [`api.py`](src/noterpiper/api.py),
[`HABITICA-SCHEMA.md`](src/noterpiper/plugins/habitica/HABITICA-SCHEMA.md).

## 6. Channels — you don't touch them

You never deal with delivery. The engine fans your Notification out to **every enabled
channel** (ntfy, webhook, …). Want a new delivery target? That's a **Channel**, not a
Source — a separate small class with `send()` / `already_sent()` (see
[`channels/`](src/noterpiper/channels/)).

## 7. Test it

TDD. Your Source is pure (time comes in via `now`), so mock any API and assert on the
returned Notifications — see [`examples/plugin_template/test_example_source.py`](examples/plugin_template/test_example_source.py).

## 8. Shipping it — repo, not fork

Pick one of three, none of which touches the engine:

- **Pip package (the standard).** Keep it in **your own repo** that depends on `noterpiper`,
  and register your Source as an **entry point** — then anyone `pip install`s it and it
  **auto-registers** (the pytest `pytest11` model). In your plugin's `pyproject.toml`:

  ```toml
  [project.entry-points."noterpiper.plugins"]
  weather = "noterpiper_weather:WeatherSource"
  ```

  The deployer adds your package to the install step (`pip install noterpiper-weather`), and
  `discover_all` finds it via `importlib.metadata`. No code, no app, no engine changes.

- **Drop-in folder** (no packaging). Copy your plugin package into a deployment's
  `src/noterpiper/plugins/` (or add it as a `git submodule`); the `pkgutil` scan picks it up.
  Good for a quick personal plugin on the serverless/fork deployment.

- **Official plugin** → open a PR adding your folder under `src/noterpiper/plugins/`; it joins
  the curated core.

**Never fork the engine to add a plugin.** Forking is for running your own deployment, not for
authoring — forks can't be combined and drift from the core. Target the `Source` contract,
and the engine stays untouched.

## 9. Contract & compatibility (what you can rely on)

The `Source` contract — `id`, `check(now, config) → [Notification]`, plus optional `defaults`
and `wants_location` — is **stable within a major version.** NoterPiper follows
[SemVer](https://semver.org): a breaking change to the contract bumps the **major** version.

- **Pin it** in your plugin's dependencies: `noterpiper>=1,<2`.
- Check it at runtime if you like: `noterpiper.__version__` / `noterpiper.PLUGIN_API_MAJOR`.
- New *optional* fields (like `defaults` was) are **minor** — they never break an existing
  plugin, because the engine reads them with `getattr(..., default)`.

So a plugin written against `1.x` keeps working across every `1.x` engine release.

## 10. Make your plugin run in a serverless deployment

A pip plugin still needs to be **installed** where the engine runs. On the GitHub-Actions
deployment, a deployer lists their plugins in **`plugins-requirements.txt`** at the repo root;
the workflows `pip install -r` it before each run (skipped if the file is absent). So shipping
a plugin to a deployment is: add one line to that file.

---

That's the whole model: **one class, one contract, auto-discovered, delivered everywhere.**
If writing the plugin felt easy, the architecture did its job.
