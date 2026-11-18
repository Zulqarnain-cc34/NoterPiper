// The config page's application module — all DOM wiring and GitHub/Aladhan I/O.
// Pure, testable logic lives in app.js; this file is what index.html loads.
// Extracted from the former inline <script type="module"> so biome lints it
// and the e2e suite exercises exactly what ships.
import {
  CITIES,
  COUNTRIES,
  decodeContent,
  encodeContent,
  fromConfig,
  isStale,
  maxOffset,
  PRAYERS,
  prayerWindows,
  resolveState,
  toConfig,
  validTime,
} from './app.js';

// Offline shell: a default config stands in until loadConfig() fetches the real file.
const DEFAULT = {
  city: 'Makkah',
  country: 'Saudi Arabia',
  method: '4',
  timezone: 'Asia/Riyadh',
  prayer: {
    reminders: {
      Fajr: { before_end: 30 },
      Zohar: { before_end: 30 },
      Asr: { before_end: 30 },
      Maghrib: { before_end: 30 },
      Isha: { after_start: 60 },
    },
  },
  habitica: { time: '21:30', enabled: true },
};
// Curated shortlist of the stable, long-established methods only. The full list is
// Aladhan's (aladhan.com/calculation-methods) and changes over time — don't hand-sync
// it here. Any id not in this list is still preserved on load (see loadConfig below).
const METHODS = [
  ['1', 'Univ. of Karachi'],
  ['2', 'ISNA'],
  ['3', 'Muslim World League'],
  ['4', 'Umm al-Qura'],
  ['5', 'Egyptian Authority'],
  ['0', 'Shia Ithna-Ashari (Jafari)'],
  ['7', 'Tehran'],
  ['8', 'Gulf Region'],
  ['9', 'Kuwait'],
  ['10', 'Qatar'],
  ['11', 'Singapore'],
  ['12', 'France'],
  ['13', 'Turkey (Diyanet)'],
  ['14', 'Russia'],
  ['15', 'Moonsighting Committee'],
  ['16', 'Dubai'],
];

let state = fromConfig(DEFAULT);

function renderMethods() {
  document.getElementById('method').innerHTML = METHODS.map(
    ([v, l]) => `<option value="${v}">${l}</option>`,
  ).join('');
  document.getElementById('country').innerHTML = COUNTRIES.map(
    (c) => `<option value="${c}">${c}</option>`,
  ).join('');
  const slots = (from, to) => {
    // half-hour <option>s in [from, to]
    let out = '';
    for (let h = from; h <= to; h++)
      for (const m of ['00', '30'])
        out += `<option value="${String(h).padStart(2, '0')}:${m}">${String(h).padStart(2, '0')}:${m}</option>`;
    return out;
  };
  document.getElementById('nudgeTime').innerHTML = slots(18, 23); // evening sweep window
  document.getElementById('morningTime').innerHTML = slots(4, 11); // a sane morning range
  document.getElementById('weeklyTime').innerHTML = slots(8, 22); // any waking hour
  document.getElementById('weeklyDay').innerHTML = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
  ]
    .map((d) => `<option value="${d}">${d}</option>`)
    .join('');
}

// ─── live city validation against Aladhan (the real "can't save a bad city" check) ───
let pending = false,
  resolved = null,
  debounce,
  seq = 0,
  windows = {};
const aladhan = (city, country, method) =>
  `https://api.aladhan.com/v1/timingsByCity?city=${encodeURIComponent(city)}&country=${encodeURIComponent(country)}&method=${encodeURIComponent(method)}`;

async function checkCity() {
  const my = ++seq; // only the latest check may set state
  const g = (id) => document.getElementById(id);
  const city = g('city').value.trim(),
    country = g('country').value;
  if (!city) {
    resolved = null;
    pending = false;
    paint();
    return;
  }
  pending = true;
  paint();
  let tz = null,
    timings = null;
  try {
    const r = await fetch(aladhan(city, country, g('method').value));
    const j = await r.json();
    if (r.ok && j?.data) {
      tz = j.data.meta?.timezone || null;
      timings = j.data.timings || null;
      hijriMonth = Number(j.data.date?.hijri?.month?.number) || hijriMonth;
    }
  } catch {
    tz = null;
  }
  if (my !== seq) return; // a newer check superseded this one
  resolved = tz;
  if (tz) state.timezone = tz;
  if (timings) {
    windows = prayerWindows(timings);
    clampAll();
  } // cap offsets to each prayer's window
  pending = false;
  paint();
  updateRamHint();
  if (userTouched && resolved) scheduleSave(); // a user-driven location change resolved → autosave
}
// The Ramadan toggle stays armed year-round; this label shows whether it's firing now.
let hijriMonth = null;
function updateRamHint() {
  const el = document.getElementById('ramHint');
  if (!el) return;
  el.textContent =
    hijriMonth === 9
      ? "active now — it's Ramadan 🌙"
      : hijriMonth
        ? 'armed · dormant until Ramadan'
        : 'reminders — only during Ramadan';
}

