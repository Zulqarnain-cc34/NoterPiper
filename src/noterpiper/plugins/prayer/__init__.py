"""Prayer-reminder source — the first plugin.

The prayer-time logic behind the Source contract: fetch today's times (Aladhan),
work out each prayer's reminder moment from its rule, and return the ones due *now*.
`now` is supplied by the engine (timezone-aware), so this is pure and testable.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
from datetime import datetime, timedelta

from ... import net
from ...engine import Notification
from .._common import due_at as _due
from .._common import fmt as _fmt
from .._common import to_dt as _to_dt

# When each prayer STARTS and when its window ENDS (ends when the next one starts).
# Isha's end is madhab-dependent — see MADHABS below; this entry is the fallback.
STARTS_AT = {"Fajr": "Fajr", "Zohar": "Dhuhr", "Asr": "Asr", "Maghrib": "Maghrib", "Isha": "Isha"}
ENDS_AT = {
    "Fajr": "Sunrise",
    "Zohar": "Asr",
    "Asr": "Maghrib",
    "Maghrib": "Isha",
    "Isha": "Midnight",
}
DEFAULT_RULE = {"before_end": 30}
WINDOW_MIN = 5  # fire if a run lands within this many minutes after the reminder time
DEFAULT_REMINDERS = {
    "Fajr": {"before_end": 30},
    "Zohar": {"before_end": 30},
    "Asr": {"before_end": 30},
    "Maghrib": {"before_end": 30},
    "Isha": {"after_start": 60},
}

# One setting drives every madhab-sensitive choice in this plugin, so picking a madhab
# fixes all of them together — not two separate knobs (an Asr setting and an Isha
# setting) a user has to discover and reconcile by hand:
#   - asr_school: Aladhan's own Asr juristic-method parameter. "0" Shafi'i/standard
#     (shadow length = object length; also used in practice by Maliki/Hanbali). "1"
#     Hanafi (shadow length = 2x object), noticeably later. INDEPENDENT of `method`
#     (the Fajr/Isha angle convention, e.g. method "1" = Univ. of Islamic Sciences,
#     Karachi) — Aladhan does not infer one from the other, so a Karachi-style method
#     does NOT imply Hanafi Asr on its own.
#   - isha_end: which already-fetched timing marks Isha's displayed end. Hanafi holds
#     there's no midnight cutoff — Isha stays valid until Fajr. The other schools'
#     preferred-time view ends around Islamic midnight.
MADHABS = {
    "hanafi": {"asr_school": "1", "isha_end": "Fajr"},
    "standard": {"asr_school": "0", "isha_end": "Midnight"},  # Shafi'i / Maliki / Hanbali
}
DEFAULT_MADHAB = "hanafi"


def _madhab_profile(name) -> dict:
    """The chosen madhab's settings, falling back to the default on anything
    unrecognized — a config typo must not crash the whole prayer plugin."""
    return MADHABS.get(str(name).strip().lower(), MADHABS[DEFAULT_MADHAB])


def _resolve_profile(config: dict) -> dict:
    """The madhab's profile, with each axis individually overridable. `madhab`
    alone is the common case (one coherent default); `asr_school`/`isha_end`
    are opt-in escape hatches for someone who wants to mix the two axes rather
    than pick one of the two bundled presets — never UI-exposed (that would
    reintroduce the two-disconnected-knobs problem for the common case), but a
    real, honest parameter for anyone editing config.json directly."""
    profile = dict(
        _madhab_profile(config.get("madhab", DEFAULT_MADHAB))
    )  # copy — don't mutate MADHABS
    if config.get("asr_school") is not None:
        profile["asr_school"] = str(config["asr_school"])
    isha_end = config.get("isha_end")
    if isha_end is not None:
        normalized = str(isha_end).strip().capitalize()
        if normalized in ("Fajr", "Midnight"):
            profile["isha_end"] = normalized
    return profile


def _reminder_dt(prayer: str, timings: dict, ref: datetime, rules: dict, ends_at: dict) -> datetime:
    rule = rules.get(prayer, DEFAULT_RULE)
    if "after_start" in rule:
        return _to_dt(timings[STARTS_AT[prayer]], ref) + timedelta(minutes=int(rule["after_start"]))
    return _to_dt(timings[ends_at[prayer]], ref) - timedelta(
        minutes=int(rule.get("before_end", 30))
    )


def fetch_timings(
    city: str, country: str, method: str, school: str = MADHABS[DEFAULT_MADHAB]["asr_school"]
) -> dict:
    """Today's prayer times for the city from Aladhan. Raises a clear, location-free
    error (public logs) if the request is rejected or the response is unusable.

    `school` is Aladhan's own Asr-juristic-method parameter — PrayerSource resolves it
    from the user's `madhab` setting before calling this; it's exposed directly here
    for testability and because it's the literal Aladhan vocabulary."""
    url = "https://api.aladhan.com/v1/timingsByCity?" + urllib.parse.urlencode(
        {"city": city, "country": country, "method": method, "school": school}
    )
    try:
        payload = net.get_json(url)
    except urllib.error.HTTPError as e:
        if e.code < 500:
            raise RuntimeError(
                f"Aladhan rejected the configured location (HTTP {e.code}). "
                f"Check your city / country / method."
            ) from e
        raise
    data = payload.get("data") if isinstance(payload, dict) else None
    timings = data.get("timings") if isinstance(data, dict) else None
    if not isinstance(timings, dict):
        raise RuntimeError("Aladhan returned no usable prayer times for the configured location.")
    return timings


class PrayerSource:
    id = "prayer"
    wants_location = True  # city/country/method/timezone come from the shared location
    defaults = {
        "enabled": True,
        "window": WINDOW_MIN,
        "reminders": DEFAULT_REMINDERS,
        "madhab": DEFAULT_MADHAB,  # "hanafi" (default) or "standard" — drives Asr + Isha together
        "asr_school": None,  # advanced override: "0" or "1" — beats whatever `madhab` implies
        "isha_end": None,  # advanced override: "Fajr" or "Midnight" — beats whatever `madhab` implies
    }

    def check(self, now: datetime, config: dict) -> list[Notification]:
        if not config.get("enabled", True):  # same off-switch every other plugin has
            return []
        profile = _resolve_profile(config)
        timings = fetch_timings(
            config.get("city"), config.get("country"), config.get("method"), profile["asr_school"]
        )
        ends_at = {**ENDS_AT, "Isha": profile["isha_end"]}
        rules = config.get("reminders", {})
        window = int(config.get("window", WINDOW_MIN))
        out: list[Notification] = []
        for prayer in STARTS_AT:
            try:
                remind = _reminder_dt(prayer, timings, now, rules, ends_at)
            except (KeyError, ValueError, TypeError):
                continue  # bad rule / missing timing → skip this one
            if not _due(remind, now, window):
                continue
            try:
                end = _to_dt(timings[ends_at[prayer]], now)
                while end < remind:
                    end += timedelta(days=1)
                body = f"Time to pray · ends {_fmt(end)}"
            except (KeyError, ValueError, TypeError):
                body = "Time to pray"  # end time unavailable — still remind
            out.append(
                Notification(prayer, body, priority="max", tags=("mosque",), dedup_key=prayer)
            )
        return out
