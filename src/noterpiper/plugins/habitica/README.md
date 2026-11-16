<div align="center">

# 🌙 Habitica nightly nudge

**A NoterPiper plugin — one calm end-of-day check-in.** *(optional)*

*If you track habits in Habitica, this sends a single summary each night of what's
still unlogged and which streaks are at risk. The prayer plugin works without it.*

</div>

---

## What it does

Once a night, at the time you set, it reads your Habitica tasks and sends **one grouped
message** — unlogged prayer habits and due-but-not-done dailies, with at-risk streaks
flagged. One nudge, never a stream.

## What lands on your phone

> ### Nightly check-in
> 3 left before midnight
>
> Prayers · 1
> Fajr
>
> Dailies · 2
> Surah Mulk · 52 🔥
> Morning walk

---

## Setup

The engine is set up once in the main **[SETUP](../../../../SETUP.md)**. This plugin is
**optional** and needs two things:

1. **Two secrets** — add `HABITICA_API_TOKEN` and `HABITICA_USER_ID` (both from
   Habitica → *Settings → Site Data*) as repo secrets.
2. **Its settings** in `config.json`:

   ```json
   { "nudge": { "time": "21:30", "enabled": true } }
   ```

If the secrets aren't set, the plugin simply does nothing — nothing breaks.

## Settings reference

| Key | Meaning |
|---|---|
| `nudge.time` | When to send it (24-hour local time) |
| `nudge.enabled` | Turn it on/off without removing it |
| `nudge.window` *(optional)* | Minutes the nudge stays "due" — defaults to 5 |

## Security

- **Read-only.** The Habitica client only ever issues `GET` requests — it can never
  modify or delete anything in your account.
- **Credential, not shipped.** The API token lives only as a GitHub **Secret** (or a
  git-ignored `.env`); it is never committed, printed, or logged.
- **No task content in logs.** Your task names go to your phone, never into the
  (public) Actions logs.

## How it works

At the set time (once per day), the plugin fetches your tasks, groups what's still
outstanding, flags streaks at risk, and returns one notification. A stable title gives
it robust **once-per-day** delivery under the frequent engine runs. The on-demand
"send now" button forces it immediately, bypassing the time gate. Code:
[`__init__.py`](__init__.py) — the `HabiticaSource` class satisfies NoterPiper's
`Source` contract (`id = "habitica"`, `check(now, config) → [Notification]`).