// Keep every offset inside its prayer's window (5 ≤ offset ≤ window − margin).
function clampAll() {
  document.querySelectorAll('.prow').forEach((prow) => {
    const p = prow.dataset.prayer,
      vEl = prow.querySelector('.n');
    const cap = maxOffset(windows[p]);
    const v = Math.min(cap, Math.max(5, parseInt(vEl.textContent, 10)));
    if (v !== parseInt(vEl.textContent, 10)) {
      vEl.textContent = v;
      writeRule(p, prow);
    }
  });
}

function paint() {
  const g = (id) => document.getElementById(id);
  const city = g('city').value.trim(),
    country = g('country').value;
  const st = resolveState(city, pending, resolved);
  const box = g('resolve');
  box.className = `resolve${st === 'valid' ? ' good' : st === 'unknown' ? ' warn' : ''}`;
  const icon = g('ricon'),
    txt = g('rtxt'),
    tag = g('rtag');
  if (st === 'empty') {
    icon.textContent = '🕓';
    txt.textContent = 'Enter your city to begin';
    tag.textContent = '';
  } else if (st === 'typing') {
    icon.textContent = '🕓';
    txt.textContent = 'Checking…';
    tag.textContent = '…';
  } else if (st === 'valid') {
    icon.textContent = '🕓';
    txt.textContent = `${city}, ${country} → ${resolved}`;
    tag.textContent = '✓ valid';
  } else {
    icon.textContent = '⚠';
    txt.textContent = `“${city}” not found`;
    tag.textContent = 'can’t resolve';
  }
  g('save').disabled = st !== 'valid' || !validTime(g('nudgeTime').value);
}
function renderPrayers() {
  document.getElementById('prayers').innerHTML = PRAYERS.map((p) => {
    const rule = state.reminders[p] || { before_end: 30 };
    const mode = 'after_start' in rule ? 'after' : 'before';
    const n = rule.after_start ?? rule.before_end ?? 30;
    return `<div class="prow" data-prayer="${p}">
        <div class="pname"><span class="pdot"></span>${p}</div>
        <div class="pctrl">
          <div class="stepper">
            <button data-step="-5">−</button>
            <div class="val"><span class="n">${n}</span><small>min</small></div>
            <button data-step="5">+</button>
          </div>
          <button class="mode"><span class="sw">⇄</span> <b>${mode}</b></button>
        </div></div>`;
  }).join('');
}
// Inline city suggestions (our own dropdown — appears right under the field, not
// the native one that pops at the bottom of the screen on mobile).
function renderSuggest(q) {
  const sug = document.getElementById('suggest');
  q = String(q).trim().toLowerCase();
  const hits = q ? CITIES.filter(([c]) => c.toLowerCase().startsWith(q)).slice(0, 6) : [];
  if (!hits.length || (hits.length === 1 && hits[0][0].toLowerCase() === q)) {
    sug.className = 'suggest';
    sug.innerHTML = '';
    return;
  }
  sug.innerHTML = hits
    .map(
      ([c, co]) =>
        `<div class="opt" data-city="${c}"><span class="pin">📍</span><span>${c}</span><span class="co">${co}</span></div>`,
    )
    .join('');
  sug.className = 'suggest show';
}

