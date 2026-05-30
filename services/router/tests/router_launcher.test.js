import test from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { fileURLToPath } from 'node:url';

import { startRouterLauncher, RouterLaunchError } from '../launcher.mjs';

// Pure-node lifecycle tests for the router launcher. They spawn a FAKE router stub
// (node, not python) on a loopback port, so the launcher's real spawn / health-poll /
// timeout / crash-detection / shutdown logic is exercised with zero python / submodule /
// converter dependency — fit for the product_tests "core" job.
const FAKE_ROUTER = fileURLToPath(new URL('./fixtures/fake_router.mjs', import.meta.url));

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function launchFake(extraArgs, opts = {}) {
  const port = opts.port;
  return startRouterLauncher({
    command: process.execPath, // node
    args: [FAKE_ROUTER, '--port', String(port), ...extraArgs],
    stdio: 'ignore',
    host: '127.0.0.1',
    healthIntervalMs: 25,
    healthTimeoutMs: 250,
    stopTimeoutMs: 300,
    ...opts,
  });
}

// Launch a fake expected to become ready, retrying on ROUTER_START_FAILED — the only
// transient outcome (the rare free-port reuse race makes the child fail to bind and exit).
async function launchReady(extraArgs = [], opts = {}, attempts = 4) {
  let lastErr;
  for (let i = 0; i < attempts; i++) {
    const port = await freePort();
    const launcher = launchFake(extraArgs, { ...opts, port });
    try {
      await launcher.ready();
      return launcher;
    } catch (err) {
      lastErr = err;
      await launcher.stop();
      if (err instanceof RouterLaunchError && err.code === 'ROUTER_START_FAILED') continue;
      throw err;
    }
  }
  throw lastErr;
}

// True once `pid` is no longer a live process (polls so we don't depend on stop()).
async function waitGone(pid, timeoutMs = 2000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      process.kill(pid, 0);
    } catch {
      return true; // ESRCH -> gone
    }
    await new Promise((r) => setTimeout(r, 25));
  }
  return false;
}

test('startRouterLauncher requires a command', () => {
  assert.throws(() => startRouterLauncher({}), (err) => {
    assert.ok(err instanceof RouterLaunchError);
    assert.equal(err.code, 'ROUTER_START_NOT_CONFIGURED');
    return true;
  });
});

test('launch -> ready resolves with the loopback url, then stop() exits the child', async () => {
  const launcher = await launchReady([], { startTimeoutMs: 4000 });
  try {
    assert.match(launcher.url, /^http:\/\/127\.0\.0\.1:\d+$/);
    assert.equal(typeof launcher.pid, 'number');
    assert.equal(await launcher.ready(), launcher.url); // ready() is stable/idempotent
  } finally {
    const info = await launcher.stop();
    assert.ok(info, 'stop resolves with exit info');
    assert.ok(await waitGone(launcher.pid), 'child exited after stop()');
  }
});

test('ready polls until /health turns 200 (delayed readiness)', async () => {
  const started = Date.now();
  const launcher = await launchReady(['--health-delay-ms', '300'], { startTimeoutMs: 5000 });
  try {
    assert.ok(Date.now() - started >= 250, 'did not resolve before the health delay elapsed');
  } finally {
    await launcher.stop();
  }
});

test('child that exits before readiness -> ROUTER_START_FAILED', async () => {
  const port = await freePort();
  const launcher = launchFake(['--crash'], { port, startTimeoutMs: 4000 });
  await assert.rejects(launcher.ready(), (err) => {
    assert.ok(err instanceof RouterLaunchError);
    assert.equal(err.code, 'ROUTER_START_FAILED');
    return true;
  });
  await launcher.stop();
});

test('/health never ready within startTimeout -> ROUTER_START_TIMEOUT, and the child is killed', async () => {
  // Retry only to skip the rare port-bind race (which surfaces as START_FAILED, not TIMEOUT).
  let launcher;
  let err;
  for (let i = 0; i < 4; i++) {
    const port = await freePort();
    // health-delay far exceeds the start timeout, so /health stays 503 the whole window
    launcher = launchFake(['--health-delay-ms', '60000'], { port, startTimeoutMs: 250 });
    err = await launcher.ready().then(() => null, (e) => e);
    if (err instanceof RouterLaunchError && err.code === 'ROUTER_START_TIMEOUT') break;
    await launcher.stop(); // START_FAILED (port race) -> retry
    err = null;
  }
  assert.ok(err instanceof RouterLaunchError && err.code === 'ROUTER_START_TIMEOUT', 'expected ROUTER_START_TIMEOUT');
  // The TIMEOUT path itself must kill the child — verified WITHOUT calling stop(), so a
  // regression that drops the timeout-kill (orphaning a real router) would fail here.
  assert.ok(await waitGone(launcher.pid), 'timed-out child was killed (no orphan)');
  await launcher.stop(); // idempotent cleanup
});

test('ROUTER_START_TIMEOUT force-kills an ignore-SIGTERM child (no orphan, without stop())', async () => {
  // Regression guard: the timeout path must use the SAME SIGTERM->SIGKILL escalation as
  // stop(); a child that ignores SIGTERM must still be gone after the timeout WITHOUT the
  // caller invoking stop(). (Retry loop only skips the rare port-bind race.)
  let launcher;
  let err;
  for (let i = 0; i < 4; i++) {
    const port = await freePort();
    launcher = launchFake(['--health-delay-ms', '60000', '--ignore-sigterm'], { port, startTimeoutMs: 250 });
    err = await launcher.ready().then(() => null, (e) => e);
    if (err instanceof RouterLaunchError && err.code === 'ROUTER_START_TIMEOUT') break;
    await launcher.stop();
    err = null;
  }
  assert.ok(err instanceof RouterLaunchError && err.code === 'ROUTER_START_TIMEOUT', 'expected ROUTER_START_TIMEOUT');
  // No stop() on this launcher — proves the timeout path alone force-killed the child.
  assert.ok(await waitGone(launcher.pid, 3000), 'ignore-SIGTERM child force-killed on timeout (no orphan)');
  await launcher.stop(); // idempotent cleanup (already gone)
});

test('stop() force-kills a child that ignores SIGTERM, and is idempotent', async () => {
  const launcher = await launchReady(['--ignore-sigterm'], { startTimeoutMs: 4000 });
  const p1 = launcher.stop();
  const p2 = launcher.stop();
  assert.equal(p1, p2, 'stop() returns the same promise when called twice');
  const info = await p1; // SIGTERM ignored -> SIGKILL after stopTimeoutMs -> exits
  assert.ok(info);
  assert.ok(await waitGone(launcher.pid), 'stuck child force-killed');
});
