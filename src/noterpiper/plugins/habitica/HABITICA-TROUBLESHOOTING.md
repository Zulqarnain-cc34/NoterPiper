# Troubleshooting & FAQ

Most "it's doing the wrong thing" turns out to be a deliberate rule. This maps each
symptom to the cause and the fix.

> **Fastest way to test:** the three **Send now** buttons on the config page (🌙 evening ·
> 🌅 morning · 📊 weekly) each fire that push immediately, bypassing every time gate — so
> you can see exactly what each would send with your real data.

## I got no notification at all

Work down this list:

1. **Habitica nudge turned off** — check the toggle on the config page.
2. **Not subscribed to your ntfy topic** — open the ntfy app and subscribe to the topic in
   your `NTFY_TOPIC` secret. No subscription, no delivery.
3. **Wrong credentials** — if your token/user-id is bad you'll actually get a **"Habitica
   sign-in failed"** notification instead of silence (see below). Silence means it's one of
   the above, or…
4. **Nothing was owed** — if every due task is done you get a calm
   `All done today — everything is logged. 🌙`, not nothing.
5. **It wasn't the set time yet** — it only sends within a few minutes of your `time`
   setting. Use **Send now** to test outside that window.

## I got "Habitica sign-in failed"

Your `HABITICA_API_TOKEN` or `HABITICA_USER_ID` is wrong or expired. Update those secrets.
(This ping is sent at most once a day so it doesn't nag.)

## It says "All done" but I still have tasks

A task is only "owed tonight" if it's genuinely due and not done. Yours is probably:

- **Not due today** — a weekly/monthly/yearly daily on an off day (Habitica's `isDue` is
  false), so it isn't owed tonight.
- **Already completed** today.
- **Tagged `Archived`**, or a **`#### …` / `-----` divider** — both are skipped.
- An **undated or future to-do** — those aren't owed tonight; they're the backlog count.

## A whole type (or a tagged task) is missing

Check **quiet mode** on the config page: a switched-off type (`Dailies` / `Habits` /
`To-dos`) is dropped from every push, and a **tag whitelist** hides any task whose first
tag isn't on the list. Two deliberate exceptions: **untagged tasks always pass** the
whitelist, and **overdue to-dos always show** regardless of either filter.

## The morning briefing has no task names

By design — it's counts only (`3 dailies · 2 habits · 1 at risk 🔥`), a glance at the
day's shape. The 🌙 evening summary is the one with names and sections.

## The weekly digest only reflects today

Expected on GitHub Actions: the runner's disk is wiped between runs, so the week's saved
state only survives within one run and the digest shows the digest-day's snapshot. The
format and stats are real; full week-long accumulation needs a persistent machine.

## The weekly digest never arrives

It's **off by default** — enable it on the config page and check its **day** and **time**.
Like every push it fires only within a few minutes of the set time on the set day; 📊
Send now previews it any time.

## A task I don't care about keeps showing

Tag it **`Archived`** to hide it, or — if it's a visual separator — name it with a markdown
header (`#### Morning`) or a rule (`------`); those are skipped automatically.

## My habit never appears

Only **daily-reset "good" (+)** habits show, and only if you **haven't tapped it today**.
Deliberately left out: weekly/monthly habits (they reset on their own cycle — no nightly
deadline) and down-only "bad habits" (`-` only). Tagging doesn't change this.

## Tasks are under the wrong section

The **first** tag on a task is its section. Reorder the task's tags in Habitica, or keep a
single "section" tag per task. Untagged tasks fall back to `Dailies` / `To-dos` / `Habits`.

## The count is low / my to-dos aren't listed

By design: to-dos with **no due date** or due **later** are collapsed into
`+N open to-dos in your backlog` and **excluded from the headline count**, so the number
reflects only what's actually owed before midnight. Give a to-do today's date to make it a
listed item.

## It's too long / I can't see everything

Each section caps at a few names with `+N more`. The nudge is a summary, not a task list —
open Habitica for the full detail.

## Nothing about rewards or my gold

Rewards aren't "owed," so they're never in the nudge. It only covers dailies, to-dos, and
habits.

---

## What it reads, and where it goes

- **Read-only.** It only ever `GET`s your tasks and tags — it never changes anything in
  Habitica.
- **Only metadata.** It reads structured fields (type, due date, streak, tags, priority),
  not the meaning of your titles.
- **Your token stays put** — it lives in your deployment's secrets, is never logged, and
  the summary is sent only to **your** ntfy topic.