// bind() wires handlers once at startup; applyState() paints values (and is the
// only place that does — it runs at init and again after every config load).
function bind() {
  const g = (id) => document.getElementById(id);
  // Toggles and steppers: flip/step state, repaint, and autosave (onEdit).
  const wireToggle = (id, key, after) => {
    g(id).classList.toggle('off', !state[key]);
    g(id).onclick = (e) => {
      state[key] = !state[key];
      e.currentTarget.classList.toggle('off', !state[key]);
      if (after) after();
      onEdit();
    };
  };
  const wireStepper = (id, valId, key, lo, hi) => {
    g(valId).textContent = state[key];
    g(id).onclick = (e) => {
      const step = e.target.dataset.step;
      if (!step) return;
      state[key] = Math.min(hi, Math.max(lo, state[key] + parseInt(step, 10)));
      g(valId).textContent = state[key];
      onEdit();
    };
  };
  wireToggle('nudgeEnabled', 'nudgeEnabled', updateNudgeOpts);
  wireToggle('nudgeDailies', 'nudgeDailies');
  wireToggle('nudgeHabits', 'nudgeHabits');
  wireToggle('nudgeTodos', 'nudgeTodos');
  g('nudgeWhitelist').oninput = () => {
    state.nudgeWhitelist = g('nudgeWhitelist').value;
    onEdit();
  };
  wireToggle('morningEnabled', 'morningEnabled', updateMorningWeeklyRows);
  wireToggle('weeklyEnabled', 'weeklyEnabled', updateMorningWeeklyRows);
  g('morningTime').onchange = () => {
    state.morningTime = g('morningTime').value;
    onEdit();
  };
  g('weeklyDay').onchange = () => {
    state.weeklyDay = g('weeklyDay').value;
    onEdit();
  };
  g('weeklyTime').onchange = () => {
    state.weeklyTime = g('weeklyTime').value;
    onEdit();
  };
  wireToggle('ramEnabled', 'ramadanEnabled', updateRamOpts);
  wireStepper('streakStepper', 'streakVal', 'nudgeStreakRisk', 1, 60);
  wireStepper('suhoorStepper', 'suhoorVal', 'ramadanSuhoorLead', 0, 120);
  wireStepper('iftarStepper', 'iftarVal', 'ramadanIftarLead', 0, 120);
  g('ramTest').onclick = () => dispatchWorkflow('ramadan.yml', null, 'ramTest');
  g('city').oninput = () => {
    resolved = null;
    userTouched = true;
    const v = g('city').value.trim();
    const hit = CITIES.find(([c]) => c.toLowerCase() === v.toLowerCase());
    if (hit) g('country').value = hit[1]; // auto-fill country when a known city is picked
    renderSuggest(v);
    paint();
    clearTimeout(debounce);
    debounce = setTimeout(checkCity, 400);
  };
  g('city').onblur = () =>
    setTimeout(() => {
      g('suggest').className = 'suggest';
    }, 150);
  g('suggest').addEventListener('mousedown', (e) => e.preventDefault()); // keep focus so onblur doesn't beat the click
  g('suggest').addEventListener('click', (e) => {
    const opt = e.target.closest('.opt');
    if (!opt) return;
    const c = opt.dataset.city,
      hit = CITIES.find(([x]) => x === c);
    g('city').value = c;
    if (hit) g('country').value = hit[1];
    g('suggest').className = 'suggest';
    resolved = null;
    userTouched = true;
    paint();
    clearTimeout(debounce);
    checkCity();
  });
  g('country').onchange = () => {
    userTouched = true;
    checkCity();
  };
  g('method').onchange = () => {
    userTouched = true;
    checkCity();
  };
  g('nudgeTime').onchange = () => {
    paint();
    onEdit();
  };
  document.getElementById('prayers').addEventListener('click', (e) => {
    const prow = e.target.closest('.prow');
    if (!prow) return;
    const p = prow.dataset.prayer,
      valEl = prow.querySelector('.n');
    if (e.target.dataset.step) {
      const cap = maxOffset(windows[p]); // bounded by this prayer's window
      const v = Math.min(
        cap,
        Math.max(5, parseInt(valEl.textContent, 10) + parseInt(e.target.dataset.step, 10)),
      );
      valEl.textContent = v;
      writeRule(p, prow);
      onEdit();
    } else if (e.target.closest('.mode')) {
      const b = prow.querySelector('.mode b');
      b.textContent = b.textContent === 'before' ? 'after' : 'before';
      writeRule(p, prow);
      onEdit();
    }
  });
}
function writeRule(p, prow) {
  const n = parseInt(prow.querySelector('.n').textContent, 10);
  const mode = prow.querySelector('.mode b').textContent;
  state.reminders[p] = mode === 'after' ? { after_start: n } : { before_end: n };
}
// Controls that get validated before saving (location, nudge time) are read here at
// save time; every other control writes `state` directly in its own handler.
function readForm() {
  const g = (id) => document.getElementById(id);
  state.city = g('city').value.trim();
  state.country = g('country').value.trim();
  state.method = g('method').value;
  state.nudgeTime = g('nudgeTime').value.trim();
  return state;
}

// ─── Schema-driven plugin cards ───────────────────────────────────────────
// prayer/habitica/ramadan keep their hand-built cards above; every OTHER plugin
// that ships a `config_schema` (→ plugins.schema.json) gets a generic card here,
// so community plugins appear on this page with zero app code. Controls bind to
// state.ext[pluginId][key] and autosave through the same onEdit() path.
const CUSTOM_CARDS = ['prayer', 'habitica', 'ramadan'];
let extSchema = {};
const esc = (s) =>
  String(s).replace(
    /[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c],
  );
const title = (id) => id.charAt(0).toUpperCase() + id.slice(1);

