// NoterPiper config page — PURE logic only (no `document`), so Node can unit-test it
// and the browser can import it as a module. All DOM building lives in index.html.

export const PRAYERS = ['Fajr', 'Zohar', 'Asr', 'Maghrib', 'Isha'];

// "HH:MM" in a real 24-hour range.
export function validTime(t) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(String(t).trim());
  if (!m) return false;
  const h = +m[1],
    mi = +m[2];
  return h >= 0 && h < 24 && mi >= 0 && mi < 60;
}

// Pure mapping for the location "resolve line": empty / typing(pending) / valid / unknown.
export function resolveState(city, pending, resolved) {
  if (!String(city).trim()) return 'empty';
  if (resolved) return 'valid';
  if (pending) return 'typing';
  return 'unknown';
}

// Common cities for type-ahead suggestions (the custom .suggest dropdown). Not exhaustive — any city
// still works via the live Aladhan check; these just speed up the common ones and
// auto-fill the country. [city, country].
// biome-ignore format: compact hand-packed reference table — one country per line is noise
export const CITIES = [
  ['Lahore', 'Pakistan'], ['Karachi', 'Pakistan'], ['Islamabad', 'Pakistan'], ['Rawalpindi', 'Pakistan'],
  ['Faisalabad', 'Pakistan'], ['Multan', 'Pakistan'], ['Peshawar', 'Pakistan'], ['Quetta', 'Pakistan'],
  ['Istanbul', 'Turkey'], ['Ankara', 'Turkey'], ['Izmir', 'Turkey'], ['Cairo', 'Egypt'], ['Alexandria', 'Egypt'],
  ['Dubai', 'United Arab Emirates'], ['Abu Dhabi', 'United Arab Emirates'], ['Sharjah', 'United Arab Emirates'],
  ['Mecca', 'Saudi Arabia'], ['Medina', 'Saudi Arabia'], ['Riyadh', 'Saudi Arabia'], ['Jeddah', 'Saudi Arabia'],
  ['Doha', 'Qatar'], ['Kuwait City', 'Kuwait'], ['Manama', 'Bahrain'], ['Muscat', 'Oman'], ['Amman', 'Jordan'],
  ['Baghdad', 'Iraq'], ['Beirut', 'Lebanon'], ['Damascus', 'Syria'], ['Tehran', 'Iran'],
  ['London', 'United Kingdom'], ['Birmingham', 'United Kingdom'], ['Manchester', 'United Kingdom'],
  ['New York', 'United States'], ['Chicago', 'United States'], ['Los Angeles', 'United States'],
  ['Houston', 'United States'], ['Dearborn', 'United States'], ['Toronto', 'Canada'], ['Montreal', 'Canada'],
  ['Paris', 'France'], ['Berlin', 'Germany'], ['Amsterdam', 'Netherlands'], ['Brussels', 'Belgium'],
  ['Stockholm', 'Sweden'], ['Kuala Lumpur', 'Malaysia'], ['Jakarta', 'Indonesia'], ['Dhaka', 'Bangladesh'],
  ['Delhi', 'India'], ['Mumbai', 'India'], ['Hyderabad', 'India'], ['Casablanca', 'Morocco'], ['Tunis', 'Tunisia'],
  ['Lagos', 'Nigeria'], ['Nairobi', 'Kenya'], ['Singapore', 'Singapore'], ['Sydney', 'Australia'], ['Melbourne', 'Australia'],
];

