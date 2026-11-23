// Harness for the config-page browser tests: a tiny static server for docs/ and a
// stubbed GitHub + Aladhan backend installed via Playwright request interception.
// No real network, no real repo — the page runs exactly as deployed, but every call
// it makes is captured and every response is a fixture.

import { readFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DOCS = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'docs');
const TYPES = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.json': 'application/json',
  '.webmanifest': 'application/manifest+json',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

// Serve docs/ on an ephemeral localhost port. On localhost the page's repoSlug()
// falls back to a fixed owner/repo, so the GitHub stub URLs are deterministic.
export function serveDocs() {
  const server = http.createServer(async (req, res) => {
    const name = req.url.split('?')[0].replace(/^\/+/, '') || 'index.html';
    try {
      const file = path.join(DOCS, path.normalize(name));
      if (!file.startsWith(DOCS)) throw new Error('traversal');
      const body = await readFile(file);
      res.writeHead(200, {
        'content-type': TYPES[path.extname(file)] || 'application/octet-stream',
      });
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end('not found');
    }
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      resolve({
        origin: `http://127.0.0.1:${server.address().port}`,
        close: () => new Promise((r) => server.close(r)),
      });
    });
  });
}

// A realistic keyed-shape config fixture with distinctive values the tests assert on.
export function fixtureConfig() {
  return {
    city: 'Makkah',
    country: 'Saudi Arabia',
    method: '4',
    timezone: 'Asia/Riyadh',
    prayer: {
      madhab: 'standard', // non-default, so "loads and paints" tests actually prove it round-trips
      reminders: {
        Fajr: { before_end: 30 },
        Zohar: { before_end: 30 },
        Asr: { before_end: 30 },
        Maghrib: { before_end: 30 },
        Isha: { after_start: 60 },
      },
    },
    habitica: {
      time: '22:30',
      enabled: true,
      streak_risk: 21,
      notify_dailies: true,
      notify_habits: false,
      notify_todos: true,
      tag_whitelist: ['deen'],
      morning: { enabled: true, time: '06:00' },
      weekly: { enabled: false, day: 'Sunday', time: '19:00' },
    },
    ramadan: { enabled: true, suhoor_lead: 45, iftar_lead: 0 }, // on → its Test button is visible
    dates: { enabled: true, lead_days: 3, time: '09:00', window: 5, items: [] },
  };
}

const b64 = (obj) => Buffer.from(`${JSON.stringify(obj, null, 2)}\n`).toString('base64');

// Install the fake backend on a page. Returns live capture arrays:
//   puts       — every config.json PUT: { sha, config }
//   dispatches — every workflow dispatch: { workflow, body }
// With conflict: true, the FIRST PUT answers 409 and later config GETs serve sha2
// with an altered file — reproducing "another device saved while you were editing".
export async function stubBackend(page, { config = fixtureConfig(), conflict = false } = {}) {
  const puts = [];
  const dispatches = [];
  let conflicted = false;
  const altered = structuredClone(config);
  altered.habitica = { ...altered.habitica, time: '22:00' }; // the other device's change

  await page.route('**/sw.js', (r) => r.abort()); // keep the service worker out of tests
  await page.route('https://api.aladhan.com/**', (r) =>
    r.fulfill({
      json: {
        data: {
          // meta.timezone is what marks the city "resolved" — without it the page
          // refuses to save (checkCity sets `resolved = meta.timezone`).
          meta: { timezone: 'Asia/Riyadh' },
          date: { hijri: { month: { number: 2 } } },
          timings: {
            Fajr: '05:00',
            Sunrise: '06:15',
            Dhuhr: '12:00',
            Asr: '15:00',
            Maghrib: '17:30',
            Isha: '19:00',
            Midnight: '23:30',
          },
        },
      },
    }),
  );
  await page.route('https://api.github.com/**', (route) => {
    const req = route.request();
    const url = req.url();
    const method = req.method();
    if (url.includes('/contents/config.json') && method === 'GET')
      return route.fulfill({
        json: conflicted
          ? { sha: 'sha2', content: b64(altered) }
          : { sha: 'sha1', content: b64(config) },
      });
    if (url.includes('/contents/config.json') && method === 'PUT') {
      const body = JSON.parse(req.postData());
      puts.push({
        sha: body.sha,
        config: JSON.parse(Buffer.from(body.content, 'base64').toString('utf8')),
      });
      if (conflict && !conflicted) {
        conflicted = true; // first writer loses: someone else saved since sha1
        return route.fulfill({ status: 409, json: { message: 'is at sha2 but expected sha1' } });
      }
      return route.fulfill({ json: { content: { sha: 'sha3' } } });
    }
    if (url.includes('/actions/workflows/') && method === 'POST') {
      dispatches.push({
        workflow: url.split('/workflows/')[1].split('/')[0],
        body: JSON.parse(req.postData() || '{}'),
      });
      return route.fulfill({ status: 204, body: '' });
    }
    if (url.includes('/actions/variables'))
      return route.fulfill({ json: method === 'GET' ? { value: '' } : {} });
    return route.fulfill({ status: 404, json: { message: `unstubbed ${method} ${url}` } });
  });
  // The save path needs a token; seeded before any page script runs.
  await page.addInitScript(() => localStorage.setItem('noterpiper_token', 'TEST'));
  return { puts, dispatches };
}

// Navigate and wait until the page has loaded config + painted (status says so).
export async function openPage(page, origin) {
  await page.goto(`${origin}/index.html`);
  await page.waitForFunction(
    () => document.getElementById('status').textContent.startsWith('loaded'),
    null,
    { timeout: 10_000 },
  );
}
