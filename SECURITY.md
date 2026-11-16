# Security

A short, honest threat model for a personal, serverless notifier.

## What's sensitive
- **Habitica API token** — read-only, but still a credential.
- **ntfy topic** — a *bearer secret*: anyone who knows it can read **and send**
  notifications to your phone.

## How they're protected
- Secrets live only as **GitHub Actions Secrets** (encrypted) or a local `.env`
  (git-ignored). They are **never committed, printed, or logged** — the HTTP
  layer only sends headers, never echoes them, and errors don't include them.
- `.env`, `.env`-style files, `data/`, and `token.txt` are git-ignored.
- **Config-page token** — the optional phone page writes `config.json` with a
  **fine-grained token you create** (scoped to this repo only, Contents + Actions),
  kept solely in your browser's local storage — never committed. The repo being
  public makes `config.json` (your city and offsets) visible, but it holds **no
  secrets**; the ntfy topic and Habitica token stay GitHub Secrets.

## Design choices that reduce risk
- **Read-only Habitica access** (GET only) — the tool can never modify your account.
- **Zero runtime dependencies** — the app is pure standard library, so there is
  essentially no supply-chain surface. CI and workflows pin action versions.
- **HTTPS everywhere** — Habitica, Aladhan, and ntfy are all called over TLS.
- **No untrusted input in workflows** — no injection surface; `GITHUB_TOKEN` is
  used only by the keepalive job and only for `contents: write` on this repo.
- **Inputs are safe** — city/country are URL-encoded; `config.json` parsing
  falls back to defaults on any error; there is no `eval`/shell execution.

## The one real caveat: your ntfy topic
Because the topic is a bearer secret, **choose a long, random topic name** (e.g.
`muezzin-7f3qk9zx2m`). If it ever leaks, rotate it (pick a new one, update the
`NTFY_TOPIC` secret, and re-subscribe in the app). For stronger protection, use
ntfy **access tokens / reserved topics** (self-hosted or ntfy Pro).

## Failure behavior (does it break safely?)
- A provider outage (Habitica / Aladhan / ntfy) is retried with backoff; if it
  still fails, that single run fails **loudly** (GitHub emails you) and the next
  scheduled run recovers. Prayer reminders and the nudge are independent, so one
  failing never affects the other.

## Reporting
This is a personal project — open a private issue or contact the maintainer.
