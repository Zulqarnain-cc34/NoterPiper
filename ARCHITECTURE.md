# Architecture — built to run for years, easy to extend

A plain map of how this works, why it won't break, and how to add new nudges.

## The shape

```
GitHub Actions (free, scheduled)         ← runs everything; no server, no computer
   │
   ├─ prayers.yml   → schedule_prayers.py → ntfy (pre-scheduled, exact-time reminders)
   ├─ notify.yml    → notify.py           → ntfy (daily "nudges")
   ├─ dashboard.yml → sync_from_api.py     → GitHub Pages (dashboard)
   └─ keepalive.yml → tiny monthly commit  → keeps the schedules alive forever

src/habitica_etl/        the shared library
   net.py        ← ONE resilient network layer (retries + backoff) everything uses
   api.py        ← read-only Habitica API client (built on net)
   config.py     ← settings, timezone, which tasks are in scope
   loaders/transform/database/analytics/validation ← data + dashboard pipeline

scripts/   schedule_prayers.py · notify.py · sync_from_api.py · selftest.py
reminders.json   ← you edit this to change reminder timings
```

## Why it won't break (the 5-year design)

1. **The critical path has zero dependencies.** Prayer reminders and nudges use
   **only the Python standard library** — no pandas/pip packages to rot or break
   on an update. (Only the optional *dashboard* uses extra packages; if those
   ever break, your reminders are unaffected.)
2. **Every network call retries.** `net.py` wraps all HTTP with retries +
   exponential backoff, doesn't retry genuine 4xx (bad token), and surfaces a
   clear error otherwise. A blip in Habitica/Aladhan/ntfy self-heals.
3. **Partial failure never cascades.** If one prayer send or one nudge throws,
   the others still run (`try/except` per item) — you still get the rest.
4. **No server to maintain.** Free, managed services only: GitHub Actions
   (compute), ntfy (push), Aladhan (prayer times). The **keepalive** workflow
   stops GitHub from pausing the schedules after 60 idle days.
5. **It fails loudly, not silently.** GitHub emails you if a run fails, so you
   always know if something needs a look.
6. **Pinned, stable integrations.** Action versions are pinned (`@v4`); the APIs
   used are long-stable public endpoints.

## How to extend it

**Add a nudge** (e.g. for to-dos or a specific daily) — the whole point:
1. In `scripts/notify.py`, write a function that takes `tasks` and returns lines:
   ```python
   def nudge_stale_todos(tasks):
       old = [t["text"] for t in tasks.get("todos", []) if is_old(t)]
       return ["📋 Stale to-dos: " + ", ".join(old)] if old else []
   ```
2. Add it to the `NUDGES` list. Done — it runs daily, and if it ever errors it
   won't affect the other nudges.

**Change reminder timings** → edit `reminders.json` (`before_end` / `after_start`
minutes per prayer). Takes effect next run.

**Change city** → set the `PRAYER_CITY` variable (`Lahore`, `Islamabad`, …).

## Testing

- **Offline unit tests** (`tests/`) lock the timing math and data decoding — run
  `python -m pytest`.
- **Live self-test** (`scripts/selftest.py`) proves ntfy delivers at the exact
  second and shows today's planned reminder times.
