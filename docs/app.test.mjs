import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toConfig, fromConfig, validTime, resolveState, COUNTRIES, CITIES, encodeContent, prayerWindows, maxOffset } from './app.js';

test('toConfig emits a real boolean nudge.enabled (not a string)', () => {
  const c = toConfig({
    city: 'Makkah', country: 'Saudi Arabia', method: '4', timezone: 'Asia/Riyadh',
    reminders: { Isha: { after_start: 60 } }, nudgeTime: '21:30', nudgeEnabled: false,
  });
  assert.equal(c.nudge.enabled, false);
  assert.equal(typeof c.nudge.enabled, 'boolean');
  assert.equal(c.nudge.time, '21:30');
  assert.equal(c.city, 'Makkah');
});

test('fromConfig/toConfig round-trips and preserves unknown keys', () => {
  const orig = {
    city: 'X', country: 'Y', method: '1', timezone: 'Z',
    reminders: { Isha: { after_start: 60 } },
    nudge: { time: '21:30', enabled: true }, _future: 'keep',
  };
  const back = toConfig(fromConfig(orig), orig);
  assert.equal(back._future, 'keep');          // unknown top-level key survives
  assert.equal(back.nudge.enabled, true);
  assert.equal(back.city, 'X');
});

test('fromConfig reads the habitica controls with safe defaults', () => {
  const on = fromConfig({});                          // nothing set → defaults
  assert.equal(on.nudgeStreakRisk, 7);
  assert.equal(on.nudgeShowTodos, true);
  assert.equal(on.nudgeShowDailies, true);
  assert.equal(on.nudgeShowPrayers, true);
  const set = fromConfig({ nudge: { streak_risk: 14, show_todos: false, show_dailies: false, show_prayers: false } });
  assert.equal(set.nudgeStreakRisk, 14);
  assert.equal(set.nudgeShowTodos, false);
  assert.equal(set.nudgeShowDailies, false);
  assert.equal(set.nudgeShowPrayers, false);
});

test('toConfig writes the habitica controls as real values', () => {
  const c = toConfig({
    city: 'Makkah', country: 'Saudi Arabia', method: '4', timezone: 'Asia/Riyadh',
    reminders: {}, nudgeTime: '21:30', nudgeEnabled: true,
    nudgeStreakRisk: 10, nudgeShowTodos: false, nudgeShowDailies: true, nudgeShowPrayers: false,
  });
  assert.equal(c.nudge.streak_risk, 10);
  assert.equal(c.nudge.show_todos, false);
  assert.equal(typeof c.nudge.show_todos, 'boolean');
  assert.equal(c.nudge.show_dailies, true);
  assert.equal(c.nudge.show_prayers, false);
});

test('validTime accepts HH:MM, rejects junk and out-of-range', () => {
  assert.equal(validTime('21:30'), true);
  assert.equal(validTime('9pm'), false);
  assert.equal(validTime('99:99'), false);
  assert.equal(validTime(''), false);
});

test('resolveState maps the four UI states', () => {
  assert.equal(resolveState('', false, null), 'empty');
  assert.equal(resolveState('Mak', true, null), 'typing');        // check pending
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
  const text = new TextDecoder().decode(Uint8Array.from(atob(b64), c => c.charCodeAt(0)));
  assert.equal(text, JSON.stringify(obj, null, 2) + '\n');   // clean, diff-friendly
  assert.deepEqual(JSON.parse(text), obj);
});

test('CITIES pairs each city with its country', () => {
  assert.ok(CITIES.length > 30);
  assert.deepEqual(CITIES.find(([c]) => c === 'Istanbul'), ['Istanbul', 'Turkey']);
  assert.ok(CITIES.every(([c, co]) => c && co));
});

test('prayerWindows computes each window in minutes, wrapping midnight', () => {
  const t = { Fajr:'05:00', Sunrise:'06:30', Dhuhr:'12:00', Asr:'15:30', Maghrib:'17:30', Isha:'19:00', Midnight:'00:00' };
  const w = prayerWindows(t);
  assert.equal(w.Fajr, 90);        // 05:00 -> 06:30
  assert.equal(w.Maghrib, 90);     // 17:30 -> 19:00
  assert.equal(w.Isha, 300);       // 19:00 -> 00:00 next day
});

test('maxOffset leaves a margin, rounds to 5, caps when unknown', () => {
  assert.equal(maxOffset(90), 80);
  assert.equal(maxOffset(300), 290);
  assert.equal(maxOffset(0), 120);     // not resolved yet
});
