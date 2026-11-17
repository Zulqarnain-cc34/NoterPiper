import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  CITIES,
  COUNTRIES,
  encodeContent,
  fromConfig,
  maxOffset,
  prayerWindows,
  resolveState,
  toConfig,
  validTime,
} from './app.js';

test('toConfig writes the keyed shape — habitica section, reminders under prayer', () => {
  const c = toConfig({
    city: 'Makkah',
    country: 'Saudi Arabia',
    method: '4',
    timezone: 'Asia/Riyadh',
    reminders: { Isha: { after_start: 60 } },
    nudgeTime: '21:30',
    nudgeEnabled: false,
  });
  assert.equal(c.habitica.enabled, false);
  assert.equal(typeof c.habitica.enabled, 'boolean');
  assert.equal(c.habitica.time, '21:30');
  assert.deepEqual(c.prayer.reminders, { Isha: { after_start: 60 } }); // reminders live under prayer
  assert.equal(c.nudge, undefined); // legacy section dropped on save
  assert.equal(c.reminders, undefined); // legacy top-level reminders dropped
  assert.equal(c.city, 'Makkah');
});

test('fromConfig/toConfig migrates a legacy file to keyed + preserves unknown keys', () => {
  const legacy = {
    city: 'X',
    country: 'Y',
    method: '1',
    timezone: 'Z',
    reminders: { Isha: { after_start: 60 } },
    nudge: { time: '21:30', enabled: true },
    _future: 'keep',
  };
  const back = toConfig(fromConfig(legacy), legacy);
  assert.equal(back._future, 'keep'); // unknown top-level key survives
  assert.equal(back.habitica.enabled, true); // nudge -> habitica
  assert.deepEqual(back.prayer.reminders, { Isha: { after_start: 60 } });
  assert.equal(back.nudge, undefined); // legacy removed
  assert.equal(back.reminders, undefined);
  assert.equal(back.city, 'X');
});

test('fromConfig reads the at-risk streak — keyed habitica, and legacy nudge', () => {
  assert.equal(fromConfig({}).nudgeStreakRisk, 7); // default
  assert.equal(fromConfig({ habitica: { streak_risk: 14 } }).nudgeStreakRisk, 14); // new
  assert.equal(fromConfig({ nudge: { streak_risk: 9 } }).nudgeStreakRisk, 9); // legacy still read
});

test('toConfig writes the at-risk streak threshold as a number', () => {
  const c = toConfig({
    city: 'Makkah',
    country: 'Saudi Arabia',
    method: '4',
    timezone: 'Asia/Riyadh',
    reminders: {},
    nudgeTime: '21:30',
    nudgeEnabled: true,
    nudgeStreakRisk: 10,
  });
  assert.equal(c.habitica.streak_risk, 10);
  assert.equal(typeof c.habitica.streak_risk, 'number');
});

test('fromConfig reads the ramadan controls with safe defaults', () => {
  const on = fromConfig({});
  assert.equal(on.ramadanEnabled, true);
  assert.equal(on.ramadanSuhoorLead, 45);
  assert.equal(on.ramadanIftarLead, 0);
  const set = fromConfig({ ramadan: { enabled: false, suhoor_lead: 30, iftar_lead: 10 } });
  assert.equal(set.ramadanEnabled, false);
  assert.equal(set.ramadanSuhoorLead, 30);
  assert.equal(set.ramadanIftarLead, 10);
});

test('toConfig writes the ramadan controls as real values', () => {
  const c = toConfig({
    city: 'Makkah',
    country: 'Saudi Arabia',
    method: '4',
    timezone: 'Asia/Riyadh',
    reminders: {},
    nudgeTime: '21:30',
    nudgeEnabled: true,
    ramadanEnabled: false,
    ramadanSuhoorLead: 30,
    ramadanIftarLead: 15,
  });
  assert.equal(c.ramadan.enabled, false);
  assert.equal(typeof c.ramadan.enabled, 'boolean');
  assert.equal(c.ramadan.suhoor_lead, 30);
  assert.equal(c.ramadan.iftar_lead, 15);
});