// Fixed country list for the dropdown (can't go stale). Aladhan-friendly English names.
// biome-ignore format: compact hand-packed reference table — one country per line is noise
export const COUNTRIES = [
  'Afghanistan','Albania','Algeria','Andorra','Angola','Argentina','Armenia','Australia','Austria','Azerbaijan',
  'Bahrain','Bangladesh','Belarus','Belgium','Benin','Bhutan','Bolivia','Bosnia and Herzegovina','Botswana','Brazil',
  'Brunei','Bulgaria','Burkina Faso','Burundi','Cambodia','Cameroon','Canada','Chad','Chile','China',
  'Colombia','Comoros','Congo','Costa Rica','Croatia','Cuba','Cyprus','Czechia','Denmark','Djibouti',
  'Dominican Republic','Ecuador','Egypt','El Salvador','Eritrea','Estonia','Ethiopia','Fiji','Finland','France',
  'Gabon','Gambia','Georgia','Germany','Ghana','Greece','Guatemala','Guinea','Guyana','Haiti',
  'Honduras','Hungary','Iceland','India','Indonesia','Iran','Iraq','Ireland','Israel','Italy',
  'Ivory Coast','Jamaica','Japan','Jordan','Kazakhstan','Kenya','Kosovo','Kuwait','Kyrgyzstan','Laos',
  'Latvia','Lebanon','Lesotho','Liberia','Libya','Lithuania','Luxembourg','Madagascar','Malawi','Malaysia',
  'Maldives','Mali','Malta','Mauritania','Mauritius','Mexico','Moldova','Mongolia','Montenegro','Morocco',
  'Mozambique','Myanmar','Namibia','Nepal','Netherlands','New Zealand','Nicaragua','Niger','Nigeria','North Macedonia',
  'Norway','Oman','Pakistan','Palestine','Panama','Papua New Guinea','Paraguay','Peru','Philippines','Poland',
  'Portugal','Qatar','Romania','Russia','Rwanda','Saudi Arabia','Senegal','Serbia','Sierra Leone','Singapore',
  'Slovakia','Slovenia','Somalia','South Africa','South Korea','South Sudan','Spain','Sri Lanka','Sudan','Suriname',
  'Sweden','Switzerland','Syria','Taiwan','Tajikistan','Tanzania','Thailand','Togo','Trinidad and Tobago','Tunisia',
  'Turkey','Turkmenistan','Uganda','Ukraine','United Arab Emirates','United Kingdom','United States','Uruguay','Uzbekistan','Venezuela',
  'Vietnam','Yemen','Zambia','Zimbabwe',
];

// Each prayer's window = [start, end] in Aladhan timing names.
const _WINDOW = {
  Fajr: ['Fajr', 'Sunrise'],
  Zohar: ['Dhuhr', 'Asr'],
  Asr: ['Asr', 'Maghrib'],
  Maghrib: ['Maghrib', 'Isha'],
  Isha: ['Isha', 'Midnight'],
};
function _toMin(t) {
  const p = String(t).trim().split(' ')[0].split(':');
  return +p[0] * 60 + +p[1];
}

// Aladhan timings → { prayer: window length in minutes } (wrapping past midnight for Isha).
export function prayerWindows(timings) {
  const out = {};
  for (const p in _WINDOW) {
    const [a, b] = _WINDOW[p];
    if (timings[a] == null || timings[b] == null) continue;
    let d = _toMin(timings[b]) - _toMin(timings[a]);
    if (d < 0) d += 1440; // Isha → Islamic midnight crosses 00:00
    if (d > 0) out[p] = d;
  }
  return out;
}

// Largest offset that keeps the reminder inside the window (leaving a margin), rounded to 5.
export function maxOffset(windowMin, margin = 10) {
  if (!windowMin || windowMin <= margin) return 120; // unknown yet → conservative cap
  return Math.max(5, Math.floor((windowMin - margin) / 5) * 5);
}

