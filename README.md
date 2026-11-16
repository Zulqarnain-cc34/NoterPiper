<div align="center">

# 🕌 Habitica Salah

**Your prayers and daily recitations — gently tracked, with reminders that reach your phone.**

</div>

This little tool connects to your Habitica account and does three kind things for you:

- 🔔 **Prayer reminders** — your phone **rings 30 minutes before each of the 5 prayers ends**, at the real prayer times for your city.
- 🌙 **A nightly check-in** — before midnight it tells you what you haven't logged yet, and warns you if a long streak is about to break.
- 📊 **A simple dashboard** — a clean page showing how your prayers and recitations are going over time.

It runs **by itself, on the internet — you don't need to keep a computer on.**

---

## Will this keep working forever?

Mostly yes — here's the honest version:

- ✅ It runs on **GitHub's free servers**, not your computer. So it keeps going whether your laptop is on or off.
- ✅ Reminders are delivered by **ntfy** (a free notification service) and prayer times come from a **free prayer-times service** — both are stable and free.
- ⏳ One catch: GitHub **pauses automatic jobs if a project sits untouched for 60 days**. A built-in monthly "keepalive" taps the project so that **never happens** — so it truly keeps running hands-off.
- 🙏 The only things that could ever stop it are if those free services shut down one day. If that happens, it's a quick swap, not a rebuild.

**So: yes — set it up once, and it keeps reminding you, indefinitely.**

---

## What you need to do once

**On your phone**
1. Install the **ntfy** app (iPhone or Android).
2. Subscribe to your private topic (a secret name you pick), and allow it to show notifications.

**On the website (GitHub)**
3. Add your details as **Secrets**: your Habitica key, your Habitica ID, and your ntfy topic.
4. Choose your city as a **Variable**: `PRAYER_CITY` = `Lahore` or `Islamabad`.
5. Turn the automatic jobs on (the **Actions** tab) — done.

*(Full step-by-step is in `SETUP.md`.)*

---

## Run it yourself any time (optional)

If you ever want to trigger things by hand from a computer:

```bash
source .venv/bin/activate
python scripts/schedule_prayers.py   # schedules today's prayer reminders
python scripts/notify.py             # sends the "not logged yet" check-in
python scripts/sync_from_api.py      # refreshes the dashboard
python scripts/selftest.py           # proves reminders fire on time
```

---

## Your privacy
- Your Habitica key stays private — it's kept as a hidden secret, never shown or shared.
- Your prayer data stays in **your** private project. Nothing is public.

## Make it yours
- **Change reminder times** → edit **`reminders.json`** (minutes `before_end` or
  `after_start`, per prayer). No code needed — editable right on GitHub's website.
- **Change city** → set the `PRAYER_CITY` variable.

Notifications are kept **deliberately small** — 5 prayer reminders + one gentle
nightly check-in — so they stay meaningful instead of becoming noise.

## Under the hood
- **`ARCHITECTURE.md`** — how it's built to run for years.
- **`reports/data_guide.md`** — plain-English guide to every habit tracked.
