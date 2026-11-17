# Habitica task schema (reference)

The exact data NoterPiper gets from Habitica, so the shape never has to be re-guessed.
Captured live from a real account (identifiers + personal text redacted).

## Where it comes from

| Call | Returns |
|---|---|
| `GET /api/v3/tasks/user` | all active tasks in one flat array; each has a `type` field |
| `GET /api/v3/tags` | the tag dictionary: `[{ "id": "<uuid>", "name": "<tag name>" }, …]` |
| `GET /api/v3/user?userFields=preferences` | the day boundary — see [Day boundary](#the-day-boundary-why-isdue--completed-can-be-trusted) |

Auth headers: `x-api-user: <USER_ID>`, `x-api-key: <API_TOKEN>`. **Read-only (GET) only.**
The client splits the flat array by `type` into **`habits / dailys / todos`**
(see [`api.py`](src/noterpiper/api.py)). Habitica also returns `reward` tasks — NoterPiper
**ignores rewards**; only these three types matter.

> ⚠️ A task's `tags` field is an array of **tag UUIDs**, not names. Resolve them against
> `GET /tags`.

---

## Fields common to all three types

| Field | Type | Meaning |
|---|---|---|
| `type` | `"habit" \| "daily" \| "todo" \| "reward"` | which kind of task |
| `text` | string | the task's name (free text — do **not** parse meaning from it) |
| `notes` | string | user's free-text note (often empty) |
| `tags` | string[] | **tag UUIDs** (resolve via `/tags`) |
| `priority` | `0.1 \| 1 \| 1.5 \| 2` | difficulty: Trivial / Easy / Medium / Hard |
| `value` | number | Habitica's health/colour score (red ≪ 0 … gold ≫ 0) — how well you keep up |
| `attribute` | `"str" \| "int" \| "con" \| "per"` | which character stat it trains |
| `byHabitica` | bool | created by Habitica itself |
| `id` / `_id` | uuid | task id *(redacted here)* |
| `userId` | uuid | owner *(redacted here)* |
| `createdAt` / `updatedAt` | ISO-8601 | timestamps |
| `reminders` | array | per-task reminder times — see [Nested structures](#nested-structures--context-inside-a-task) |
| `challenge` / `group` | object | shared-task linkage — see [Nested structures](#nested-structures--context-inside-a-task) |

---

## Habit

Reinforcement behaviour with `+` and/or `−`. **No `isDue`, no `completed`, no `streak`.**
"Done today?" is only inferable when `frequency == "daily"` (the counter resets each day).

| Habit-only field | Type | Meaning |
|---|---|---|
| `up` / `down` | bool | is the `+` / `−` button enabled |
| `counterUp` / `counterDown` | int | taps since the last reset (`frequency`) |
| `frequency` | `"daily" \| "weekly" \| "monthly"` | **counter reset period** |
| `history` | array | past scores — see [Nested structures](#nested-structures--context-inside-a-task) |

```json
{
  "type": "habit",
  "text": "<task name>",
  "notes": "",
  "tags": [],
  "value": 1,
  "priority": 1,
  "attribute": "str",
  "up": true,
  "down": true,
  "counterUp": 0,
  "counterDown": 0,
  "frequency": "daily",
  "createdAt": "2026-11-16T01:22:43.258Z",
  "updatedAt": "2026-11-16T20:12:58.996Z"
}
```

---

## Daily

A scheduled recurring commitment — the backbone of the nudge. Has the full "owed today
+ streak" model.

| Daily-only field | Type | Meaning |
|---|---|---|
| `isDue` | bool | **scheduled for today** |
| `completed` | bool | **ticked off today** → owed = `isDue && !completed` |
| `streak` | int | consecutive completions (drives 🔥 at-risk) |
| `frequency` | `"daily" \| "weekly" \| "monthly" \| "yearly"` | repeat unit |
| `everyX` | int | "every X" of that unit |
| `repeat` | object | `{m,t,w,th,f,s,su: bool}` — which weekdays (weekly) |
| `daysOfMonth` / `weeksOfMonth` | int[] | monthly schedules |
| `startDate` | ISO-8601 | when the schedule begins |
| `nextDue` | ISO-8601[] | upcoming due dates (next ~6) |
| `yesterDaily` | bool | was it due yesterday (for streak grace) |
| `checklist` | array | sub-items (see below) |
| `collapseChecklist` | bool | UI-only |
| `history` | array | past due/completion — see [Nested structures](#nested-structures--context-inside-a-task) |

```json
{
  "type": "daily",
  "text": "<task name>",
  "notes": "<free text>",
  "tags": [],
  "value": 40.42,
  "priority": 1,
  "attribute": "str",
  "frequency": "weekly",
  "everyX": 1,
  "startDate": "2026-09-04T19:00:00.000Z",
  "repeat": { "m": true, "t": true, "w": true, "th": true, "f": true, "s": true, "su": true },
  "streak": 52,
  "daysOfMonth": [],
  "weeksOfMonth": [],
  "nextDue": ["2026-11-17T19:00:00.000Z", "2026-11-18T19:00:00.000Z"],
  "yesterDaily": true,
  "completed": false,
  "isDue": true,
  "collapseChecklist": false,
  "checklist": [],
  "createdAt": "2026-09-05T18:44:42.814Z",
  "updatedAt": "2026-11-16T20:12:58.939Z"
}
```

---

## To-do

A one-off, finite task. Optional due date; never "resets."

| To-do-only field | Type | Meaning |
|---|---|---|
| `completed` | bool | done (completed to-dos drop off the active list) |
| `date` | ISO-8601 \| `null` | **optional** due date; `null` = no due date |
| `checklist` | array | sub-items (see below) |
| `collapseChecklist` | bool | UI-only |

```json
{
  "type": "todo",
  "text": "<task name>",
  "notes": "<free text>",
  "tags": [],
  "value": -44.17,
  "priority": 1,
  "attribute": "str",
  "date": null,
  "completed": false,
  "collapseChecklist": false,
  "checklist": [],
  "createdAt": "2026-10-21T10:54:23.157Z",
  "updatedAt": "2026-11-16T20:12:58.973Z"
}
```

---

## Nested structures & context (inside a task)

These live **inside** each task object — richer context than the top-level flags.

### `history[]` — past completions (the consistency signal)

A habit and a daily each keep a per-day history. **Shapes differ by type:**

```json
// habit history entry — how many times you scored it that day
{ "date": 1794792213461, "value": 1, "scoredUp": 1, "scoredDown": 0 }

// daily history entry — whether it was due, and whether you did it
{ "date": 1794906067151, "value": 20.1, "isDue": true, "completed": true }
```

`date` is epoch **milliseconds**. This is the raw material for context like
"completed 5 of the last 7 due days" or "missed yesterday" — beyond just the current
`streak`. To-dos have no history.

### `checklist[]` — sub-tasks (dailies & to-dos)

```json
{ "id": "<uuid>", "text": "<sub-task>", "completed": false }
```

Progress = `sum(completed) / len(checklist)` → e.g. `2/3`.

### `reminders[]` — per-task reminder times (often empty)

```json
{ "id": "<uuid>", "time": "2026-11-16T05:00:00.000Z", "startDate": null }
```

### `challenge{}` / `group{}` — shared-task linkage (empty for solo use)

```json
// challenge: {} when the task isn't part of a Challenge; otherwise:
{ "id": "<uuid>", "taskId": "<uuid>", "shortName": "<challenge name>", "broken": null }

// group: party/Guild assignment — empty-ish for a solo account:
{ "completedBy": {}, "assignedUsers": [] }
```

NoterPiper doesn't use `reminders` / `challenge` / `group` today, but they're here so
nothing is a surprise later.

## Tags (`GET /tags`)

```json
[ { "id": "8f2c…-uuid", "name": "prayer" }, { "id": "a71b…-uuid", "name": "Archived" } ]
```

A task references these by `id` in its `tags` array; map id → name to get the label.

## The day boundary — why `isDue` / `completed` can be trusted

Habitica doesn't roll over at literal midnight; it rolls at the user's **`dayStart`**
hour (`GET /user → preferences.dayStart`, `0`–`23`; e.g. `0` = midnight, `3` = 3 AM),
in their `preferences.timezoneOffset`. Habitica computes `isDue`, `completed`, and
`streak` **server-side relative to that boundary** — so the plugin can **trust those
fields directly** and never has to recompute "is it today?" itself. (That's why the
nudge keys off `isDue && !completed` rather than parsing dates.)

---

## What the plugin actually reads

| Purpose | Field(s) |
|---|---|
| Is it owed today? | daily `isDue && !completed` · to-do `!completed` · habit `frequency=="daily" && counterUp==0` |
| Urgency | daily `streak` (🔥 at-risk) |
| Category / section | `tags` → `/tags` names |
| Importance (later) | `priority` |
| Progress (later) | `checklist` |
| Consistency context (later) | `history` (e.g. "did 5 of last 7 due days"), `value` (struggling) |
| Due / overdue (to-do) | `date` |

Everything else (`attribute`, `reminders`, `nextDue`, `challenge`, `group`, …) is ignored.
