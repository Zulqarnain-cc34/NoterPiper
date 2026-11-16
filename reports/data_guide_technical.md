# Technical Data Guide — Habitica Tracking (pipeline/assistant reference)

**Purpose:** the technical counterpart to `data_guide.md`. The human guide says
*what each thing means*; this says *what type of data it is, how Habitica stores
it, how to decode it, and the edge cases*. Same section order as the human guide.
Keep this updated as each section is added. The owner does not read this file.

> Old archived data (pre-16 Nov 2026 hand-note era, the original Namaz & Jamaat
> daily + 1400/X note reconstruction) is documented separately in
> `task_definitions.md`. This file covers the **new, correctly-structured** era.

---

## Cross-cutting facts (apply to everything)

- **Timezone:** history timestamps are **UTC** (epoch ms in JSON). Convert to
  **Asia/Karachi (UTC+5)**. Day boundary = **midnight PKT** (`dayStart = 0`).
  Rollover/cron entries (~00:40 PKT) settle the **previous** day.
- **Habitica task types & history:**
  - **Daily** history entry = `{date, value, completed, isDue}` (verified from
    the real export). `completed` is the direct done/miss flag — prefer it over
    value-delta inference. Multiple entries/day occur (cron + completion).
  - **Habit** history = `{date, value}` with direction inferred from the value
    delta sign (↑ = ➕, ↓ = ➖). **The exact multi-tap-per-day recording format is
    UNVERIFIED** (no habit existed in the first export) — confirm from the first
    real habit export before trusting per-tap granularity.
  - **Habit counter** (the ➕N/➖N display) **resets daily** at cron (configurable
    weekly/monthly); the **history is permanent** and not cleared by the reset.
  - **Checklists** have **no timestamped history** → never use for tracked data.
- **Counts are derived, never hand-stored.** "How many times done" = count the
  taps from history. **Total-days = `today − createdAt`** (computed).
- **One outcome per (task, day):** for habits, if a day has multiple taps, resolve
  to a single outcome — **last tap of the day wins** (handles mis-taps/corrections).

---

## 1. Prayers — Namaz & Jamaat
- **Habitica type:** 5 **Habits**, each with ➕ and ➖ enabled —
  `Fajr · Zohar · Asr · Maghrib · Isha`.
- **Encoding (per prayer, per day):** ➕ = **Jamaat** (congregation), ➖ = **prayed
  at home/alone**, **no tap = missed**. Three categories, tracked individually.
- **Decode:** resolve each prayer to one outcome/day (last tap wins). Direction
  from value-delta sign on the habit history.
- **Derived:** per prayer over time → counts of Jamaat/home/missed, time-of-day,
  reconstructed streaks. Day roll-ups (all-5-prayed, all-5-jamaat) are optional,
  not primary.
- **Edge cases:** multi-tap → last wins; counter resets daily (display only);
  mosque attendance is a real signal now (no longer lossy like the old note).
- **TODO:** verify habit multi-tap history format from first real export.

## 2. Daily Recitations
- **Habitica type:** 5 **Dailies** (every day, binary) —
  `Surah Mulk · 500 Lā ḥawla · 100 Tasbeeh Fatima · 11 Times Muhammad · Quran Hakeem`.
- **Decode:** `completed = true` → done that day; due-but-not-completed → miss
  (use `completed`/`isDue`, not value deltas).
- **Derived:** days done/missed, current & longest streak, consistency. Total-days
  computed. Drop the `1400/X` hand note.

## 3. Weekly Recitations (Fridays)
- **Habitica type:** 2 **Dailies**, schedule **Weekly → Friday** —
  `313 Darood · Quran Every Jummah`.
- **Decode:** only due on Fridays (`isDue`); completed on a due Friday → done.
  Non-Friday days are not-due (never a miss).
- **Derived:** Fridays done/missed, Friday streak.

> **Scope (locked 16 Nov 2026):** the project is exactly **three sections** —
> Prayers, Daily Recitations, Weekly Recitations. Qaza 2 Fajr, #### Quran, and
> Sadaqa are **out of scope** (owner keeps them as personal notes only; not
> tracked or analysed). To-dos are **out of scope** entirely.

---

## Decode rules summary (for the future pipeline)
1. Parse task type → apply the matching decode (Daily: `completed`/`isDue`;
   Habit: value-delta direction + last-tap-per-day).
2. Convert all timestamps UTC → PKT; assign day by midnight-PKT boundary; shift
   ~00:40 cron entries to the previous day.
3. Derive all counts/totals from taps; never read a hand-written tally as truth.
4. Reconstruct streaks from the day sequence; treat a broken streak as display
   only — never as lost data.
