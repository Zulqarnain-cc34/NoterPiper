<div align="center">

# 🌙 Ramadan suhoor & iftar

**A NoterPiper plugin — eat before Fajr, break at Maghrib.** *(optional)*

*During Ramadan, your phone nudges you to finish suhoor before Fajr and rings again
at Maghrib for iftar — computed live for your city. Silent the rest of the year.*

</div>

---

## What it does

On each engine run it reads today's **Fajr** and **Maghrib** (same free Aladhan API
as the prayer plugin, reusing your configured city) and, **only during Ramadan**
(Hijri month 9), sends two reminders a day:

- **Suhoor** — a set number of minutes **before Fajr**: *stop eating soon*.
- **Iftar** — **at Maghrib** (or a lead before it): *time to break your fast*.

Outside Ramadan it does nothing. One ring each, deduped once per day.

## What lands on your phone

> ### 🌙 Suhoor
> Stop eating soon — Fajr at 5:12 AM

> ### 🌅 Iftar
> Time to break your fast — Maghrib at 6:45 PM

## Testing it any time of year

Because it's silent outside Ramadan, the config page has a **Test now** button
(Ramadan card). It forces a one-off **preview of today's Fajr & Maghrib** regardless
of the month, so you can confirm it works before Ramadan arrives:

> ### 🌙 Ramadan preview
> Suhoor ends 5:12 AM (Fajr) · Iftar 6:45 PM (Maghrib)

## Setup

Nothing extra — it reuses the **location** your prayer plugin already uses. All of its
settings are editable on the config page (and save automatically):

| Key | Meaning |
|---|---|
| `ramadan.enabled` | Turn the suhoor/iftar reminders on/off |
| `ramadan.suhoor_lead` *(optional)* | Minutes before Fajr for the suhoor nudge — defaults to 45 |
| `ramadan.iftar_lead` *(optional)* | Minutes before Maghrib for the iftar nudge — defaults to 0 (at Maghrib) |
| `ramadan.window` *(optional)* | Minutes a reminder stays "due" — defaults to 10 |

## How it works

Each run fetches today's times + the Hijri month from Aladhan; outside Ramadan it
returns nothing. During Ramadan it fires the suhoor reminder in the window after
`Fajr − suhoor_lead` and the iftar reminder after `Maghrib − iftar_lead`, each with a
stable dedup key so it goes out once. The config page's **Test** forces a preview via
`FORCE_SOURCE=ramadan` (`.github/workflows/ramadan.yml`), bypassing the month gate.
Code: [`__init__.py`](__init__.py) — the `RamadanSource` class satisfies NoterPiper's
`Source` contract (`id = "ramadan"`, `check(now, config) → [Notification]`).
