# Changelog

All notable changes to NoterPiper are recorded here.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] — 2026-11-16

Rebuilt from a single prayer-reminder app into a small, serverless **notification
engine** with pluggable sources and channels.

### Added
- **Notification engine** — a core that, every ~2 minutes, asks each source
  "anything due now?", removes duplicates, and fans each notification out to **every**
  enabled channel. It depends only on the `Source` and `Channel` interfaces, so new
  parts drop in without changing the core.
- **Sources (plugins)** — `prayer` (five daily reminders) and `habitica` (optional
  nightly nudge), each a self-contained package with its own README.
- **Channels** — `ntfy` (push to your phone) and a generic `webhook` (Discord, Slack,
  Microsoft Teams, Home Assistant, IFTTT, Zapier, or any URL).
- **Configurable due-windows** per plugin, via `config.json`.
- **Private location in the phone app** — the config page reads and writes your
  location (city / country / method / timezone) as private repo **Variables**, so your
  city stays out of the public file but is still shown and editable in the app.
- **Docs & visuals** — logo, badges, four architecture diagrams, a plain-English
  README, `PLUGINS.md` (how to write a source or channel), an engine-only `SETUP`
  (plugin setup lives with each plugin), and an MIT `LICENSE`.
- Built test-first — **57 tests**, pure Python standard library (zero runtime dependencies).

### Changed
- **Renamed** the project from Muezzin to **NoterPiper** (package, branding, repo).
- The **nightly nudge** now runs on the reliable ~2-minute engine instead of GitHub's
  flaky nightly cron; its title is now **"Nightly check-in"** (the count moved to the body).
- `config.json` stays flat; the entry point maps it into each plugin's config slice,
  so the phone config page is unaffected.
- `SETUP` is now engine-only; prayer and Habitica setup moved into their plugin READMEs.

### Removed
- The old standalone scripts (`schedule_prayers.py`, `notify.py`) — their logic now
  lives in the plugins, driven by `run_engine.py`.

### Security
- Your location is kept out of the public repo via private GitHub Variables (which
  override `config.json`); the engine never prints your city or timezone to the
  (public) Actions logs.