test('fromConfig hydrates schema-driven (ext) plugins: defaults ← saved config', () => {
  const schema = { dates: { defaults: { enabled: true, lead_days: 3, items: [] } } };
  const st = fromConfig(
    { dates: { lead_days: 7, items: [{ label: 'X', date: '01-01' }] } },
    schema,
  );
  assert.equal(st.ext.dates.enabled, true); // untouched default
  assert.equal(st.ext.dates.lead_days, 7); // saved override wins
  assert.deepEqual(st.ext.dates.items, [{ label: 'X', date: '01-01' }]);
});

test('toConfig writes ext plugins back into config[id], preserving base', () => {
  const c = toConfig(
    {
      city: 'M',
      country: 'S',
      method: '4',
      timezone: 'Z',
      reminders: {},
      nudgeTime: '21:30',
      nudgeEnabled: true,
      nudgeStreakRisk: 7,
      ext: { dates: { enabled: false, lead_days: 5, items: [] } },
    },
    { dates: { _keep: 1 } },
  );
  assert.equal(c.dates.enabled, false);
  assert.equal(c.dates.lead_days, 5);
  assert.equal(c.dates._keep, 1); // base key survives
});

test('no ext plugins → nothing extra written', () => {
  const st = fromConfig({});
  assert.deepEqual(st.ext, {});
  const c = toConfig({
    city: '',
    country: '',
    method: '1',
    timezone: '',
    reminders: {},
    nudgeTime: '21:30',
    nudgeEnabled: true,
    nudgeStreakRisk: 7,
  });
  assert.equal(c.dates, undefined);
});

test('validTime accepts HH:MM, rejects junk and out-of-range', () => {
  assert.equal(validTime('21:30'), true);
  assert.equal(validTime('9pm'), false);
  assert.equal(validTime('99:99'), false);
  assert.equal(validTime(''), false);
});

test('resolveState maps the four UI states', () => {
  assert.equal(resolveState('', false, null), 'empty');
  assert.equal(resolveState('Mak', true, null), 'typing'); // check pending
  assert.equal(resolveState('Makkah', false, 'Asia/Riyadh'), 'valid');
  assert.equal(resolveState('asdf', false, null), 'unknown');
});

test('COUNTRIES is a non-trivial list including Turkey', () => {
  assert.ok(Array.isArray(COUNTRIES) && COUNTRIES.length > 100);
  assert.ok(COUNTRIES.includes('Turkey'));
});

test('encodeContent is base64 of pretty JSON with a trailing newline', () => {
  const obj = { city: 'Makkah', nudge: { time: '21:30', enabled: true } };
  const b64 = encodeContent(obj);
  const text = new TextDecoder().decode(Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)));
  assert.equal(text, `${JSON.stringify(obj, null, 2)}\n`); // clean, diff-friendly
  assert.deepEqual(JSON.parse(text), obj);
});

test('CITIES pairs each city with its country', () => {
  assert.ok(CITIES.length > 30);
  assert.deepEqual(
    CITIES.find(([c]) => c === 'Istanbul'),
    ['Istanbul', 'Turkey'],
  );
  assert.ok(CITIES.every(([c, co]) => c && co));
});

test('prayerWindows computes each window in minutes, wrapping midnight', () => {
  const t = {
    Fajr: '05:00',
    Sunrise: '06:30',
    Dhuhr: '12:00',
    Asr: '15:30',
    Maghrib: '17:30',
    Isha: '19:00',
    Midnight: '00:00',
  };
  const w = prayerWindows(t);
  assert.equal(w.Fajr, 90); // 05:00 -> 06:30
  assert.equal(w.Maghrib, 90); // 17:30 -> 19:00
  assert.equal(w.Isha, 300); // 19:00 -> 00:00 next day
});

test('maxOffset leaves a margin, rounds to 5, caps when unknown', () => {
  assert.equal(maxOffset(90), 80);
  assert.equal(maxOffset(300), 290);
  assert.equal(maxOffset(0), 120); // not resolved yet
});
