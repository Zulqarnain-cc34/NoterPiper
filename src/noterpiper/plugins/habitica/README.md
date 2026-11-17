<div align="center">

# 🌙 Habitica nudges

**A NoterPiper plugin — your Habitica day, pushed to your phone.** *(optional)*

*One calm evening summary of what you still owe — grouped by **your own tags**, at-risk
streaks and overdue to-dos first — plus an optional morning briefing and weekly digest.
It reads Habitica's structured fields, never the wording of a title, so it works for anyone.*

</div>

---

## Three pushes, each with its own switch

| Push | Default | What it says |
|---|---|---|
| **🌙 Evening — "Nightly check-in"** | **on**, 21:30 | The full summary: everything still owed today, grouped and ordered by urgency |
| **🌅 Morning — "Habitica morning briefing"** | off | Counts only — `3 dailies · 2 habits · 1 at risk 🔥` — a glance at the day ahead, no task names |
| **📊 Weekly — "Habitica weekly digest"** | off | Once a week: items due, best streak, an at-risk callout |

Each is deduped independently, so it arrives **at most once per day** no matter how often
the engine runs. The config page's three **Send now** buttons push any of them immediately
— one tap, one push, every time gate bypassed.

## What the evening summary contains

- **Dailies** due today and not done — any schedule (daily / weekly / monthly / yearly);
  a long streak still unticked is flagged 🔥 **at-risk** and leads the message.
- **To-dos** — overdue ones get their own urgent block; due **today** appear as a normal
  section; undated / future ones collapse to `+N open to-dos in your backlog`.
- **Habits** — daily-reset "good" (+) habits you haven't tapped today.

Each item appears under its **first tag** as a section (`Work`, `Health`, … — your own
words); untagged tasks fall back to `Dailies` / `To-dos` / `Habits`. Order is fixed by
urgency — at-risk 🔥 → overdue → your sections (hardest first) → backlog count — and long
lists cap with `+N more`. Tasks tagged **`Archived`** and `####`/`-----` dividers are
skipped.

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
> + 3 open to-dos in your backlog

When everything's logged: `All done today — everything is logged. 🌙`

## Quiet mode — notify only what you choose

Three type switches and a tag whitelist narrow every push:

- `notify_dailies` / `notify_habits` / `notify_todos` — drop a whole type.
- `tag_whitelist` — e.g. `["deen"]` (or the string `"deen, quran"`): only tasks carrying
  one of these tags are included. Case-insensitive. **Untagged tasks always pass** — a
  whitelist narrows topics, it never silently orphans unlabeled tasks.
- **Overdue to-dos always show**, whatever the filters say — being late outranks being quiet.

## Settings

All of it lives on the phone config page — no JSON needed. The `habitica` section of
`config.json`:

| Key | Default | Meaning |
|---|---|---|
| `enabled` / `time` | `true` / `"21:30"` | The evening nudge's switch and clock |
| `streak_risk` | `7` | Streak length that flags a daily 🔥 at-risk |
| `notify_dailies` / `notify_habits` / `notify_todos` | `true` | Quiet mode type switches |
| `tag_whitelist` | `null` | Only these tags (list or comma string); `null` = all |
| `morning` | `{"enabled": false, "time": "06:00"}` | The morning briefing |
| `weekly` | `{"enabled": false, "day": "Sunday", "time": "19:00"}` | The weekly digest |
| `window` | `5` | Minutes a nudge stays "due" past its set time |

Sections are driven entirely by your **tags** — add a tag in Habitica and a new section
appears, no config change.

> **Weekly digest caveat:** it aggregates state saved across the week in
> `.noterpiper_state/` — on GitHub's throwaway runners that file only lives for one run,
> so there the digest reflects the digest-day's snapshot. On any persistent machine it
> genuinely accumulates the week.

## Setup

The engine is set up once in the main **[SETUP](../../../../SETUP.md)**. This plugin is
**optional** and needs only **two secrets**: `HABITICA_API_TOKEN` and `HABITICA_USER_ID`
(both from Habitica → *Settings → Site Data*). If they aren't set, the plugin simply does
nothing — nothing breaks.

> Two optional tweaks make the summary nicer (tags for named sections, an `Archived` tag
> to hide things) — see **[HABITICA-SETUP.md](HABITICA-SETUP.md)**. Something off?
> **[HABITICA-TROUBLESHOOTING.md](HABITICA-TROUBLESHOOTING.md)**. Why it behaves this way:
> **[HABITICA-DECISIONS.md](HABITICA-DECISIONS.md)**. Field shapes (for maintainers):
> **[HABITICA-SCHEMA.md](HABITICA-SCHEMA.md)**.

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

On each engine run it fetches your tasks (`GET /tasks/user`) and tags (`GET /tags`),
collects what's **owed today** per Habitica's structured fields (`isDue`/`completed`/
`streak`, due `date`, habit `frequency`/`counter`, `priority`) through the quiet-mode
filters, then emits whichever pushes are due: the evening summary, the counts-only morning
brief, and — when its day/time hits — the weekly digest built from the week's saved
snapshots. Every push's title equals its dedup key, which is how the ntfy channel keeps
each one to once a day. A forced run ("Send now", `force_kind` = `evening` / `morning` /
`weekly`) sends exactly **one** push of the chosen format with dedup bypassed.
Code: [`__init__.py`](__init__.py) (the `HabiticaSource` class — NoterPiper's `Source`
contract) and [`weekly.py`](weekly.py) (the digest's week state).
