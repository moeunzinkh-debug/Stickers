import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/index.js';

const env = { RENDER_ORIGIN: 'https://example.onrender.com', TELEGRAM_WEBHOOK_SECRET: 'secret' };
const request = (secret = 'secret') => new Request('https://worker.example/webhook', {
  method: 'POST', headers: { 'X-Telegram-Bot-Api-Secret-Token': secret, 'Content-Type': 'application/json' }, body: '{"update_id":1}',
});

test('validates routes and webhook secret', async () => {
  assert.equal((await worker.fetch(new Request('https://worker.example/'), env)).status, 200);
  assert.equal((await worker.fetch(new Request('https://worker.example/other'), env)).status, 404);
  assert.equal((await worker.fetch(request('wrong'), env)).status, 401);
  assert.equal((await worker.fetch(request(), {})).status, 503);
  assert.equal((await worker.fetch(request(), { ...env, RENDER_ORIGIN: 'http://example.com' })).status, 503);
});

test('forwards authenticated request and preserves backend response', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, 'https://example.onrender.com/webhook');
      assert.equal(options.headers['X-Telegram-Bot-Api-Secret-Token'], 'secret');
      assert.equal(await new Response(options.body).text(), '{"update_id":1}');
      return new Response('retry', { status: 503 });
    };
    assert.equal((await worker.fetch(request(), env)).status, 503);
  } finally { globalThis.fetch = original; }
});
