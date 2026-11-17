# Habitica setup standard for NoterPiper

**A structure anyone can follow so the nightly nudge is accurate, organised, and scalable.**

NoterPiper's Habitica plugin sends **one calm summary each night of what you still owe
today**. It can only be as good as the data behind it. Habitica gives every task
structured fields — *type*, *tags*, *priority*, *streak*, *checklist* — so the nudge
should read those, not guess from the wording of a title. This document is the standard:
set your Habitica up this way and the nudge "just works" for anyone, not just one person.

---

## 1. Know the three task types — and use the right one

Habitica has three types. They are **not** interchangeable; each carries different fields,
and the nudge treats each differently.

| Type | What Habitica models it as | Has "owed today"? | The nudge reads |
|---|---|---|---|
| **Daily** | A scheduled, recurring commitment | ✅ `isDue` + `completed` + `streak` | due-but-not-done → shown; long streak → 🔥 at-risk |
| **Habit** | A +/− behaviour to reinforce | ⚠️ ambiguous — **opt-in only** | shown **only if you tagged it** (and it's daily-reset & untapped) |
| **To-do** | A one-off finite task | optional due `date` | not completed → shown; past its date → overdue |

### The design in one line: progressive enhancement

> **Works out-of-the-box on *universal* fields; gets smarter when you add *your own* structure.**

Habitica's data is either **universal** (means the same for everyone — a daily's
`isDue`/`completed`/`streak`, a to-do's `date`, `priority`, `checklist`) or **personal**
(means different things to different people — `tags`, titles, notes). The nudge **never
guesses meaning from a title**; it reads universal fields by default, and layers your
personal structure (tags) on top when it's there:

- **Level 0 — zero setup:** shows what's owed (dailies due, to-dos open), grouped **by type**.
- **Level 1 — you tag:** grouped **by your tags** → real sections (Prayer, Work, Quran).
- **Level 2 — priority & checklists:** Hard tasks first, `2/3` progress shown.

Because it reads *fields*, not intent, it works even when someone "uses a daily as a
habit" — the daily still has `isDue`/`completed`, so it shows when owed.

### The golden rule
> **If you should do it every day (or on a schedule), make it a _Daily_ — not a Habit.**

Dailies are the only type with a true *"you still owe this today, and here's your streak"*
model, so they are the **backbone** of the nudge. A Habit has no "due date," so the nudge
can only ask *"tapped today?"* — and that's only meaningful if the habit's **reset
frequency is Daily** (which zeroes its counter each day). A habit set to weekly/monthly
reset is reinforcement, not a daily obligation, so the nudge **ignores it**.

*(This is read from the real `frequency` field — no guessing from the title.)*

---

## 2. Tags = your sections

A **tag is a category**, and each category becomes a **section** in the summary. You
choose the vocabulary — `prayer`, `quran`, `work`, `health`, `study`, anything.

- **One section tag per task.** The nudge groups tasks by that tag.
- **Invent a tag → invent a section.** No code change, ever.
- **Untagged tasks** still appear, under a catch-all **Other** — so nothing is silently
  dropped, and it's your cue to tag them.

This replaces title-guessing entirely: a task called `Quran Fajr` lands under **Quran**
because you tagged it `quran`, never under Prayers because its name happens to contain
"Fajr."

---

## 3. Hide what shouldn't be nagged

- Tag dividers, headers (`#### …`), and retired tasks **`Archived`** — the nudge skips
  anything tagged `Archived`.
- Markers you tap to *record* something (not tasks you *owe*) don't belong as nagged
  items — model those as a daily you complete, or leave them untagged/Archived.

---

## 4. Optional signals that make the nudge smarter

All read from Habitica's own fields — you don't have to use them, but they help:

| Signal | Habitica field | What the nudge does with it |
|---|---|---|
| **Urgency** | daily `streak` | a long unticked streak is flagged 🔥 **at-risk** and shown first |
| **Importance** | `priority` (Trivial / Easy / Medium / **Hard**) | Hard tasks can be surfaced above easy ones within a section |
| **Progress** | `checklist` | a part-done task can show `Surah Mulk · 2/3` instead of just the name |

---

## 5. What lands on your phone

One grouped message, built from the rules above:

> ### Nightly check-in
> 7 left before midnight · 2 at risk 🔥
>
> At risk · 2
> Surah Mulk · 53, 100 tasbeeh · 53
>
> Prayers · 4
> Zohar, Asr, Maghrib, Isha
>
> Quran · 1
> Quran Kareem
>
> Dhikr · 1
> 313 darood

- Sections are **your tags**, ordered: **at-risk 🔥 first**, then your sections, then **Other**.
- Each section is a capped comma-list (`+N more`) so it stays readable at any size.
- Everything tagged `Archived` is gone.

---

## 6. Quick-start checklist (hand this to anyone)

1. **Create tags** for your categories (`prayer`, `quran`, `work`, …).
2. **Make recurring commitments _Dailies_** and set their schedule.
3. For a **habit** you want nudged, set its **reset to Daily**.
4. **Tag every task** with exactly one section tag.
5. **Tag dividers / retired tasks `Archived`.**
6. *(Optional)* mark must-dos **Hard**; use **checklists** for multi-step tasks.

That's it. Follow this and the nudge categorises everything correctly with **zero guessing**.

---

## 7. How the plugin consumes this (for maintainers)

1. `GET /tags` → map tag id → name.
2. Collect **pending** items:
   - **Dailies**: `isDue and not completed`.
   - **Habits**: `frequency == 'daily' and up and counterUp == 0`.
   - **To-dos**: `not completed` (flag overdue by `date`).
   - Skip anything tagged `Archived`.
3. **Group by section tag**; untagged → `Other`.
4. **Rank**: at-risk streaks (`streak ≥ threshold`) first across all sections; within a
   section, higher `priority` first; then by streak.
5. Render capped sections with `+N more`; show `checklist` progress where present.

The hardcoded `PRAYERS` tuple and "contains a prayer word" matching are **removed** — all
categorisation is tag-driven and user-owned.
