# Setup

About 10 minutes, once. Then it runs itself — forever.

---

## 1 · Phone

1. Install **ntfy** — [iPhone](https://apps.apple.com/us/app/ntfy/id1625396347) · [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy).
2. Think of a **secret topic name** — random text, e.g. `muezzin-7f3qk9zx`. Keep it private.
3. In the app: tap **＋** → type your topic → **Subscribe**.
4. Allow notifications for ntfy in your phone settings.

---

## 2 · GitHub settings

Go to **Settings → Secrets and variables → Actions**.

**Add one Secret** (the *Secrets* tab → *New repository secret*):

| Secret | Value |
|---|---|
| `NTFY_TOPIC` | your topic from step 1 |

**Set your location** — open [`config.json`](config.json) on GitHub, tap ✏️ *Edit*,
and change `"city"`, `"country"`, and `"method"` to yours. Commit.

> **method** is the calculation body for your region (it mainly sets the Fajr/Isha
> angles). The common ones: `1` Karachi · `2` ISNA (N. America) · `3` Muslim World
> League · `4` Umm al-Qura (Saudi) · `5` Egyptian Authority. Any valid id works — see
> the current, complete list at
> [aladhan.com/calculation-methods](https://aladhan.com/calculation-methods).

> Timezone is detected from your city — it works anywhere.

---

## 3 · Make it run automatically

GitHub can send the reminders, but it won't start a frequent schedule
reliably on its own. A tiny free service presses the button for you —
every couple of minutes, on the dot.

1. **Enable + test** — open the **Actions** tab → enable workflows if asked →
   click **Prayer Reminders** → **Run workflow**. Your phone should ring.
2. **Make a GitHub token** (your own, generated on GitHub) — *Settings → Developer
   settings → Fine-grained tokens → Generate new token*. Repository access:
   **only this repo**. Permissions: **Actions → Read and write**. Copy it —
   this is the `<your token>` used in the Authorization header below.
3. **Sign up at [cron-job.org](https://cron-job.org)** — free, no card.
4. **Create a cronjob** with these settings:

   | Field | Value |
   |---|---|
   | URL | `https://api.github.com/repos/<you>/muezzin/actions/workflows/prayers.yml/dispatches` |
   | Schedule | every **2 minutes** |
   | Request method | `POST` |
   | Request body | `{"ref":"main"}` |

   **Headers** (four):

   | Key | Value |
   |---|---|
   | `Authorization` | `Bearer <your token>` — the GitHub fine-grained token from step 2 |
   | `Accept` | `application/vnd.github+json` |
   | `X-GitHub-Api-Version` | `2022-11-28` |
   | `Content-Type` | `application/json` |

5. Save. Within a couple of minutes the **Actions** tab shows **Prayer
   Reminders** running on its own. ✅

That's it. Reminders now land on time every day, and any setting you change
applies within minutes.

> One token does both jobs — if you also set up the phone page below, give
> the token **Contents → Read and write** as well, and reuse it.

---

## Optional

- **Phone config page** — edit all of this from your phone instead of GitHub's file editor:
  1. **Make the repo public** — *Settings → General → Change visibility → Public*. (Your
     secrets stay private; only `config.json` — your city and offsets — becomes visible.)
  2. **Turn on Pages** — *Settings → Pages → Source: Deploy from a branch → `main` / `/docs`*.
     Your page appears at `https://<you>.github.io/muezzin/`.
  3. **Make a token** — *Settings → Developer settings → Fine-grained tokens → Generate*.
     Repository access: **only this repo**. Permissions: **Contents → Read and write** and
     **Actions → Read and write**. Copy it.
  4. **Install** — open the Pages URL on your phone → **⚙ Connect to GitHub** → paste the
     token → Save. Then your browser's menu → **Add to Home Screen**.
- **Nightly Habitica nudge** — only if you track in Habitica. Add two more Secrets:
  `HABITICA_API_TOKEN` and `HABITICA_USER_ID` (both from Habitica → Settings → Site Data),
  then set the time in [`config.json`](config.json) (`nudge.time`, 24-hour local).
- **Change reminder times** — edit [`config.json`](config.json): `reminders` holds
  `before_end` / `after_start` minutes per prayer.
- **Anywhere in the world?** Prayer reminders need no changes — they're computed from
  your city's own timezone automatically. Only the nightly Habitica nudge runs on a
  fixed UTC `cron` in `notify.yml`; adjust that window if you use the nudge.
