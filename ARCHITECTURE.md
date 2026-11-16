# Architecture — built to run for years, easy to extend

A plain map of how this works, why it won't break, and how to add new nudges.

## The shape

```
GitHub Actions (free, scheduled)         ← runs everything; no server, no computer
   │
   ├─ prayers.yml   → schedule_prayers.py → ntfy (pre-scheduled, exact-time reminders)
   ├─ notify.yml    → notify.py           → ntfy (one nightly nudge)
   └─ keepalive.yml → tiny monthly commit  → keeps the schedules alive forever

src/habitica_etl/        the shared library (3 tiny files, stdlib only)
   net.py        ← ONE resilient network layer (retries + backoff) everything uses
   api.py        ← read-only Habitica API client (built on net)
   config.py     ← settings, timezone, which recitations the nudge watches

scripts/   schedule_prayers.py · notify.py · selftest.py
reminders.json   ← you edit this to change reminder timings
```

## Why it won't break (the 5-year design)

1. **Zero dependencies.** The entire app uses **only the Python standard
   library** — nothing from pip to rot or break on an update. (Only the test
   suite uses `pytest`.)
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

## Notification philosophy — keep it minimal

**Notifications are precious. More is worse.** If the phone buzzes for everything,
you tune it all out — including the prayer reminders that matter. So the default
is deliberately small: **5 prayer reminders + one gentle nightly nudge.** Don't
add more unless something is genuinely worth interrupting the day for.

## How to extend it (sparingly)

**Change reminder timings** → edit `reminders.json` (`before_end` / `after_start`
minutes per prayer). Takes effect next run.

**Change city** → set the `PRAYER_CITY` variable (`Lahore`, `Islamabad`, …).

**Add a nudge** — only if it clears the "worth a buzz?" bar. It's a small function
in `scripts/notify.py` returning lines, added to the `NUDGES` list; a failing
nudge never affects the others. That's the mechanism — but restraint is the rule.

## Testing

- **Offline unit tests** (`tests/`) lock the reminder-timing math — run
  `python -m pytest`.
- **Live self-test** (`scripts/selftest.py`) proves ntfy delivers at the exact
  second and shows today's planned reminder times.
