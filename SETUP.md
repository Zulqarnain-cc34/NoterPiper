# Setup — step by step

Takes about 10 minutes, once. After this it runs by itself.

## 1. Get your phone ready (for reminders)
1. Install the **ntfy** app — [iPhone](https://apps.apple.com/us/app/ntfy/id1625396347) · [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy).
2. Pick a **secret topic name** — any random text, e.g. `muezzin-<random-letters-digits>`.
   (Anyone who knows it can see your notifications, so keep it random and private.)
3. In the app, tap **＋** → type your topic → **Subscribe**.
4. Let the app show notifications: **phone Settings → Apps → ntfy → Notifications → On**
   (and turn off battery optimization so it works in the background).

## 2. Put your details on GitHub
In your repo: **Settings → Secrets and variables → Actions**.

**Secrets** (hidden) — click *New repository secret* for each:
| Name | Value |
|---|---|
| `HABITICA_API_TOKEN` | your Habitica API token (Habitica → Settings → Site Data) |
| `HABITICA_USER_ID` | your Habitica User ID (same page) |
| `NTFY_TOPIC` | the topic you picked above |

**Variables** (plain) — the *Variables* tab, *New repository variable*:
| Name | Value |
|---|---|
| `PRAYER_CITY` | `Lahore` or `Islamabad` |
| `LEAD_MIN` | `30` (optional — minutes before each prayer ends) |

## 3. Turn it on
- Open the **Actions** tab → if asked, enable workflows.
- Click **Prayer Reminders** → **Run workflow** to test now.
  Your phone should get today's reminders scheduled at the right times.
- The jobs then run on their own:
  - **Prayer Reminders** — every morning
  - **Habitica Notifications** — nightly check-in
  - **Keepalive** — monthly, so GitHub never pauses the above

## 4. Running locally (optional)
No packages needed — the scripts are pure standard library.
```bash
printf "API_TOKEN=your_token\nUSER_ID=your_id\nNTFY_TOPIC=your_topic\nPRAYER_CITY=Lahore\n" > .env
python3 scripts/selftest.py     # proves reminders fire on time
```

---
**Timing note:** GitHub's scheduled start can be a few minutes loose, but the
reminders themselves are **exact** — they're pre-scheduled on ntfy, which
delivers at the precise second (verified by `selftest.py`).