// config object → base64 of pretty JSON (+ trailing newline) for the GitHub
// Contents API. UTF-8 safe and diff-friendly (stable 2-space formatting).
export function encodeContent(obj) {
  const text = `${JSON.stringify(obj, null, 2)}\n`;
  const bytes = new TextEncoder().encode(text);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

// Inverse of encodeContent: GitHub's base64 (with embedded newlines) → text.
export function decodeContent(b64) {
  const bin = atob(String(b64).replace(/\s/g, ''));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

// "prayer, Quran" → ["prayer", "quran"] · empty/blank → null (no filtering).
// Mirrors the engine's whitelist normalization (lowercase, trimmed).
export function parseWhitelist(text) {
  const names = String(text || '')
    .split(',')
    .map((p) => p.trim().toLowerCase())
    .filter(Boolean);
  return names.length ? names : null;
}

// config.json object → flat form state the controls bind to.
// Reads the keyed shape ({habitica,prayer,ramadan}); falls back to the legacy shape
// (a `nudge` section, top-level `reminders`) so an un-migrated file still loads.
// `extSchema` is the generated plugins.schema.json minus the custom-card plugins; each of
// its plugins gets a generic slice in `ext` (its schema defaults overlaid by config[id]).
export function fromConfig(o = {}, extSchema = {}) {
  const sec = (k) => (o && typeof o[k] === 'object' && o[k]) || {};
  const nudge = { ...sec('nudge'), ...sec('habitica') }; // 'habitica' (new) wins over legacy 'nudge'
  const sub = (k) => (nudge[k] && typeof nudge[k] === 'object' && nudge[k]) || {};
  const morning = sub('morning');
  const weekly = sub('weekly');
  const prayer = sec('prayer');
  const ram = sec('ramadan');
  const _lead = (v, d) => (Number.isFinite(+v) && +v >= 0 ? +v : d);
  const ext = {};
  for (const id of Object.keys(extSchema)) {
    ext[id] = { ...(extSchema[id].defaults || {}), ...sec(id) }; // defaults ← saved config[id]
  }
  return {
    city: o.city ?? '',
    country: o.country ?? '',
    method: String(o.method ?? '1'),
    timezone: o.timezone ?? '',
    reminders: prayer.reminders ?? o.reminders ?? {},
    nudgeTime: nudge.time ?? '21:30',
    nudgeEnabled: nudge.enabled !== false, // default on; only explicit false is off
    nudgeStreakRisk:
      Number.isFinite(+nudge.streak_risk) && +nudge.streak_risk > 0 ? +nudge.streak_risk : 7,
    // Quiet mode: type toggles default on; the whitelist binds as a comma string.
    nudgeDailies: nudge.notify_dailies !== false,
    nudgeHabits: nudge.notify_habits !== false,
    nudgeTodos: nudge.notify_todos !== false,
    nudgeWhitelist: Array.isArray(nudge.tag_whitelist)
      ? nudge.tag_whitelist.join(', ')
      : nudge.tag_whitelist || '',
    // Morning briefing + weekly digest: opt-in extras — only explicit true is on.
    morningEnabled: morning.enabled === true,
    morningTime: morning.time ?? '06:00',
    weeklyEnabled: weekly.enabled === true,
    weeklyDay: weekly.day ?? 'Sunday',
    weeklyTime: weekly.time ?? '19:00',
    ramadanEnabled: ram.enabled !== false, // default on; silent outside Ramadan anyway
    ramadanSuhoorLead: _lead(ram.suhoor_lead, 45),
    ramadanIftarLead: _lead(ram.iftar_lead, 0),
    ext,
  };
}

// Form state → config.json object. `base` is the loaded file so unknown keys
// (anything a future version adds) survive a round-trip untouched.
export function toConfig(s, base = {}) {
  const next = {
    ...base,
    city: s.city,
    country: s.country,
    method: String(s.method),
    timezone: s.timezone,
    prayer: { ...(base.prayer || {}), reminders: s.reminders },
    habitica: {
      ...(base.habitica || {}),
      time: s.nudgeTime,
      enabled: Boolean(s.nudgeEnabled),
      streak_risk: Number(s.nudgeStreakRisk),
      notify_dailies: Boolean(s.nudgeDailies),
      notify_habits: Boolean(s.nudgeHabits),
      notify_todos: Boolean(s.nudgeTodos),
      tag_whitelist: parseWhitelist(s.nudgeWhitelist),
      morning: {
        ...((base.habitica || {}).morning || {}),
        enabled: Boolean(s.morningEnabled),
        time: s.morningTime,
      },
      weekly: {
        ...((base.habitica || {}).weekly || {}),
        enabled: Boolean(s.weeklyEnabled),
        day: s.weeklyDay,
        time: s.weeklyTime,
      },
    },
    ramadan: {
      ...(base.ramadan || {}),
      enabled: Boolean(s.ramadanEnabled),
      suhoor_lead: Number(s.ramadanSuhoorLead),
      iftar_lead: Number(s.ramadanIftarLead),
    },
  };
  for (const [id, vals] of Object.entries(s.ext || {})) {
    // schema-driven plugins
    next[id] = { ...(base[id] || {}), ...vals };
  }
  delete next.nudge; // migrate away from the legacy section…
  delete next.reminders; // …and top-level reminders (now under prayer)
  return next;
}
