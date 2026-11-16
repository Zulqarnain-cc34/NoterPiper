# 🕌 Prayer reminders — a NoterPiper plugin

Rings your phone for each of the five daily prayers — **Fajr, Zohar, Asr, Maghrib,
Isha** — at the moment *you* choose within each prayer's own window. Prayer times are
calculated live for your city (via the free [Aladhan](https://aladhan.com) API).

## What it sends

> ### 🕌 Maghrib
> Time to pray · ends 5:03 PM

One ring, at max priority, when the prayer is due.

## Its configuration

The plugin reads its own slice of settings:

```json
{
  "city": "Istanbul",
  "country": "Turkey",
  "method": "13",
  "reminders": {
    "Fajr":    { "after_start": 30 },
    "Maghrib": { "before_end": 30 }
  }
}
```

- **city / country** — your location (or set privately via `PRAYER_CITY` / `PRAYER_COUNTRY`).
- **method** — the calculation method id ([full list](https://aladhan.com/calculation-methods)).
- **reminders** — per prayer, pick one:
  - `{ "after_start": N }` — N minutes **after** the prayer begins.
  - `{ "before_end": N }` — N minutes **before** its window closes (the default, 30).

## How it works

On each engine run: fetch today's times, compute each prayer's reminder moment from
its rule, and return the ones due *now*. A 20-minute due window plus ntfy's message
cache mean a reminder fires **exactly once**, even though many runs fall inside the
window — and a late or skipped run is still caught.

## The code

`PrayerSource` implements NoterPiper's `Source` contract: `id = "prayer"` and
`check(now, config) → list[Notification]`. See [`__init__.py`](__init__.py).
