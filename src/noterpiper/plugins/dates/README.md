<div align="center">

# 📅 Date reminders

**A NoterPiper plugin — birthdays, bills, expiries, never missed.** *(optional)*

*A simple list of dates; your phone reminds you a few days ahead. No account, no API —
just dates and arithmetic.*

</div>

---

## What it does

Once a day, at the time you set, it checks a list of dated items and reminds you about
any coming up within your **lead window**. A date written `MM-DD` **recurs every year**
(a birthday); written `YYYY-MM-DD` it's a **one-off** (a bill, a passport) that stops
once it's past.

## What lands on your phone

> ### Electricity bill
> in 2 days

> ### Mom's birthday
> today

---

## Setup

No secrets, no API. Just its settings in `config.json`:

```json
{
  "dates": {
    "enabled": true,
    "time": "09:00",
    "lead_days": 3,
    "items": [
      { "label": "Mom's birthday", "date": "03-15" },
      { "label": "Passport expiry", "date": "2027-06-01" },
      { "label": "Electricity bill", "date": "2026-11-19" }
    ]
  }
}
```

## Settings reference

| Key | Meaning |
|---|---|
| `dates.enabled` | Turn it on/off |
| `dates.time` | When to send the daily check (24-hour local time) |
| `dates.lead_days` | How many days ahead to start reminding — defaults to 3 |
| `dates.items[]` | `{ "label": "...", "date": "MM-DD" or "YYYY-MM-DD" }` |

This plugin ships a **`config_schema`**, so its controls are rendered on the config page
automatically — no app code. See [PLUGIN-AUTHORING](../../../../PLUGIN-AUTHORING.md).

## How it works

Each run (once a day, at `time`), it computes each item's next occurrence and reminds you
when it's within `lead_days` (counting down `in N days` → `today`). A stable per-item
title gives robust once-a-day delivery. Code: [`__init__.py`](__init__.py) — `DateRemindersSource`
satisfies the `Source` contract (`id = "dates"`, `check(now, config) → [Notification]`).