async function loadExtSchema() {
  try {
    const r = await fetch('plugins.schema.json', { cache: 'no-store' });
    if (!r.ok) {
      extSchema = {};
      return;
    }
    const all = await r.json();
    extSchema = Object.fromEntries(
      Object.entries(all).filter(([id]) => !CUSTOM_CARDS.includes(id)),
    );
  } catch {
    extSchema = {};
  } // local file:// or missing file → no ext cards, page unaffected
}

const extVal = (id, key) => state.ext?.[id]?.[key];
function setExt(id, key, v) {
  state.ext ||= {};
  state.ext[id] ||= {};
  state.ext[id][key] = v;
  onEdit();
}
const nameCell = (f) =>
  `<span class="rname">${esc(f.label)}${f.hint ? `<span class="hint">${esc(f.hint)}</span>` : ''}</span>`;

// One field spec → a bound .row element (or, for a list, a repeating row editor).
function makeControl(id, f) {
  if (f.type === 'list') return makeListEditor(id, f);
  const row = document.createElement('div');
  row.className = 'row';
  if (f.type === 'toggle') {
    row.innerHTML = `${nameCell(f)}<div class="toggle"><div class="knob"></div></div>`;
    const t = row.querySelector('.toggle');
    const paint = () => t.classList.toggle('off', !extVal(id, f.key));
    t.onclick = () => {
      setExt(id, f.key, !extVal(id, f.key));
      paint();
    };
    paint();
  } else if (f.type === 'stepper') {
    const step = f.step || 1,
      lo = f.min ?? 0,
      hi = f.max ?? 999;
    row.innerHTML =
      nameCell(f) +
      `<span class="spacer"></span><div class="stepper">` +
      `<button aria-label="less">−</button><div class="val"><span class="n"></span><small>${esc(f.unit || '')}</small></div>` +
      `<button aria-label="more">+</button></div>`;
    const n = row.querySelector('.n');
    const paint = () => {
      n.textContent = extVal(id, f.key) ?? lo;
    };
    const [minus, plus] = row.querySelectorAll('.stepper button');
    minus.onclick = () => {
      setExt(id, f.key, Math.max(lo, (extVal(id, f.key) ?? lo) - step));
      paint();
    };
    plus.onclick = () => {
      setExt(id, f.key, Math.min(hi, (extVal(id, f.key) ?? lo) + step));
      paint();
    };
    paint();
  } else if (f.type === 'select') {
    const opts = (f.options || []).map((o) =>
      o && typeof o === 'object' ? o : { value: o, label: o },
    );
    row.innerHTML =
      nameCell(f) +
      `<span class="spacer"></span><select>` +
      opts.map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('') +
      `</select>`;
    const sel = row.querySelector('select'),
      cur = extVal(id, f.key);
    if (cur != null && !opts.some((o) => String(o.value) === String(cur)))
      // keep an unknown saved value selectable
      sel.insertAdjacentHTML('beforeend', `<option value="${esc(cur)}">${esc(cur)}</option>`);
    sel.value = cur ?? (opts[0] ? opts[0].value : '');
    sel.onchange = () => setExt(id, f.key, sel.value);
  } else if (f.type === 'time' || f.type === 'text') {
    row.innerHTML =
      nameCell(f) +
      `<span class="spacer"></span>` +
      `<input type="${f.type === 'time' ? 'time' : 'text'}" class="text">`;
    const inp = row.querySelector('input');
    inp.value = extVal(id, f.key) ?? '';
    inp[f.type === 'time' ? 'onchange' : 'oninput'] = () => setExt(id, f.key, inp.value);
  } else {
    return null; // unknown type → render nothing, never a misleading text box
  }
  return row;
}

