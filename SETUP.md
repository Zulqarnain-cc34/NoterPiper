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

**Add your location** (the *Variables* tab → *New repository variable*):

| Variable | Example | Default |
|---|---|---|
| `PRAYER_CITY` | `Istanbul` | Lahore |
| `PRAYER_COUNTRY` | `Turkey` | Pakistan |
| `PRAYER_METHOD` | [method id](https://aladhan.com/calculation-methods) | 1 |

> Timezone is detected from your city — it works anywhere.

---

## 3 · Turn it on

1. Open the **Actions** tab → enable workflows if asked.
2. Click **Prayer Reminders** → **Run workflow**.
3. Your phone gets today's reminders. ✅

That's it. The prayer reminders now run every day on their own.

---

## Optional

- **Nightly Habitica nudge** — only if you track in Habitica. Add two more Secrets:
  `HABITICA_API_TOKEN` and `HABITICA_USER_ID` (both from Habitica → Settings → Site Data).
- **Change reminder times** — edit [`reminders.json`](reminders.json).
- **Not in Pakistan?** The scheduled times (`cron`) are in UTC and tuned for Pakistan.
  Set the `cron` in `.github/workflows/prayers.yml` to just after midnight in your
  timezone — e.g. New York (UTC−5) → `0 5 * * *`.
