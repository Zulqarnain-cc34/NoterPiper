# Design decisions — the Habitica nudge

Why the nightly nudge behaves the way it does. Each entry is a deliberate choice, often
with an alternative that was considered and rejected — so a future change is a decision,
not an accident. (Project-wide choices live in the top-level [DECISIONS](../../../../DECISIONS.md).)

---

## What the summary is for

**One notification, ruthlessly prioritised — not a task list.** At the end of the day there
is exactly one ping, so it leads with what hurts to miss and summarises the rest. Order is
fixed by urgency: **at-risk streaks → overdue → due-today sections → a backlog count.**
*Rejected:* ordering sections by size (biggest first) — it buried the one urgent thing under
a big trivial list.

**The headline counts only what's owed tonight.** "6 to do before midnight" means 6.
*Rejected:* counting the whole open-to-do backlog in the headline — it produced scary,
dishonest numbers like "35 left before midnight" for someone with a big someday list.

## What's included, and what isn't

**Read structured fields, never the wording of a title.** Categorisation is by Habitica's
own fields and the user's tags. *Rejected:* the original title-matching (a hardcoded
`PRAYERS` list, "contains a prayer word") — it only worked for one person's data.

**Works for any setup; tags only make it nicer.** Universal fields (`isDue`, `completed`,
`streak`, `date`) work with zero setup; untagged tasks fall back to `Dailies`/`To-dos`/
`Habits` sections. *Why:* a plugin anyone installs cannot impose a convention on them.

**Untagged habits fall back like everything else.** *Rejected:* the earlier "habits are
opt-in, untagged ones are dropped" — it made habits silently vanish while dailies/to-dos
fell back, an inconsistency users couldn't see.

**To-dos not owed tonight collapse to a backlog count.** Undated or future-dated to-dos
become `+N open to-dos in your backlog`, listed only as a number. *Rejected:* listing every
open to-do (a prior choice) — for a user with a large backlog it flooded the one notification
and conflated "due today" with "someday".

**Overdue to-dos get their own urgent block.** Being *late* is the most important thing to
say. *Rejected:* a quiet `(overdue)` suffix buried inside a tag section.

**Within a section, Hard tasks lead** (Habitica's `priority`). *Why:* surface the big rocks,
not the trivial ones, inside the space a single notification has.

## Recurrence & task types

**Dailies of any frequency are handled by `isDue`.** Weekly/monthly/yearly/everyX scheduling
is already computed server-side into `isDue`; the plugin trusts it and never parses a
schedule itself. *Why:* re-deriving Habitica's calendar would be fragile and redundant.

**Habits are daily-reset only.** Only daily-reset "good" (+) habits that are untapped today
are shown. *Rejected:* including weekly/monthly habits — they reset on their own cycle with
no *nightly* deadline, so nudging for them every night would be strictly noise. Down-only
"bad habits" are also out (they're "don't do X", not an obligation).

**Rewards are never shown.** They aren't "owed".

## Quiet mode, extra pushes, send-now

**Quiet mode filters at collection, with two deliberate exceptions.** Type switches and
the tag whitelist drop tasks before any summary sees them — so every push (evening,
morning counts, weekly totals) agrees. The exceptions: **untagged tasks always pass the
whitelist** (a whitelist narrows topics; silently orphaning unlabeled tasks would look
like data loss) and **overdue to-dos always show** (being late outranks being quiet).
*Rejected:* letting the filters mute the backlog counter only partially — "notify_todos
off" must mean the nudge never mentions to-dos at all, except the urgent overdue block.

**Morning is counts-only, never names.** `3 dailies · 2 habits · 1 at risk 🔥` is a
glance, not a list — the detail belongs to the evening. *Rejected:* a shortened task list
— it duplicated the evening nudge at the wrong time of day.

**Each push has its own title → its own once-a-day dedup.** Evening, morning, and weekly
use distinct stable titles as dedup keys, so each fires independently at most once a day
under the ~2-min engine.

**A forced send ("Send now") is exactly one push.** `force_kind` picks the format
(evening / morning / weekly); dedup is bypassed; a corrupt weekly state falls back to the
full summary rather than eating the button press. *Rejected:* forcing everything that's
enabled — the doubled traffic tripped ntfy's rate limit and a button tap delivered
nothing (observed in production, 2026-11-17).

**The weekly digest can never cost the nightly nudge.** Its whole code path is guarded;
a bad day name or corrupt state file logs a warning and skips the digest. Its week state
is plugin-owned (`weekly.py`, `.noterpiper_state/`) and honestly shallow on ephemeral CI
runners — the docs say so rather than pretending.

## Hiding, grouping, delivery

**Two things stay the user's choice: which tag is a section, and what to hide.** Everything
else is automatic. The **first** tag is the section; an **`Archived`** tag hides a task.
*Why:* these two genuinely can't be inferred — there's no field that says "this tag is my
section" or "hide this".

**`#### …` / `-----` dividers are skipped natively**, tagged or not. *Rejected:* requiring
the `Archived` tag on dividers — the `####` header is a near-universal Habitica pattern, so
an untagged one would otherwise get nagged as a real task.

**A bad token is surfaced, not swallowed.** A `401`/`403` sends one once-a-day "Habitica
sign-in failed" notification. *Rejected:* letting it fail the workflow (the alert email
doesn't reach the phone and it would disrupt the other plugins' run) and *rejected:* staying
silent (the user would never know why the nudge stopped).

**One message per day, deduped by a stable title.** The title equals the dedup key, so the
channel delivers it at most once a day under the ~2-min engine.

## On the vendored API spec

**The community OpenAPI is a thin, write-oriented contract**, so [HABITICA-SCHEMA.md](HABITICA-SCHEMA.md)
— not the spec — is the authoritative read-contract. The spec's GET responses are untyped and
its `Task` schema omits the read-only fields the nudge actually reads (`completed`, `isDue`,
`tags`, `counterUp/Down`). It's kept for endpoints/auth/params reference only.
