#!/usr/bin/env node
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import net from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { startRouterLauncher } from '../launcher.mjs';

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

function skip(message) {
  console.log(`SKIP: ${message}`);
  process.exit(0);
}

const root = fileURLToPath(new URL('../../../', import.meta.url));
const python = process.env.PYTHON || 'python3';
const routerPy =
  process.env.ROUTER_PY ||
  fileURLToPath(new URL('../../../deps/cadgamefusion/tools/plm_router_service.py', import.meta.url));

if (!existsSync(routerPy)) {
  skip(`CADGameFusion router not found at ${routerPy}; run git submodule update --init deps/cadgamefusion`);
}

const pyVersion = spawnSync(python, ['--version'], { encoding: 'utf8' });
if (pyVersion.error || pyVersion.status !== 0) {
  skip(`python interpreter unavailable: ${python}`);
}

const port = Number(process.env.ROUTER_PORT) || await freePort();
const outRoot = mkdtempSync(join(tmpdir(), 'vemcad-router-smoke-'));
const launcher = startRouterLauncher({
  command: python,
  args: [
    routerPy,
    '--host', '127.0.0.1',
    '--port', String(port),
    '--out-root', outRoot,
    '--max-workers', '1',
    '--queue-size', '1',
    '--ttl-seconds', '0',
    '--cleanup-interval', '0',
  ],
  host: '127.0.0.1',
  port,
  stdio: process.env.ROUTER_SMOKE_STDIO || 'ignore',
  startTimeoutMs: Number(process.env.ROUTER_START_TIMEOUT_MS) || 15000,
});

try {
  const url = await launcher.ready();
  const res = await fetch(`${url}/health`);
  assert.equal(res.status, 200, 'GET /health should be ready');
  const body = await res.json();
  assert.equal(body.status, 'ok');
  assert.ok(body.service || body.uptime_seconds !== undefined || body.tasks !== undefined, 'health body should be router-shaped');
  console.log(JSON.stringify({
    status: 'PASS',
    smoke: 'router_reference_smoke',
    root,
    routerPy,
    python,
    url,
    pid: launcher.pid,
    health: body,
  }, null, 2));
} finally {
  await launcher.stop();
  rmSync(outRoot, { recursive: true, force: true });
}
