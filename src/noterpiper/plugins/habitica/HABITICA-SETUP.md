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

**1. Tags → named sections.** Tag a task and it groups under that tag's name (e.g. `prayer`
→ a **Prayer** section) instead of the plain type fallback. The task's **first** tag is
used as its section, so if you want predictable grouping, keep one "section" tag per task.
Invent a tag, invent a section — no code change.

**2. Hide what shouldn't be nagged.** Tag anything `Archived` to hide it. Visual dividers —
`#### Morning` markdown headers or `-------` separator rows — are **skipped automatically**,
tagged or not.

## What lands on your phone

```
Nightly check-in

7 left before midnight · 2 at risk 🔥

At risk · 2
Surah Mulk · 53, tasbeeh · 53

Prayers · 4
Zohar, Asr, Maghrib, Isha

Quran · 1
Quran Kareem
```

Sections are your tags, ordered: at-risk 🔥 first, then your tag sections, then the type
fallbacks. Each section is a capped comma-list (`+N more`) so it stays readable at any size.

---

*For maintainers:* the exact fields and response shapes the plugin reads are in
[HABITICA-SCHEMA.md](HABITICA-SCHEMA.md) — that's the authoritative read-contract.
