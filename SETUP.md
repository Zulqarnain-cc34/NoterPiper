# Setup — step by step

Takes about 10 minutes, once. After this it runs by itself.

## 1. Get your phone ready (for reminders)
1. Install the **ntfy** app — [iPhone](https://apps.apple.com/us/app/ntfy/id1625396347) · [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy).
2. Pick a **secret topic name** — any random text, e.g. `muezzin-<random-letters-digits>`.
   (Anyone who knows it can see your notifications, so keep it random and private.)
3. In the app, tap **＋** → type your topic → **Subscribe**.
4. Let the app show notifications: **phone Settings → Apps → ntfy → Notifications → On**
   (and turn off battery optimization so it works in the background).

## 2. Put your settings on GitHub
In your repo: **Settings → Secrets and variables → Actions**.

**Secret** (hidden) — *New repository secret*:
| Name | Value |
|---|---|
| `NTFY_TOPIC` | the topic you picked above — **required** |

**Variables** (plain) — the *Variables* tab, *New repository variable* — set your location:
| Name | Value | Default |
|---|---|---|
| `PRAYER_CITY` | your city, e.g. `Lahore`, `Istanbul`, `London` | `Lahore` |
| `PRAYER_COUNTRY` | your country, e.g. `Pakistan`, `Turkey`, `United Kingdom` | `Pakistan` |
| `PRAYER_METHOD` | Aladhan calc-method id ([list](https://aladhan.com/calculation-methods)) | `1` (Karachi) |

The timezone is detected automatically from your city — it works anywhere.

**Optional — the nightly Habitica nudge.** Only if you log in Habitica; the prayer
reminders don't need it. Add two more **Secrets**:
| Name | Value |
|---|---|
| `HABITICA_API_TOKEN` | Habitica → Settings → Site Data |
| `HABITICA_USER_ID` | same page |

## 3. Turn it on
- Open the **Actions** tab → if asked, enable workflows.
- Click **Prayer Reminders** → **Run workflow** to test now.
  Your phone should get today's reminders scheduled at the right times.
- The jobs then run on their own:
  - **Prayer Reminders** — every morning
  - **Habitica Notifications** — nightly nudge (if configured)
  - **Keepalive** — monthly, so GitHub never pauses the above

> **Not in Pakistan?** The workflow `cron` times are in **UTC** and default to
> early morning / night in Pakistan. So all of *today's* reminders get scheduled,
> set the `cron` in `.github/workflows/prayers.yml` to **shortly after midnight in
> your timezone** (and `notify.yml` to your evening). Cron uses UTC — e.g. for
> New York (UTC−5) use `0 5 * * *` for ~00:00 local.

## 4. Running locally (optional)
No packages needed — the scripts are pure standard library.
```bash
cp .env.example .env     # then edit NTFY_TOPIC and your city
python3 scripts/selftest.py     # proves reminders fire on time
```

---
**Timing note:** GitHub's scheduled start can be a few minutes loose, but the
reminders themselves are **exact** — they're pre-scheduled on ntfy, which
delivers at the precise second (verified by `selftest.py`).
