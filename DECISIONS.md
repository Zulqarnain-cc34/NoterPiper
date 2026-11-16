# Decisions

Why Muezzin is built the way it is, and the notable changes along the way.
For how the pieces fit together, see [ARCHITECTURE](ARCHITECTURE.md).

---

## The shape of it

**Serverless, on free parts.** GitHub Actions is the clock and the compute,
ntfy.sh delivers the push, Aladhan gives prayer times, Habitica (optional) gives
your habits. Nothing to host, nothing to pay for, built to run for years untouched.

**One file holds every setting.** Location, per-prayer timings, and the nudge all
live in a single `config.json`. One place to change things — and the one thing the
phone page edits.

**Zero runtime dependencies.** The jobs are pure Python standard library; the phone
page is plain HTML/JS with no build step. Nothing can rot or break the chain.

**One bad input can't break a run.** A wrong city, a typo'd setting, a provider
outage — each is caught and either falls back to a sane default or fails loudly
(an email), never a silent stop. Prayer reminders and the nudge are independent.

---

## Notable changes

### How reminders are delivered

Reminders are **live**: a job reads your settings fresh and fires each reminder the
moment it's due, so a change you make takes effect within minutes.

- Timing lands within ~2 minutes of the target (it can drift to ~5 if a run is late).
- A free external timer ([cron-job.org](https://cron-job.org)) triggers the job every
  couple of minutes via GitHub's `workflow_dispatch` — GitHub's own `cron` can stall
  on a quiet repo, so it isn't relied on. Setup instructions are in [SETUP](SETUP.md), step 3.
- Each reminder fires exactly once — a 20-minute due window plus ntfy's message cache
  catch a late or skipped run without ever double-sending.

### Reminder timings are bounded to each prayer's window

A reminder only makes sense *inside* its prayer — between when that prayer begins
and when its window ends. The phone page reads today's times and caps each
timing accordingly, so a setting can never land outside the prayer it belongs to.

### Settings move to the phone

A small page on GitHub Pages edits `config.json` directly (through GitHub's API,
with a personal token kept only in your browser). The repository is public so the
page can read settings without a login — but it carries no secrets: the ntfy topic
and any Habitica token stay as private GitHub Secrets.
