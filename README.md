<div align="center">

# 🔔 NoterPiper

**A free, serverless notification engine — it pushes the right message to your phone at the right moment.**

*Runs on free infrastructure, needs no server, and is built to be extended. Ships with two plugins: prayer reminders and a Habitica nightly nudge.*

<br>

<img src="assets/demo.png" alt="NoterPiper" width="280">

</div>

---

## What it is

NoterPiper is a tiny **notification engine**. Every couple of minutes it asks each
**plugin** — *"anything to notify right now?"* — and delivers what comes back to your
phone. Nothing runs on your own devices, and it costs nothing.

It ships with two plugins:

- 🕌 **[Prayer reminders](src/noterpiper/plugins/prayer/)** — your phone rings for each
  of the five daily prayers, at a time you choose within each prayer's window.
- 🌙 **[Habitica nightly nudge](src/noterpiper/plugins/habitica/)** *(optional)* — one
  calm end-of-day summary of what's still unlogged and which streaks are at risk.

Adding your own — gym, water, a standup reminder, anything — is one small file.

---

## How it works

```
   SOURCES (plugins)          THE ENGINE                 A CHANNEL          Your phone
   decide WHAT to send   →    asks each plugin      →    delivers it   →    (the ring)
   • prayer reminders         "anything due now?",       via ntfy
   • Habitica nudge           dedupes, routes
```

A free timer wakes a tiny job on GitHub every couple of minutes; the **engine** asks
each **plugin** what's due and sends it through a **channel** (ntfy). The engine knows
nothing about prayers or habits — only the small plugin interface — which is what lets
new plugins drop in without touching the core.

See **[PLUGINS.md](PLUGINS.md)** for the full design and how to
write a plugin.

---

## Get started

About ten minutes, once — then it runs itself.

### **→ Follow [SETUP](SETUP.md).**

---

## Why it's built well

- **Serverless & free.** Nothing to host, pay for, or patch.
- **Extensible by design.** The engine talks to plugins through one small, stable interface.
- **Zero dependencies.** Pure Python standard library — nothing to rot in five years.
- **Live.** Settings are re-read every run; a change applies within minutes.
- **Self-correcting.** A late or skipped run is caught by the next; each reminder fires exactly once.
- **Minimal.** One ring when it matters — restraint is a feature.

---

## Learn more

- **[PLUGINS.md](PLUGINS.md)** — engine design + writing a plugin
- **[ARCHITECTURE.md](ARCHITECTURE.md)** · **[DECISIONS.md](DECISIONS.md)** · **[SECURITY.md](SECURITY.md)**
- Plugins: **[prayer](src/noterpiper/plugins/prayer/)** · **[habitica](src/noterpiper/plugins/habitica/)**

<div align="center"><sub>Built to run quietly for years. 🤲</sub></div>
