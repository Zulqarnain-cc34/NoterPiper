// Browser tests for the config page (docs/index.html) — the DOM/network layer the
// pure-logic tests in docs/ can't reach. Real page, headless Chromium, stubbed
// GitHub + Aladhan backend (see helpers.mjs). Each test is: stub → open → act like a
// user → assert on what the page rendered and what it sent.
//
// Every test here pins a regression that previously shipped: values not painting,
// a toggle reverting on save, rows wrong on first paint, and the stale-writer
// clobber that silenced the 06:00 morning brief.

import assert from 'node:assert/strict';
import { after, before, beforeEach, test } from 'node:test';
import { chromium } from 'playwright';
import { fixtureConfig, openPage, serveDocs, stubBackend } from './helpers.mjs';

let browser;
let server;
let context;
let page;

before(async () => {
  browser = await chromium.launch();
  server = await serveDocs();
});
after(async () => {
  await browser.close();
  await server.close();
});
beforeEach(async () => {
  if (context) await context.close();
  context = await browser.newContext();
  page = await context.newPage();
});

const toggleOn = (id) =>
  page.evaluate((i) => !document.getElementById(i).classList.contains('off'), id);
const rowVisible = (id) =>
  page.evaluate((i) => document.getElementById(i).style.display !== 'none', id);
const value = (id) => page.evaluate((i) => document.getElementById(i).value, id);
const text = (id) => page.evaluate((i) => document.getElementById(i).textContent, id);

test('loading paints every habitica control from config.json', async () => {
  await stubBackend(page);
  await openPage(page, server.origin);

  assert.equal(await value('nudgeTime'), '22:30');
  assert.equal(await text('streakVal'), '21');
  assert.equal(await toggleOn('nudgeEnabled'), true);
  assert.equal(await toggleOn('nudgeDailies'), true);
  assert.equal(await toggleOn('nudgeHabits'), false); // fixture switches habits off
  assert.equal(await toggleOn('nudgeTodos'), true);
  assert.equal(await value('nudgeWhitelist'), 'deen');
  assert.equal(await toggleOn('morningEnabled'), true);
  assert.equal(await rowVisible('morningTimeRow'), true); // morning on → picker shown
  assert.equal(await value('morningTime'), '06:00');
  assert.equal(await toggleOn('weeklyEnabled'), false);
  assert.equal(await rowVisible('weeklyDayRow'), false); // weekly off → pickers hidden
  assert.equal(await rowVisible('weeklyTimeRow'), false);
});

test('a filter toggle saves once and does not revert', async () => {
  const { puts } = await stubBackend(page);
  await openPage(page, server.origin);

  await page.click('#nudgeDailies'); // user switches dailies off
  await page.waitForFunction(
    () => document.getElementById('status').textContent === 'saved ✓',
    null,
    { timeout: 10_000 },
  );

  assert.equal(puts.length, 1, 'exactly one save');
  assert.equal(puts[0].config.habitica.notify_dailies, false, 'the change was persisted');
  assert.equal(puts[0].config.habitica.notify_habits, false, 'untouched settings preserved');
  assert.equal(await toggleOn('nudgeDailies'), false, 'the toggle did not revert');
});

test('morning and weekly pickers appear only while their nudge is on', async () => {
  await stubBackend(page);
  await openPage(page, server.origin);

  await page.click('#morningEnabled'); // on → off
  assert.equal(await rowVisible('morningTimeRow'), false);
  await page.click('#weeklyEnabled'); // off → on
  assert.equal(await rowVisible('weeklyDayRow'), true);
  assert.equal(await rowVisible('weeklyTimeRow'), true);
  assert.equal(await value('weeklyDay'), 'Sunday');
  assert.equal(await value('weeklyTime'), '19:00');
});

test('each send button dispatches its workflow with the right kind', async () => {
  const { dispatches } = await stubBackend(page);
  await openPage(page, server.origin);

  for (const id of ['sendEvening', 'sendMorning', 'sendWeekly', 'ramTest']) {
    await page.click(`#${id}`);
    await page.waitForFunction((btn) => !document.getElementById(btn).disabled, id, {
      timeout: 5_000,
    });
  }

  assert.deepEqual(
    dispatches.map((d) => [d.workflow, d.body.inputs?.kind]),
    [
      ['notify.yml', 'evening'],
      ['notify.yml', 'morning'],
      ['notify.yml', 'weekly'],
      ['ramadan.yml', undefined], // the ramadan test passes no inputs
    ],
  );
  for (const d of dispatches) assert.equal(d.body.ref, 'main');
});

test('a concurrent writer causes a visible merge, not a silent clobber', async () => {
  // The 06:00-morning-brief incident: user enables a toggle while another device
  // saved meanwhile. Expect: first PUT with the loaded sha → 409 → toast → retry on
  // the fresh sha → the user's edit survives.
  const config = fixtureConfig();
  config.habitica.morning.enabled = false; // user is about to enable it
  const { puts } = await stubBackend(page, { config, conflict: true });
  await openPage(page, server.origin);

  const sawToast = page.waitForFunction(
    () => document.getElementById('toast').textContent.includes('changed on another device'),
    null,
    { timeout: 10_000 },
  );
  await page.click('#morningEnabled');
  await sawToast;
  await page.waitForFunction(
    () => document.getElementById('status').textContent === 'saved ✓',
    null,
    { timeout: 10_000 },
  );

  assert.equal(puts.length, 2, 'first attempt conflicted, second succeeded');
  assert.equal(puts[0].sha, 'sha1', 'first PUT used the sha the form was loaded from');
  assert.equal(puts[1].sha, 'sha2', 'retry rebased onto the fresh sha');
  assert.equal(puts[1].config.habitica.morning.enabled, true, 'the edit survived the merge');
  assert.equal(await toggleOn('morningEnabled'), true, 'the toggle did not revert');
});

