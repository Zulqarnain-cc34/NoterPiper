<div align="center">

# 🕌 Prayer reminders

**A NoterPiper plugin — your call to prayer, on your phone.**

*Your phone rings for each of the five daily prayers, at the moment you choose
within that prayer's own window. Live prayer times for your city, free, forever.*

</div>

---

## What it does

Rings for **Fajr, Zohar, Asr, Maghrib, Isha** — each at a time *you* pick, calculated
live for your city via the free [Aladhan](https://aladhan.com) API.

## What lands on your phone

> ### 🕌 Maghrib
> Time to pray · ends 5:03 PM

One ring, at max priority, when the prayer is due. Nothing else.

---

## Setup

The engine itself is set up once in the main **[SETUP](../../../../SETUP.md)** (ntfy +
the trigger). This plugin only needs its **location and timings**, in `config.json`:

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

Prefer to keep your location **out of a public repo?** Set `PRAYER_CITY`,
`PRAYER_COUNTRY`, `PRAYER_METHOD`, `PRAYER_TIMEZONE` as repo **Variables** instead —
they override the file.

## Settings reference

| Key | Meaning |
|---|---|
| `city` / `country` | Your location (Aladhan resolves the timezone automatically) |
| `method` | Calculation method id — [full list](https://aladhan.com/calculation-methods) |
| `reminders.<prayer>` | `{ "after_start": N }` (N min after it begins) **or** `{ "before_end": N }` (N min before its window closes) |
| `window` *(optional)* | Minutes a reminder stays "due" — defaults to 5 |

## Security

- **Reads only public data.** Aladhan prayer times need no account and no personal
  info beyond the city name you choose.
- **Sends no secrets.** The reminder carries only the prayer name and its end time.
- **No location in logs.** The plugin never prints your city/timezone (Actions logs
  are public on a public repo).

## How it works

On each engine run it fetches today's times, computes each prayer's reminder moment
from its rule, and returns the ones due *now*. A short due-window plus ntfy's message
cache mean a reminder fires **exactly once** per day, and a late or skipped run is
still caught. Code: [`__init__.py`](__init__.py) — the `PrayerSource` class satisfies
NoterPiper's `Source` contract (`id = "prayer"`, `check(now, config) → [Notification]`).
