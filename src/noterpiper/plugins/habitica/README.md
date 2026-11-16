# 🌙 Habitica nightly nudge — a NoterPiper plugin *(optional)*

One calm end-of-day summary of what's still unlogged and which streaks are at risk —
if you track habits in [Habitica](https://habitica.com). Completely optional: the
prayer plugin works perfectly without it.

## What it sends

> ### Nightly check-in
> 3 left before midnight
>
> Prayers · 1
> Fajr
>
> Dailies · 2
> Surah Mulk · 52 🔥
> Morning walk

One grouped message, once a night, at-risk streaks flagged with 🔥.

## Its configuration

```json
{ "time": "21:30", "enabled": true }
```

- **time** — when to send the nudge (24-hour local).
- **enabled** — turn it on/off without removing it.

Plus two secrets (read-only): `HABITICA_API_TOKEN` and `HABITICA_USER_ID`.

## How it works

At the set time, once a day, the plugin reads your Habitica tasks (**GET only — it can
never change your account**), groups what's still outstanding (unlogged prayer habits
and due-but-not-done dailies), flags streaks at risk, and returns one notification. A
stable title gives it robust **once-per-day** delivery under the engine's frequent runs.

## The code

`HabiticaSource` implements NoterPiper's `Source` contract: `id = "habitica"` and
`check(now, config) → list[Notification]`. See [`__init__.py`](__init__.py).
