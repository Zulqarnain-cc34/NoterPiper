<div align="center">

# 🌙 Habitica nightly nudge

**A NoterPiper plugin — one calm end-of-day check-in.** *(optional)*

*One calm summary each night of what you still owe today — grouped by **your own tags**,
with at-risk streaks and overdue to-dos flagged first. It reads Habitica's structured
fields, never the wording of a title, so it works for anyone.*

</div>

---

## What it does

Once a night, at the time you set, it reads your Habitica tasks + tags and sends **one
grouped message** of what's still owed today:

- **Dailies** due today and not done — any schedule (daily / weekly / monthly / yearly).
- **To-dos** due today or overdue; ones not due tonight become a backlog count.
- **Habits** — daily-reset "good" (+) habits you haven't tapped today.

Each item appears under its **tag** as a section (`Work`, `Health`, `Study`, … — your own
words); untagged tasks fall back to `Dailies` / `To-dos` / `Habits`, so it works with zero
setup for any layout and gets sharper as you tag. The one message is ordered by urgency —
at-risk 🔥 → overdue → your sections (hardest first) → a backlog count — and caps long lists
with `+N more`. Tasks tagged **`Archived`** and `####`/`-----` dividers are skipped. One
nudge, never a stream.

> **Works out of the box; two optional tweaks make it nicer** (tags for named sections, an
> `Archived` tag to hide things) — see **[HABITICA-SETUP.md](HABITICA-SETUP.md)** (and the
> exact data shape in **[HABITICA-SCHEMA.md](HABITICA-SCHEMA.md)**).

## What lands on your phone

> ### Nightly check-in
> 6 to do before midnight · 1 at risk 🔥
>
> At risk · 1
> Meditate · 53
>
> Overdue · 1
> Pay rent
>
> Health · 2
> Exercise, Drink water
>
> Dailies · 1
> Journal
>
> + 3 open to-dos in your backlog

On a quiet day it's just as short — e.g. `1 to do before midnight` with a single line.
When everything's logged: `All done today — everything is logged. 🌙`

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

Then **tag your tasks** in Habitica (see the data standard above). If the secrets aren't
set, the plugin simply does nothing — nothing breaks.

## Settings reference

Editable from the phone config page — no JSON needed.

| Key | Meaning |
|---|---|
| `nudge.time` | When to send it (24-hour local time) |
| `nudge.enabled` | Turn it on/off without removing it |
| `nudge.streak_risk` *(optional)* | Streak length that flags a daily "at risk" — defaults to 7 |
| `nudge.window` *(optional)* | Minutes the nudge stays "due" — defaults to 5 |

Categorisation is driven entirely by your **tags**, not by settings — add a tag in
Habitica and a new section appears in the nudge, no config change.

## Security

- **Read-only.** The Habitica client only ever issues `GET` requests (tasks + tags) — it
  can never modify or delete anything in your account.
- **Credential, not shipped.** The API token lives only as a GitHub **Secret** (or a
  git-ignored `.env`); it is never committed, printed, or logged.
- **No task content in logs.** Your task names go to your phone, never into the logs.
- **Plays by Habitica's rules.** Well under the 30-requests/60s limit, sends the required
  `X-Client` header, and the code is public (per Habitica's
  [API guidelines](https://github.com/HabitRPG/habitica/wiki/API-Usage-Guidelines)).

## How it works

At the set time (once per day) it fetches your tasks (`GET /tasks/user`) and tags
(`GET /tags`), keeps what's **owed today** per Habitica's structured fields
(`isDue`/`completed`/`streak`, `date`, habit `frequency`/`counter`), groups them by tag,
and builds one message: **at-risk streaks first**, then your tag sections, then the
type fallbacks — each a capped comma-list. A stable title gives robust **once-per-day**
delivery under the frequent engine runs; the "send now" button forces it immediately.
Code: [`__init__.py`](__init__.py) — the `HabiticaSource` class satisfies NoterPiper's
`Source` contract (`id = "habitica"`, `check(now, config) → [Notification]`).