// A `list` field: a repeating editor over an array of objects (e.g. dates items).
// Sub-fields render by type: `text` → text input, `date` → native date picker (no free text).
// A `recurring` list pairs the date picker with an "every year" toggle: on → store MM-DD
// (recurs yearly), off → YYYY-MM-DD (one-off). Built programmatically — user text is set via
// .value / .textContent, never innerHTML, so nothing a user types can "escape".
function makeListEditor(id, f) {
  const wrap = document.createElement('div');
  const head = document.createElement('div');
  head.className = 'row';
  head.innerHTML =
    nameCell(f) +
    `<span class="spacer"></span><button class="sendnow" type="button">+ Add</button>`;
  const rows = document.createElement('div');
  wrap.append(head, rows);
  const items = () => extVal(id, f.key) || [];
  const SHRINK = 'flex:1;min-width:0;width:auto;text-align:left'; // shrink to fit a phone, never overflow

  function removeBtn(onClick) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'sendnow';
    b.setAttribute('aria-label', 'remove');
    b.style.cssText = 'flex:none;padding:10px 13px';
    b.textContent = '×';
    b.onclick = onClick;
    return b;
  }
  function textRow(item, sub, onRemove) {
    const line = document.createElement('div');
    line.className = 'litem-row';
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.className = 'text';
    inp.placeholder = sub.label;
    inp.style.cssText = SHRINK;
    inp.value = item[sub.key] ?? '';
    inp.oninput = () => {
      item[sub.key] = inp.value;
      onEdit();
    };
    line.append(inp);
    if (onRemove) line.append(removeBtn(onRemove));
    return line;
  }
  function dateRow(item, sub, onRemove) {
    const line = document.createElement('div');
    line.className = 'litem-row';
    const raw = item[sub.key] ?? '';
    let yearly = /^\d{2}-\d{2}$/.test(raw); // MM-DD stored → recurs yearly
    const di = document.createElement('input');
    di.type = 'date';
    di.className = 'text';
    di.style.cssText = SHRINK;
    di.value = yearly
      ? `${new Date().getFullYear()}-${raw}` // picker needs a full date
      : /^\d{4}-\d{2}-\d{2}$/.test(raw)
        ? raw
        : '';
    const writeBack = () => {
      item[sub.key] = !di.value ? '' : yearly ? di.value.slice(5) : di.value;
      onEdit();
    };
    di.onchange = writeBack;
    line.append(di);
    if (f.recurring) {
      const yr = document.createElement('button');
      yr.type = 'button';
      yr.className = 'yearly';
      const paint = () => {
        yr.classList.toggle('on', yearly);
        yr.textContent = yearly ? '⟳ every year' : 'every year';
      };
      yr.onclick = () => {
        yearly = !yearly;
        paint();
        writeBack();
      };
      paint();
      line.append(yr);
    }
    if (onRemove) line.append(removeBtn(onRemove));
    return line;
  }
  function render() {
    rows.innerHTML = '';
    items().forEach((item, i) => {
      const block = document.createElement('div');
      block.className = 'litem';
      const remove = () => {
        const a = items();
        a.splice(i, 1);
        setExt(id, f.key, a);
        render();
      };
      f.fields.forEach((sub, idx) => {
        const onRemove = idx === 0 ? remove : null; // × sits on the first sub-field's row
        block.append(
          sub.type === 'date' ? dateRow(item, sub, onRemove) : textRow(item, sub, onRemove),
        );
      });
      rows.appendChild(block);
    });
  }
  head.querySelector('button').onclick = () => {
    const a = items();
    a.push({});
    setExt(id, f.key, a);
    render();
  };
  render();
  return wrap;
}

// Rebuild every ext card from state.ext (controls read live state, so a fresh build = apply).
function renderExtCards() {
  const host = document.getElementById('extCards');
  if (!host) return;
  host.innerHTML = '';
  for (const [id, spec] of Object.entries(extSchema)) {
    const label = document.createElement('div');
    label.className = 'label';
    label.textContent = spec.title || title(id);
    const card = document.createElement('div');
    card.className = 'card';
    for (const f of spec.fields || []) {
      const el = makeControl(id, f);
      if (el) card.appendChild(el);
    }
    host.append(label, card);
  }
}

// ─── GitHub integration (Contents API + token in localStorage) ───
const LKEY = 'noterpiper_token';
const token = () => localStorage.getItem(LKEY) || '';
function repoSlug() {
  const h = location.hostname,
    p = location.pathname.split('/').filter(Boolean);
  if (h.endsWith('github.io')) return `${h.split('.')[0]}/${p[0] || ''}`;
  return 'Zulqarnain-cc34/noterpiper'; // local dev / custom-domain fallback
}
const API = () => `https://api.github.com/repos/${repoSlug()}`;
const ghHeaders = () => {
  const h = { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };
  if (token()) h.Authorization = `Bearer ${token()}`; // omit on public reads; required for write
  return h;
};
async function ghGet(path) {
  // no-store: GitHub's authenticated responses carry Cache-Control: max-age=60, which
  // would serve a STALE config.json sha right after a save → 409 on the next save.
  const r = await fetch(API() + path, { headers: ghHeaders(), cache: 'no-store' });
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
  return r.json();
}
async function ghFail(r) {
  // uniform GitHub error: status + API message when present
  let m = String(r.status);
  try {
    m += ` ${(await r.json()).message}`;
  } catch {}
  throw new Error(`GitHub ${m}`);
}
async function ghPut(path, body) {
  const r = await fetch(API() + path, {
    method: 'PUT',
    headers: { ...ghHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) await ghFail(r);
  return r.json();
}
// Your real location lives in private repo Variables (not the public config.json).
// These read/write it via the Actions Variables API — token needs "Variables: R&W".
async function ghGetVar(name) {
  if (!token()) return null; // Variables are private — need the token
  const r = await fetch(`${API()}/actions/variables/${name}`, {
    headers: ghHeaders(),
    cache: 'no-store',
  });
  if (r.status === 404) return null; // not set yet
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
  return (await r.json()).value;
}
async function ghSetVar(name, value) {
  let r = await fetch(`${API()}/actions/variables/${name}`, {
    method: 'PATCH',
    headers: { ...ghHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, value }),
  });
  if (r.status === 404)
    r = await fetch(`${API()}/actions/variables`, {
      // create if missing
      method: 'POST',
      headers: { ...ghHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, value }),
    });
  if (!r.ok) await ghFail(r);
}
function ghHint(e) {
  const m = e?.message || '';
  if (/403|not accessible|Resource not/i.test(m))
    return 'your token needs Contents + Variables (and Actions for Send now) — Read and write, this repo';
  if (/401|Bad credentials/i.test(m)) return 'the token is invalid or expired — paste a fresh one';
  if (/404/.test(m)) return 'not found — check the token’s repository access points at this repo';
  if (/409/.test(m)) return 'the file just changed — tap Save again';
  return m;
}

