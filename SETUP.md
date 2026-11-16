# Setup — the engine

About 10 minutes, once. Then it runs itself.

This sets up the **engine** — a way to reach your phone (a channel) and the trigger
that runs it. Once that's live, you **turn on the reminders you want** (the plugins) —
each has its own short setup. You never touch the engine again.

---

## 1 · Delivery — the ntfy channel

This is how notifications reach your phone (the default channel).

1. Install **ntfy** — [iPhone](https://apps.apple.com/us/app/ntfy/id1625396347) · [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy).
2. Think of a **secret topic name** — random text, e.g. `noterpiper-7f3qk9zx`. Keep it private.
3. In the app: tap **＋** → type your topic → **Subscribe**, and allow notifications.
4. On GitHub → **Settings → Secrets and variables → Actions → New repository secret**:

   | Secret | Value |
   |---|---|
   | `NTFY_TOPIC` | your topic from step 2 |

> Want to also receive on Discord / Slack / email? Add another channel —
> see **[channels](src/noterpiper/channels/README.md)**.

---

## 2 · The trigger — run the engine every ~2 minutes

GitHub won't start a frequent schedule reliably on its own, so a tiny free service
presses the button for you.

1. **Enable + test** — open the **Actions** tab → enable workflows if asked → run the
   workflow once → confirm the run log finishes without errors.
2. **Make a GitHub token** — *Settings → Developer settings → Fine-grained tokens →
   Generate new token*. Repository access: **only this repo**. Permissions:
   **Actions → Read and write**. Copy it (this is `<your token>` below).
3. **Sign up at [cron-job.org](https://cron-job.org)** — free, no card.
4. **Create a cronjob:**

   | Field | Value |
   |---|---|
   | URL | `https://api.github.com/repos/<you>/noterpiper/actions/workflows/prayers.yml/dispatches` |
   | Schedule | every **2 minutes** |
   | Request method | `POST` |
   | Request body | `{"ref":"main"}` |

   **Headers** (four):

   | Key | Value |
   |---|---|
   | `Authorization` | `Bearer <your token>` |
   | `Accept` | `application/vnd.github+json` |
   | `X-GitHub-Api-Version` | `2022-11-28` |
   | `Content-Type` | `application/json` |

5. Save. Within a couple of minutes the **Actions** tab shows the engine running on
   its own. ✅

The engine is now live. It just won't say anything until you turn on a plugin ↓

---

## 3 · Turn on the reminders you want

Each plugin has its own short, self-contained setup:

- 🕌 **Prayer reminders** → **[plugins/prayer](src/noterpiper/plugins/prayer/README.md)**
  (your city, method, and timings)
- 🌙 **Habitica nightly nudge** *(optional)* → **[plugins/habitica](src/noterpiper/plugins/habitica/README.md)**
  (two API-token secrets + the nudge time)

Want a new kind of reminder (gym, water, …)? See **[PLUGINS](PLUGINS.md)** — it's one small file.

---

## Optional · Edit settings from your phone

A small page lets you change your settings from your phone instead of GitHub's file editor:

1. **Make the repo public** — *Settings → General → Change visibility → Public*. (Your
   secrets stay private; only `config.json` — your settings — becomes visible.)
2. **Turn on Pages** — *Settings → Pages → Source: Deploy from a branch → `main` / `/docs`*.
   Your page appears at `https://<you>.github.io/noterpiper/`.
3. **Reuse your token** (add **Contents → Read and write** to it as well).
4. **Install** — open the Pages URL on your phone → **⚙ Connect to GitHub** → paste the
   token → Save. Then your browser's menu → **Add to Home Screen**.
