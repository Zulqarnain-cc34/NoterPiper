# Habitica Dashboard — a small, no-server tool

A compact tool that pulls your Habitica data via the API and shows a clean
**dashboard** + **weekly report** for your recitations (and prayers, once those
habits have data). **No server required** — it can host itself on GitHub Pages
and refresh on a schedule.

> This used to be a data-science project; it's now just an API tool + dashboard.
> The old analysis lives in `archive/`.

## Privacy
- Your API token stays in **`.env`** (git-ignored) locally, or as an encrypted
  **GitHub Secret** in automation. It is **never printed, logged, or committed**.
- All API calls are **read-only** (GET). The tool never changes your account.
- Snapshots are **sanitized** (token/email stripped) before saving.

---

## The two features

| Feature | What it does | Command |
|---|---|---|
| **Live sync + dashboard** | pull data → rebuild DB → regenerate dashboard (one command) | `python scripts/sync_from_api.py` |
| **Notifications** | push "not logged yet / streak at risk" to your phone via ntfy.sh | `python scripts/notify.py` |

## Run it locally
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "API_TOKEN=your_token_here" > .env      # your Habitica API token
python scripts/sync_from_api.py              # pull live → rebuild → dashboard (site/index.html)
python scripts/notify.py                     # dry-run prints the message; set NTFY_TOPIC to push
```

## Host it with no server (always-on URL)

**GitHub Actions (free scheduled runner) + GitHub Pages (free static host).**
The workflow `.github/workflows/dashboard.yml` pulls your data, builds a static
HTML dashboard, and publishes it — on a daily schedule, no server.

One-time setup:
1. Push this repo to GitHub.
2. **Settings → Secrets and variables → Actions** → add `HABITICA_API_TOKEN` and
   `HABITICA_USER_ID`.
3. **Settings → Pages → Source: GitHub Actions**.
4. **Actions tab → run "Habitica Dashboard"** (or wait for the daily run).

Your dashboard is then live at your Pages URL, refreshing itself daily.
*Want it private?* Host the same `site/index.html` on **Cloudflare Pages** with
**Cloudflare Access** (free password gate) instead of Pages.

> Why not a pure browser page? Habitica's API blocks cross-origin browser calls
> (CORS). GitHub Actions fetches server-side, so there's no CORS issue and the
> token stays in the secret store.

## Notifications (no server, free)

`scripts/notify.py` + `.github/workflows/notify.yml` push a daily nudge to your
phone via **ntfy.sh** — *"prayers not logged: …", "streak at risk: …"*.

One-time setup:
1. Install the **ntfy** app (iOS/Android) and **subscribe to a secret topic**
   name, e.g. `habitica-<something-random>`.
2. Locally: add `NTFY_TOPIC=habitica-<something-random>` to `.env`.
   In Actions: add it as the secret `NTFY_TOPIC` (plus the two Habitica secrets).
3. The Action runs ~9:30 PM Pakistan time daily (editable in `notify.yml`); or
   press **Run** in the Actions tab.

**Timing note:** GitHub's schedule can be 5–30 min late — great for a once-a-day
"before midnight" nudge, **not** for exact prayer-time alerts (use a prayer-time
app for those).

---

## What's tracked (the 3 sections)
See **`reports/data_guide.md`** (human) and **`reports/data_guide_technical.md`**
(pipeline reference):
1. **Prayers** — 5 habits, ➕ Jamaat / ➖ home / no-tap missed (new; no data yet).
2. **Daily recitations** — 5 dailies.
3. **Weekly recitations** — 2 Friday dailies.

## Project layout
```
.env                         your token + NTFY_TOPIC (git-ignored)
.github/workflows/
  dashboard.yml              no-server dashboard (Actions → Pages)
  notify.yml                 no-server daily notification (Actions → ntfy.sh)
src/habitica_etl/            api · config · loaders · transform · database · validation · analytics
scripts/   sync_from_api.py · notify.py · build_recitations_dashboard.py
notebooks/recitations_dashboard.ipynb
reports/   data_guide.md · data_guide_technical.md
```
