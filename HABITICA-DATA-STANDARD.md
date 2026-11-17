# Habitica data standard — tag your tasks, don't make the nudge guess

**Status:** design / proposal (not yet implemented in the plugin)
**Scope:** habits + dailies (to-dos later — same idea)

## Why this exists

Today the nightly nudge **guesses categories from task names** — it hardcodes that a
habit called `Fajr`, `Zohar`, `Asr`, `Maghrib`, or `Isha` means "a prayer," and lumps
them into a **Prayers** section. You never wrote the word "prayer" anywhere; the plugin
assumed it. That guessing is fragile:

- `Quran Fajr` contains "Fajr" → it was wrongly counted as a *prayer*.
- A future `Fajr workout` would pollute your prayers too.
- Headers like `#### Quran` would print literally if they ever came due.

**The fix:** *you* label each task with a **tag**, and the nudge groups by that tag.
No parsing, no assumptions. A tag is a structured signal; a name is just text.

## The principle

> **One task → one section tag.** The tag decides which section it appears under.

- The tag is the source of truth for "what kind of thing is this."
- Task **names stay human** (`Surah Mulk`, `100 tasbeeh fatima`) — the tag does the sorting.
- **Notes are optional** and only for you; the plugin never needs them.

## Your tag vocabulary (the sections)

Grounded in your actual tasks. Create these tags in Habitica, then tag each task:

| Tag | Nudge section | Your tasks that belong here |
|---|---|---|
| `prayer` | **Prayers** | Fajr · Zohar · Asr · Maghrib · Isha · Qaza 2 fajar |
| `quran` | **Quran** | Quran Fajr · Quran Kareem · Surah Mulk · Quran Every Jummah |
| `dhikr` | **Dhikr** | 11 Times Muhammad · 500 La hawla wala quwwata · 100 tasbeeh fatima · 313 darood |
| `sadaqa` | **Sadaqa** | Sadaqa |
| `Archived` *(you already have it)* | *(hidden)* | `#### Quran`, `#### Namaz & Jammat - archive`, retired tasks |

> You can add more sections later just by inventing a tag (`sunnah`, `health`, …) and
> tagging tasks with it — the nudge picks it up automatically. No code change.

## The rules

1. **Every habit and daily gets exactly one section tag** from the vocabulary above.
2. **`Archived` means "ignore me"** — the nudge skips anything tagged `Archived`.
   Use it for `####` dividers and retired tasks.
3. **Untagged tasks** still appear, but under a catch-all **Other** section — that's your
   signal that something needs a tag (nothing is ever silently dropped).
4. Multiple tags are fine; the nudge only reads the **section** tags it knows.

## How the nudge will use it

1. Fetch your tags (`GET /tags`) and map each task's tag IDs to names.
2. Find the **pending** tasks as it does now — a habit that's **untapped today**, a daily
   that's **due and not done**.
3. **Group those by section tag** → one block per section:
   `Prayers`, `Quran`, `Dhikr`, `Sadaqa`, (`Other`).
4. **Skip** anything tagged `Archived`.
5. **At-risk streaks** stay a cross-cutting flag (🔥, shown first) regardless of section —
   urgency is about streaks, not category.

This replaces the hardcoded `PRAYERS` list and the "contains a prayer word" matching
entirely. `Quran Fajr` lands under **Quran** (because you tagged it `quran`), never under
Prayers — no assumptions left.

## Going forward — the standard for any new task

When you create a habit or daily, before you save it:

- [ ] Give it a clear, human **name**.
- [ ] Add **one section tag** (`prayer` / `quran` / `dhikr` / `sadaqa` / …).
- [ ] If it's a divider or retired, tag it **`Archived`** instead.

That's it — three seconds, and the nudge categorizes it perfectly with zero guessing.

## One-time migration

1. In Habitica, create the tags: `prayer`, `quran`, `dhikr`, `sadaqa`.
2. Tag your existing habits + dailies per the table above.
3. Tag the two `####` dividers as `Archived`.

## Open question for later (not part of this standard)

Your `Quran Fajr` **habit** is really a *marker* ("I recited"), while `Quran Kareem` /
`Surah Mulk` **dailies** are the actual tasks. Tagging fixes *where* the habit shows
(Quran, not Prayers). Whether an untapped habit-marker should **nag at all** — or only
the daily should — is a separate tweak we can make once the tag sections are in place.