test('whitelist text, evening time, and streak stepper all persist', async () => {
  const { puts } = await stubBackend(page);
  await openPage(page, server.origin);

  await page.fill('#nudgeWhitelist', 'deen, quran');
  await page.selectOption('#nudgeTime', '22:00');
  await page.click('#streakStepper button[data-step="1"]'); // 21 → 22
  await page.waitForFunction(
    () => document.getElementById('status').textContent === 'saved ✓',
    null,
    { timeout: 10_000 },
  );

  const h = puts.at(-1).config.habitica;
  assert.deepEqual(h.tag_whitelist, ['deen', 'quran'], 'comma text saved as a parsed list');
  assert.equal(h.time, '22:00');
  assert.equal(h.streak_risk, 22);
});

test('morning time picker persists into the morning section', async () => {
  const { puts } = await stubBackend(page);
  await openPage(page, server.origin);

  await page.selectOption('#morningTime', '05:30');
  await page.waitForFunction(
    () => document.getElementById('status').textContent === 'saved ✓',
    null,
    { timeout: 10_000 },
  );

  assert.deepEqual(puts.at(-1).config.habitica.morning, { enabled: true, time: '05:30' });
});

test('a prayer offset stepper and the before/after flip save under prayer.reminders', async () => {
  const { puts } = await stubBackend(page);
  await openPage(page, server.origin);

  const fajr = '#prayers .prow[data-prayer="Fajr"]';
  await page.click(`${fajr} button[data-step="5"]`); // 30 → 35 min
  await page.click(`${fajr} .mode`); // before the end → after the start
  await page.waitForFunction(
    () => document.getElementById('status').textContent === 'saved ✓',
    null,
    { timeout: 10_000 },
  );

  assert.deepEqual(puts.at(-1).config.prayer.reminders.Fajr, { after_start: 35 });
});

test('the settings sheet saves a token and reloads config with it', async () => {
  await stubBackend(page);
  // No token this time: the page must load read-only and prompt for connection.
  await page.addInitScript(() => localStorage.removeItem('noterpiper_token'));
  await page.goto(`${server.origin}/index.html`);
  await page.waitForFunction(
    () => document.getElementById('status').textContent.startsWith('loaded'),
    null,
    { timeout: 10_000 },
  );
  assert.match(await text('status'), /connect/, 'read-only load asks to connect');

  await page.click('#gear');
  await page.waitForSelector('#settingsSheet.open', { timeout: 5_000 });
  await page.evaluate(() => {
    document.getElementById('connect').open = true;
  }); // expand the Connect section
  await page.fill('#token', 'tok-from-sheet');
  await page.click('#saveToken');
  await page.waitForFunction(
    () => document.getElementById('status').textContent === 'loaded ✓',
    null,
    { timeout: 10_000 },
  );

  assert.equal(
    await page.evaluate(() => localStorage.getItem('noterpiper_token')),
    'tok-from-sheet',
  );
  assert.equal(await value('token'), '', 'the token input is cleared after saving');
});

// Drive a hide→(minutes pass)→show cycle with a controlled clock, so the page's
// visibilitychange stale-tab guard sees exactly `hiddenMinutes` of elapsed time.
// (Browsers freeze a background tab's timers and fire them on wake — the guard drops
// a stale pending edit instead of letting it clobber newer saves; see isStale().)
const hideFor = (minutes) =>
  page.evaluate((mins) => {
    const realNow = Date.now;
    const base = realNow();
    Date.now = () => base; // freeze at hide time → hiddenAt = base
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    Date.now = () => base + mins * 60 * 1000; // wake `mins` later
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    Date.now = realNow;
  }, minutes);

test('a long-hidden tab drops its pending edit and reloads instead of clobbering', async () => {
  const { puts } = await stubBackend(page);
  await openPage(page, server.origin);
  assert.equal(await toggleOn('nudgeHabits'), false, 'fixture baseline: habits off');

  await page.click('#nudgeHabits'); // user edits → autosave scheduled (1200ms debounce)
  assert.equal(await toggleOn('nudgeHabits'), true);

  await hideFor(6); // longer than the 5-min staleness limit → guard reloads

  await page.waitForFunction(
    () => document.getElementById('status').textContent === 'loaded ✓',
    null,
    { timeout: 10_000 },
  );
  assert.equal(puts.length, 0, 'the stale pending edit was never saved');
  assert.equal(await toggleOn('nudgeHabits'), false, 'edit dropped; server state repainted');
});

test('a briefly hidden tab keeps its pending edit and saves normally', async () => {
  const { puts } = await stubBackend(page);
  await openPage(page, server.origin);

  await page.click('#nudgeHabits'); // edit → autosave scheduled
  await hideFor(2); // under the limit → guard must NOT interfere

  await page.waitForFunction(
    () => document.getElementById('status').textContent === 'saved ✓',
    null,
    { timeout: 10_000 },
  );
  assert.equal(puts.length, 1, 'the edit survived a brief hide and saved');
  assert.equal(puts[0].config.habitica.notify_habits, true);
  assert.equal(await toggleOn('nudgeHabits'), true);
});
