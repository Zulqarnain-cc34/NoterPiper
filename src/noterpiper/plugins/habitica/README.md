<div align="center">

# 🌙 Habitica nightly nudge

**A NoterPiper plugin — one calm end-of-day check-in.** *(optional)*

*If you track habits in Habitica, this sends one calm summary each night of everything
still open — unlogged habits, due dailies, and due or overdue to-dos — with at-risk
streaks flagged first.*

</div>

---

## What it does

Once a night, at the time you set, it reads your Habitica tasks and sends **one grouped
message** covering everything still open — unlogged prayer habits, due-but-not-done
dailies, and **due or overdue to-dos**. It leads with what's urgent (at-risk streaks,
overdue to-dos) and caps long lists with `+N more`, so it stays readable whether you
have 3 items or 30. One nudge, never a stream.

## What lands on your phone

> ### Nightly check-in
> 8 left before midnight · 2 at risk 🔥
>
> At risk · 2
> Surah Mulk · 52, Tasbeeh · 41
>
> To-dos · 3
> Submit report (overdue), Call dentist, Buy milk
>
> Dailies · 4
> Walk, Water, Read, Exercise, +1 more
>
> Prayers · 1
> Fajr

On a quiet day it's just as short — e.g. `1 left before midnight` with a single line.

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

All of these are editable from the phone config page — no JSON needed.

| Key | Meaning |
|---|---|
| `nudge.time` | When to send it (24-hour local time) |
| `nudge.enabled` | Turn it on/off without removing it |
| `nudge.streak_risk` *(optional)* | Streak length that flags a daily "at risk" — defaults to 7 |
| `nudge.show_todos` *(optional)* | Include due/overdue to-dos — defaults to true |
| `nudge.show_dailies` *(optional)* | Include due dailies (and their at-risk flag) — defaults to true |
| `nudge.show_prayers` *(optional)* | Include unlogged prayer habits — defaults to true |
| `nudge.window` *(optional)* | Minutes the nudge stays "due" — defaults to 5 |

## Security

- **Read-only.** The Habitica client only ever issues `GET` requests — it can never
  modify or delete anything in your account.
- **Credential, not shipped.** The API token lives only as a GitHub **Secret** (or a
  git-ignored `.env`); it is never committed, printed, or logged.
- **No task content in logs.** Your task names go to your phone, never into the logs.

## How it works

At the set time (once per day), the plugin fetches your tasks and builds one message:
**at-risk streaks and overdue to-dos first**, then to-dos, dailies, and prayers — each
a capped comma-list that ends in `+N more` when it's long. A stable title gives it
robust **once-per-day** delivery under the frequent engine runs. The on-demand
"send now" button forces it immediately, bypassing the time gate. Code:
[`__init__.py`](__init__.py) — the `HabiticaSource` class satisfies NoterPiper's
`Source` contract (`id = "habitica"`, `check(now, config) → [Notification]`).
