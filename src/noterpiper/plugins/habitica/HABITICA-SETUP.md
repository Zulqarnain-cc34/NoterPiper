# Getting the most out of the nightly nudge

**You don't have to set your Habitica up any particular way.** The nudge reads Habitica's
own structured fields — so it works with whatever you already have, however you use the
app. This page is just two optional tweaks that make the summary nicer, plus the one thing
that genuinely matters.

## It already works out of the box

The nudge reads fields, never the wording of a title:

- **Dailies** — shown when due and not done; a long `streak` is flagged 🔥 **at-risk**.
- **To-dos** — shown until completed; past their due `date` → **(overdue)**.
- **Habits** — shown when they're daily-reset "good" (+) habits you haven't tapped today.

Untagged tasks are **never dropped** — they fall back to a plain **Dailies / To-dos /
Habits** section. So a brand-new user with zero tags still gets a correct summary.

## The one rule that actually matters

> If you owe it on a schedule, make it a **Daily** — not a Habit.

Only dailies carry a real "you still owe this today, and here's your streak" model, so they
are the backbone. A Habit has no due date, so the nudge can only ask "tapped today?" — and
that's only meaningful for a **daily-reset** habit (read from the real `frequency` field,
not guessed). Weekly/monthly habits are reinforcement, not a daily obligation, so they're
left out.

## Two optional tweaks

**1. Tags → named sections.** Tag a task and it groups under that tag's name (e.g. `work`
→ a **Work** section, `health` → **Health**) instead of the plain type fallback. The
task's **first** tag is used as its section, so if you want predictable grouping, keep one
"section" tag per task. Invent a tag, invent a section — no code change. Use whatever words
fit your life.

**2. Hide what shouldn't be nagged.** Tag anything `Archived` to hide it. Visual dividers —
`#### Morning` markdown headers or `-------` separator rows — are **skipped automatically**,
tagged or not.

## What lands on your phone

```
Nightly check-in

6 to do before midnight · 1 at risk 🔥

At risk · 1
Meditate · 53

Overdue · 1
Pay rent

Health · 2
Exercise, Drink water

Dailies · 1
Journal

+ 3 open to-dos in your backlog
```

Ordered by **urgency**: at-risk 🔥 streaks first, then overdue, then your sections (hardest
tasks first), with open to-dos not due tonight collapsed to a single backlog count. The
headline counts only what's owed tonight. Each section is a capped comma-list (`+N more`)
so it stays readable at any size.

---

*For maintainers:* the exact fields and response shapes the plugin reads are in
[HABITICA-SCHEMA.md](HABITICA-SCHEMA.md) — that's the authoritative read-contract.
