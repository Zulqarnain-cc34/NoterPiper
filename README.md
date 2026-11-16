# 🕌 Habitica Salah

Prayer-time reminders and a nightly check-in for your Habitica prayers and
recitations — delivered to your phone. **Serverless, free, zero dependencies.**

## What it does

- **Prayer reminders** — your phone rings at each of the 5 prayer times (e.g. 30 min
  before a prayer ends), using live prayer times for your city.
- **One nightly nudge** — a single end-of-day notification: what's still unlogged and
  which streaks are at risk. Nothing else — notifications are kept deliberately minimal.

It runs on GitHub's infrastructure on a schedule, so no server and no always-on
computer are required.

## How it works

A morning job fetches today's prayer times and **pre-schedules** the reminders on
[ntfy](https://ntfy.sh) at exact times; a nightly job sends the nudge. GitHub Actions
is the scheduler, ntfy is delivery, Habitica/Aladhan are the data — and because ntfy
handles exact-time delivery, GitHub's loose cron timing is irrelevant.

Full design and diagram: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## Setup

Ten minutes, once — see **[SETUP.md](SETUP.md)**. In short: subscribe to an ntfy
topic on your phone, add three GitHub secrets (`HABITICA_API_TOKEN`,
`HABITICA_USER_ID`, `NTFY_TOPIC`) and a `PRAYER_CITY` variable, and enable Actions.

## Configuration

- **Reminder timings** — edit `reminders.json` (`before_end` / `after_start` minutes
  per prayer). No code; editable from GitHub's web UI.
- **City** — the `PRAYER_CITY` variable (`Lahore`, `Islamabad`, …).

## Privacy & security

Read-only Habitica access. The API token is a GitHub secret — never committed,
printed, or exposed (`.env` and `data/` are git-ignored). The repo is private.
