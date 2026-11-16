# NoterPiper — Project Overview

**A free, serverless notification engine — with prayer reminders and a Habitica nudge as its first two plugins.**

NoterPiper is a small engine that runs on free infrastructure and delivers the right
message to your phone at the right time. It ships with two plugins out of the box —
**prayer reminders** and an optional **nightly Habitica check-in** — and it is built
so new kinds of reminders can be plugged in without touching the core.

---

## 1. In one sentence

> NoterPiper is a notification engine you fully own: a tiny core that quietly runs on free
> services, and plugins that decide what to tell you — starting with your five daily
> prayers — with nothing for you to keep switched on.

---

## 2. The problem it solves

Most reminder apps come with a cost: ads, bloat, battery drain, a sign-up, or a
company quietly collecting your location and habits. And they stop working the day the
app is abandoned.

NoterPiper takes the opposite approach — a personal notification system that is:

- **Yours.** You own the whole thing; there is no company in the middle.
- **Private.** It only ever *reads* public data; nothing personal is sold or tracked.
- **Permanent.** Built from free, stable building blocks, so it can run for years untouched.
- **Quiet.** One clear notification when it matters — never a stream of noise.

---

## 3. What it does today — two plugins on one engine

🔔 **Prayer reminders (the first plugin)**
Your phone rings for Fajr, Zohar, Asr, Maghrib, and Isha — at a time you pick for each
one (e.g. "30 minutes after Fajr begins"). The times are calculated live for your city.

🌙 **A nightly check-in (the second plugin, optional)**
If you track habits in Habitica, NoterPiper can send one calm end-of-day summary of
what's still unticked and which streaks are at risk. Entirely optional — the prayer
plugin works perfectly without it.

📱 **A little settings app**
A page you can add to your phone's home screen lets you change your city and reminder
times whenever you like. Changes take effect within minutes.

**No servers. No sign-ups. No cost.**

---

## 4. What it looks like

<img src="assets/demo.png" alt="NoterPiper settings screen" width="280">

When a prayer is due, this is all that reaches your phone:

> ### 🕌 Maghrib
> Time to pray · ends 5:03 PM

One ring, when it matters — clear and to the point. Nothing else, ever.

---

## 5. How it works (the big picture)

NoterPiper has three simple parts, each doing one job:

```
   SOURCES (plugins)          THE ENGINE                 A CHANNEL          Your phone
   decide WHAT to send   →    asks each plugin      →    delivers it   →    (the ring)
   • prayer reminders         "anything due now?",       via ntfy
   • Habitica nudge           collects, de-duplicates
```

In plain words, every couple of minutes a **free timer** wakes a **tiny job on
GitHub**. The job (the *engine*) asks each **plugin**: *is anything due right now?*
Whatever comes back is sent to your phone as a push notification (the *channel*).
Because it re-reads your settings every run, any change shows up within minutes — and
nothing runs on your own devices.

---

## 6. Why it is built well

Simple on the surface, carefully thought-through underneath:

- **Serverless and free.** Nothing to host, pay for, or patch.
- **Zero dependencies.** Only built-in code — nothing that can rot or need security updates. Built to still work in five years untouched.
- **Extensible by design.** The engine talks to plugins through a small, stable interface, so new reminders can be added without changing the core.
- **Live settings.** Every run reads your preferences fresh — changes apply in minutes, not tomorrow.
- **Self-correcting.** A late or skipped run is caught by the next, and each reminder is sent exactly once (never twice).
- **Fails loudly, not silently.** It retries, and if it still can't recover it alerts you.
- **Minimal by design.** Each plugin is independent, so one can never break another — and restraint is a feature: fewer notifications mean each one matters.

---

## 7. The tech stack

| Layer | What it uses | Why |
|---|---|---|
| **Scheduler** | A free external timer + GitHub Actions | Reliable "every couple of minutes" trigger, at no cost |
| **Engine & plugins** | Python (standard library only) | No dependencies to rot; readable in one sitting |
| **Prayer times** | Aladhan API | Accurate live prayer times for any city worldwide |
| **Delivery (channel)** | ntfy.sh | Free, instant push notifications to any phone |
| **Settings page** | Plain HTML + JavaScript on GitHub Pages | Installable on your phone, no build step, no framework |

---

## 8. The decisions behind it

- **Send reminders live, not pre-scheduled.** The engine checks continuously, so a
  setting you change during the day takes effect right away.
- **Use an outside clock.** The obvious free scheduler was unreliable for frequent
  intervals, so the trigger was moved to a dependable free timer — no new code, no cost.
- **One settings file, namespaced per plugin.** Everything configurable lives in one
  place, split cleanly so each plugin owns its own slice.
- **Decouple the engine from the plugins.** The core depends only on a small plugin
  *interface*, never on prayers or Habitica directly — which is what makes it extensible.

---

## 9. The architecture: a notification engine with a plugin ecosystem

This is the heart of the project. NoterPiper is built as three decoupled layers:

- **The engine** — a tiny core that, on each run, asks every registered plugin
  "anything due?", collects the results, removes duplicates, and routes them. It knows
  nothing about prayers or habits.
- **Plugins (sources)** — each decides *what* to notify and *when*. Prayer reminders
  and the Habitica nudge are the first two; they implement one small shared interface.
- **Channels** — each decides *how* to deliver. ntfy is the first; email or Telegram
  could be added without changing anything else.

Because the engine depends only on the plugin *interface* (not on the plugins
themselves), new plugins can be added without ever touching the core — the same idea
that lets a library like LangChain accept endless third-party integrations.

> NoterPiper isn't "a prayer app with a Habitica feature." It's **a free, serverless
> notification engine that happens to ship two excellent plugins.**

---

## 10. What's next

- **Formalize the plugin interface** so writing a new plugin is a documented, 30-line job.
- **A smarter nightly summary** that stays one calm message even as you track more habits.
- **More plugins and channels** — new reminder types, new delivery methods.
- **A plugin ecosystem** — third parties publishing their own NoterPiper plugins.

Every step keeps the founding promise: free, serverless, and quiet.

---

## 11. Try it / learn more

- **Setup** takes about ten minutes, once — see the project's `SETUP` guide.
- **The engine design and the path to the full plugin system** are written up in
  `PLUGINS`, and the reasoning behind each choice is in `DECISIONS`.

---

## 12. In short

NoterPiper is a small idea executed with care: a notification engine that is genuinely
free, genuinely private, and genuinely built to last — a tiny core, two excellent
plugins today, and room for many more. It says exactly one thing, at exactly the right
moment.

*Built to run quietly for years.* 🤲