// The config.json content + sha our form state was derived from — saveNow PUTs with
// this sha so a concurrent writer produces a visible 409 instead of a silent clobber.
let loadedBase = null,
  loadedSha = null;
const setStatus = (t) => {
  document.getElementById('status').textContent = t;
};
function toast(msg, err) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast show${err ? ' err' : ''}`;
  setTimeout(() => {
    el.className = 'toast';
  }, 2000);
}
function applyState() {
  const g = (id) => document.getElementById(id);
  // A select keeps an out-of-range saved value selectable instead of silently dropping it.
  const setSel = (id, val, label = val) => {
    const sel = g(id);
    if (![...sel.options].some((o) => o.value === val)) {
      const o = document.createElement('option');
      o.value = val;
      o.textContent = label;
      sel.appendChild(o);
    }
    sel.value = val;
  };
  g('city').value = state.city;
  g('country').value = state.country;
  setSel('method', state.method, `Method ${state.method}`); // never drop an unlisted method
  setSel('nudgeTime', state.nudgeTime);
  g('nudgeEnabled').classList.toggle('off', !state.nudgeEnabled);
  g('streakVal').textContent = state.nudgeStreakRisk;
  g('nudgeDailies').classList.toggle('off', !state.nudgeDailies);
  g('nudgeHabits').classList.toggle('off', !state.nudgeHabits);
  g('nudgeTodos').classList.toggle('off', !state.nudgeTodos);
  if (document.activeElement !== g('nudgeWhitelist'))
    // never clobber mid-typing
    g('nudgeWhitelist').value = state.nudgeWhitelist;
  g('morningEnabled').classList.toggle('off', !state.morningEnabled);
  g('weeklyEnabled').classList.toggle('off', !state.weeklyEnabled);
  setSel('morningTime', state.morningTime);
  setSel('weeklyDay', state.weeklyDay);
  setSel('weeklyTime', state.weeklyTime);
  updateMorningWeeklyRows();
  g('ramEnabled').classList.toggle('off', !state.ramadanEnabled);
  g('suhoorVal').textContent = state.ramadanSuhoorLead;
  g('iftarVal').textContent = state.ramadanIftarLead;
  updateNudgeOpts();
  updateRamOpts();
  renderExtCards();
  syncGear();
}
// Cache the private location on this device so the NEXT load paints it instantly,
// instead of flashing the config.json placeholder while the Variables API responds.
const LOC_KEY = 'noterpiper_loc';
function readLocCache() {
  if (!token()) return null; // only meaningful when connected
  try {
    return JSON.parse(localStorage.getItem(LOC_KEY) || 'null');
  } catch {
    return null;
  }
}
function writeLocCache() {
  if (!token()) return;
  try {
    localStorage.setItem(
      LOC_KEY,
      JSON.stringify({
        city: state.city,
        country: state.country,
        method: state.method,
        timezone: state.timezone,
      }),
    );
  } catch {}
}
async function loadLocationFromVars() {
  if (!token()) return; // can't read private Variables without the token
  try {
    const [c, co, m, tz] = await Promise.all([
      // 4 variables in parallel (not one-by-one)
      ghGetVar('PRAYER_CITY'),
      ghGetVar('PRAYER_COUNTRY'),
      ghGetVar('PRAYER_METHOD'),
      ghGetVar('PRAYER_TIMEZONE'),
    ]);
    if (c) state.city = c;
    if (co) state.country = co;
    if (m) state.method = m;
    if (tz) state.timezone = tz;
  } catch (e) {
    toast(`Location: ${ghHint(e)}`, true);
  }
}
async function loadConfig() {
  const cached = readLocCache();
  await loadExtSchema(); // ext plugin schema → generic cards (best-effort)
  try {
    const d = await ghGet('/contents/config.json?ref=main'); // public read — no token needed
    const loaded = JSON.parse(decodeContent(d.content));
    loadedBase = loaded;
    loadedSha = d.sha; // what our state is derived from (see saveNow)
    state = fromConfig(loaded, extSchema);
    if (cached) {
      // instant: paint last-known real location, reveal now
      Object.assign(state, cached);
      renderPrayers();
      applyState();
      checkCity();
      document.body.classList.remove('loading');
    }
    await loadLocationFromVars(); // authoritative refresh from private Variables
    writeLocCache(); // remember it for next time
    renderPrayers();
    applyState();
    checkCity();
    setStatus(token() ? 'loaded ✓' : 'loaded · connect to see your location + save');
    firstRunPrompt(); // nothing set up yet → open Settings for them
  } catch (e) {
    setStatus('load failed');
    toast(`Load failed: ${e.message}`, true);
  } finally {
    document.body.classList.remove('loading');
  } // first-ever load reveals here (after Variables)
}
// On a genuinely fresh start (no saved city), open Settings once so the first thing the
// user sees is where to set location + connect — the one downside of hiding it behind ⚙.
let firstRunDone = false;
function firstRunPrompt() {
  if (firstRunDone) return;
  firstRunDone = true;
  if (!String(state.city || '').trim()) openSettings();
}
// ─── Autosave: any change schedules a debounced save (a burst → one save) ───
let userTouched = false,
  saveTimer = null,
  saving = false,
  dirtyAgain = false;
function onEdit() {
  userTouched = true;
  scheduleSave();
} // call from every control handler
function scheduleSave() {
  if (!userTouched) return; // ignore programmatic/load-time changes
  setStatus('unsaved…');
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => saveNow(true), 1200); // coalesce a burst of clicks into one save
}
// Stale-tab guard: browsers throttle a background tab's timers and fire them on wake —
// so a tab left open for hours would wake and autosave its old in-memory settings over
// everything saved since. Returning from a long sleep, drop any pending edit and
// reload instead; edits made minutes ago still save normally.
let hiddenAt = null;
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    hiddenAt = Date.now();
    return;
  }
  if (hiddenAt && isStale(Date.now() - hiddenAt) && !saving) {
    clearTimeout(saveTimer);
    userTouched = false;
    dirtyAgain = false;
    setStatus('refreshing…');
    loadConfig();
  }
  hiddenAt = null;
});
const doSave = () => saveNow(false); // the manual "Save changes" button
async function saveNow(auto = false) {
  const g = (id) => document.getElementById(id);
  if (!validTime(g('nudgeTime').value)) {
    if (!auto) toast('Enter a valid time (HH:MM)', true);
    return;
  }
  if (resolveState(g('city').value.trim(), pending, resolved) !== 'valid') {
    setStatus('unsaved · check the city');
    if (!auto) toast('Check the city — it must resolve first', true);
    return;
  }
  if (!token()) {
    setStatus('unsaved · connect to save');
    if (!auto) {
      openSettings();
      document.getElementById('connect').open = true;
      toast('Add your GitHub token first', true);
    }
    return;
  }
  if (saving) {
    dirtyAgain = true;
    return;
  } // a save is in flight — re-run once it's done
  saving = true;
  readForm();
  g('save').disabled = true;
  setStatus('saving…');
  try {
    // 1. location → private repo Variables (kept out of the public file)
    await ghSetVar('PRAYER_CITY', state.city);
    await ghSetVar('PRAYER_COUNTRY', state.country);
    await ghSetVar('PRAYER_METHOD', state.method);
    if (state.timezone) await ghSetVar('PRAYER_TIMEZONE', state.timezone);
    // 2. offsets + nudge → config.json (its location stays the public placeholder).
    // Optimistic concurrency: PUT with the sha our state was LOADED from. If another
    // device saved since, GitHub answers 409 — then we rebase this form onto the fresh
    // file, say so, and retry. (Pre-fetching a fresh sha here would make a stale
    // writer always "win" silently — that's exactly how a day-old tab once reverted
    // morning.enabled seconds after the phone turned it on.)
    for (let attempt = 0; ; attempt++) {
      if (!loadedSha) {
        // first save on a failed load
        const cur = await ghGet('/contents/config.json?ref=main');
        loadedBase = JSON.parse(decodeContent(cur.content));
        loadedSha = cur.sha;
      }
      const base = loadedBase || {};
      const next = toConfig(state, base);
      next.city = base.city;
      next.country = base.country; // keep placeholder; real location is in Variables
      next.method = base.method;
      next.timezone = base.timezone;
      try {
        const put = await ghPut('/contents/config.json', {
          message: 'Update settings via NoterPiper config page',
          content: encodeContent(next),
          sha: loadedSha,
          branch: 'main',
        });
        loadedBase = next;
        loadedSha = put.content.sha;
        // Read-your-write: repaint from what was actually persisted (location fields
        // keep their real on-screen values — the file only stores the placeholder).
        const loc = {
          city: state.city,
          country: state.country,
          method: state.method,
          timezone: state.timezone,
        };
        state = Object.assign(fromConfig(next, extSchema), loc);
        applyState();
        break;
      } catch (e) {
        if (attempt < 2 && /\b409\b/.test(e.message)) {
          // someone else saved since we loaded
          loadedSha = null; // → refetch, rebase this form, retry
          toast('Settings changed on another device — merged and saved');
          continue;
        }
        throw e;
      }
    }
    setStatus('saved ✓');
    if (!auto) toast('Saved ✓ · applies within ~5 min');
  } catch (e) {
    toast(`Save failed — ${ghHint(e)}`, true);
    setStatus('error');
  }
  saving = false;
  g('save').disabled = false;
  paint();
  if (dirtyAgain) {
    dirtyAgain = false;
    scheduleSave();
  } // flush changes made during the save
}

// One trigger behind every "send/test now" button: dispatch a workflow on main,
// keeping the button disabled while the request is in flight. The nudge buttons pass
// `kind` (evening/morning/weekly); the ramadan test passes no inputs.
async function dispatchWorkflow(file, inputs, btnId) {
  if (!token()) {
    openSettings();
    document.getElementById('connect').open = true;
    toast('Add your GitHub token first', true);
    return;
  }
  const b = document.getElementById(btnId);
  b.disabled = true;
  try {
    const r = await fetch(`${API()}/actions/workflows/${file}/dispatches`, {
      method: 'POST',
      headers: { ...ghHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main', ...(inputs ? { inputs } : {}) }),
    });
    if (!r.ok) await ghFail(r);
    toast('Sent ✓');
  } catch (e) {
    toast(`Send failed — ${ghHint(e)}`, true);
  }
  b.disabled = false;
}
const doNudge = (kind, btnId) => dispatchWorkflow('notify.yml', { kind }, btnId);
function updateNudgeOpts() {
  document.getElementById('nudgeOpts').style.display = state.nudgeEnabled ? 'block' : 'none';
}
function updateMorningWeeklyRows() {
  // the time/day pickers only matter when their nudge is on
  document.getElementById('morningTimeRow').style.display = state.morningEnabled ? '' : 'none';
  document.getElementById('weeklyDayRow').style.display = state.weeklyEnabled ? '' : 'none';
  document.getElementById('weeklyTimeRow').style.display = state.weeklyEnabled ? '' : 'none';
}
function updateRamOpts() {
  document.getElementById('ramOpts').style.display = state.ramadanEnabled ? 'block' : 'none';
}

// ─── Settings sheet: location + connection, opened from the ⚙ in the app bar ───
function openSettings() {
  document.getElementById('settingsSheet').classList.add('open');
  document.getElementById('settingsBackdrop').classList.add('open');
}
function closeSettings() {
  document.getElementById('settingsSheet').classList.remove('open');
  document.getElementById('settingsBackdrop').classList.remove('open');
}
function syncGear() {
  document.getElementById('gear').classList.toggle('needs', !token());
} // dot until connected
document.getElementById('gear').onclick = openSettings;
document.getElementById('settingsClose').onclick = closeSettings;
document.getElementById('settingsBackdrop').onclick = closeSettings;
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeSettings();
});

document.getElementById('saveToken').onclick = () => {
  const el = document.getElementById('token'),
    v = el.value.trim();
  if (!v) return;
  localStorage.setItem(LKEY, v);
  el.value = '';
  document.getElementById('connect').open = false;
  syncGear(); // clear the "needs setup" dot
  toast('Token saved on this device');
  loadConfig();
};
document.getElementById('save').onclick = doSave;
document.getElementById('sendEvening').onclick = () => doNudge('evening', 'sendEvening');
document.getElementById('sendMorning').onclick = () => doNudge('morning', 'sendMorning');
document.getElementById('sendWeekly').onclick = () => doNudge('weekly', 'sendWeekly');

renderMethods();
renderPrayers();
bind();
applyState();
checkCity();
loadConfig();
setTimeout(() => document.body.classList.remove('loading'), 6000); // safety: never leave the skeleton stuck
