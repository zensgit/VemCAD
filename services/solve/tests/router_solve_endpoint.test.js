import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createSolveServer, statusForResult } from '../server.mjs';

// These tests exercise the server's HTTP contract (routing + exit-code -> status
// mapping + envelope passthrough) WITHOUT the real solver: a fake CLI scripts the
// (stdout, exit) pairs. The real solver end-to-end lives in tools/ (not node --test).
const FAKE = fileURLToPath(new URL('./fixtures/fake_solve_cli.mjs', import.meta.url));

function withServer(opts, fn) {
  const server = createSolveServer(typeof opts === 'string' ? { cliPath: opts } : opts);
  return new Promise((resolve, reject) => {
    server.listen(0, async () => {
      const base = `http://127.0.0.1:${server.address().port}`;
      try {
        await fn(base);
        resolve();
      } catch (e) {
        reject(e);
      } finally {
        server.closeAllConnections?.();
        server.close();
      }
    });
  });
}
const post = (base, body) => fetch(`${base}/solve`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: typeof body === 'string' ? body : JSON.stringify(body),
});

test('statusForResult maps exit/error_code per the contract', () => {
  assert.equal(statusForResult(0, { ok: true }), 200);
  assert.equal(statusForResult(2, { ok: false, error_code: 'UNSUPPORTED_PROJECT_UNIT' }), 400);
  assert.equal(statusForResult(1, { ok: false, error_code: 'SOLVE_UNSATISFIED' }), 422);
  assert.equal(statusForResult(1, { ok: false, error_code: 'SOLVE_FAILED' }), 500);
  assert.equal(statusForResult(99, {}), 500);
});

test('POST /solve maps a solved run (exit 0) to 200 and passes the envelope through verbatim', () => withServer(FAKE, async (base) => {
  const envelope = { ok: true, value: { solve: { ok: true, iterations: 2 } }, diagnostics: [] };
  const res = await post(base, { exit: 0, stdout: envelope });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('content-type'), 'application/json; charset=utf-8');
  assert.deepEqual(await res.json(), envelope);
}));

test('POST /solve maps bad input (exit 2) to 400', () => withServer(FAKE, async (base) => {
  const res = await post(base, { exit: 2, stdout: { ok: false, error_code: 'UNSUPPORTED_PROJECT_UNIT', diagnostics: [] } });
  assert.equal(res.status, 400);
  assert.equal((await res.json()).error_code, 'UNSUPPORTED_PROJECT_UNIT');
}));

test('POST /solve maps SOLVE_UNSATISFIED (exit 1) to 422 (the sketch is unsolvable)', () => withServer(FAKE, async (base) => {
  const res = await post(base, { exit: 1, stdout: { ok: false, error_code: 'SOLVE_UNSATISFIED', analysis: { conflict_group_count: 1 }, diagnostics: [] } });
  assert.equal(res.status, 422);
  assert.equal((await res.json()).analysis.conflict_group_count, 1);
}));

test('POST /solve maps SOLVE_FAILED (exit 1, server-side failure) to 500 — NOT 422', () => withServer(FAKE, async (base) => {
  const res = await post(base, { exit: 1, stdout: { ok: false, error_code: 'SOLVE_FAILED', error: 'binary missing', diagnostics: [] } });
  assert.equal(res.status, 500);
}));

test('POST /solve with a malformed JSON body -> CLI exits 2 -> 400', () => withServer(FAKE, async (base) => {
  const res = await post(base, 'not json at all');
  assert.equal(res.status, 400);
}));

test('POST /solve maps non-JSON CLI output to 500 ROUTER_BAD_CLI_OUTPUT', () => withServer(FAKE, async (base) => {
  const res = await post(base, { raw_stdout: 'garbage, not json', exit: 0 });
  assert.equal(res.status, 500);
  assert.equal((await res.json()).error_code, 'ROUTER_BAD_CLI_OUTPUT');
}));

test('a spawn failure (bogus node command) -> 500 ROUTER_SPAWN_FAILED', () => withServer({ command: '/no/such/node-binary', cliPath: FAKE }, async (base) => {
  const res = await post(base, { exit: 0 });
  assert.equal(res.status, 500);
  assert.equal((await res.json()).error_code, 'ROUTER_SPAWN_FAILED');
}));

test('exit 0 but envelope.ok!==true (CLI drift) -> 500 ROUTER_BAD_CLI_OUTPUT, never 200+failed body', () => withServer(FAKE, async (base) => {
  const res = await post(base, { exit: 0, stdout: { ok: false, error_code: 'SOLVE_UNSATISFIED' } });
  assert.equal(res.status, 500);
  const body = await res.json();
  assert.equal(body.error_code, 'ROUTER_BAD_CLI_OUTPUT');
  assert.equal(body.envelope.error_code, 'SOLVE_UNSATISFIED'); // original kept for debugging
}));

test('failure exit but envelope.ok===true (the other drift direction) -> 500 ROUTER_BAD_CLI_OUTPUT', () => withServer(FAKE, async (base) => {
  const res = await post(base, { exit: 1, stdout: { ok: true } });
  assert.equal(res.status, 500);
  assert.equal((await res.json()).error_code, 'ROUTER_BAD_CLI_OUTPUT');
}));

test('GET /health -> 200 {ok:true}; wrong method -> 405; unknown path -> 404', () => withServer(FAKE, async (base) => {
  const health = await fetch(`${base}/health`);
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), { ok: true });
  assert.equal((await fetch(`${base}/solve`, { method: 'GET' })).status, 405);
  assert.equal((await fetch(`${base}/nope`)).status, 404);
}));

test('POST /solve-cadgf routes to the CADGF-PROJ cli and maps exit/status like /solve', () => withServer({ cadgfCliPath: FAKE }, async (base) => {
  // solved -> 200, envelope (with vars) passed through verbatim
  const solved = { ok: true, value: { vars: { 'e1_start.y': 2.5, 'e1_end.y': 2.5 }, solve: { ok: true } } };
  const ok = await fetch(`${base}/solve-cadgf`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ exit: 0, stdout: solved }) });
  assert.equal(ok.status, 200);
  assert.deepEqual(await ok.json(), solved);
  // unsatisfiable -> 422 (same mapping as /solve)
  const blocked = await fetch(`${base}/solve-cadgf`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ exit: 1, stdout: { ok: false, error_code: 'SOLVE_UNSATISFIED', error: 'conflict' } }) });
  assert.equal(blocked.status, 422);
  // GET /solve-cadgf -> 405
  const get = await fetch(`${base}/solve-cadgf`, { method: 'GET' });
  assert.equal(get.status, 405);
}));
