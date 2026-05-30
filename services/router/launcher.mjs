// VemCAD services/router — Phase 1 thin launcher (desktop / local single-user).
//
// Launches and SUPERVISES the CADGameFusion reference Python router
// (deps/cadgamefusion/tools/plm_router_service.py) on a LOOPBACK port, polls its
// /health endpoint for readiness, and returns a { url, ready(), stop() } handle.
//
// This is a SUPERVISED LAUNCHER, not a per-request spawner: the Python router is a
// long-lived STATEFUL server (queue + worker pool + in-memory tasks across
// /convert -> /status -> /manifest), so it must be started once and kept alive.
// (Contrast services/solve, which is stateless and spawns its CLI per request.)
//
// Phase-1 scope (deliberate): launch / supervise / readiness / clean shutdown ONLY.
// NO reverse proxy, NO new endpoints (the Python router owns /convert, /status,
// /manifest, /history, ...), NO cloud / multi-user / DB, NO Electron changes. The
// auth token, when given, is passed straight through to the Python router. Zero deps.
import { spawn } from 'node:child_process';
import http from 'node:http';

const DEFAULT_HOST = '127.0.0.1';
const DEFAULT_PORT = 9000;
const DEFAULT_HEALTH_PATH = '/health';
const DEFAULT_START_TIMEOUT_MS = 15000;
const DEFAULT_HEALTH_INTERVAL_MS = 250;
const DEFAULT_HEALTH_TIMEOUT_MS = 1500;
const DEFAULT_STOP_SIGNAL = 'SIGTERM';
const DEFAULT_STOP_TIMEOUT_MS = 5000;

export class RouterLaunchError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'RouterLaunchError';
    this.code = code;
  }
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// One GET to host:port/healthPath; resolves true on a 2xx, false on anything else or
// if the endpoint is unreachable (the common case while the server is still starting).
function probeHealth(host, port, healthPath, timeoutMs) {
  return new Promise((resolve) => {
    const req = http.request({ host, port, path: healthPath, method: 'GET', timeout: timeoutMs }, (res) => {
      res.resume(); // drain so the socket can close
      resolve(res.statusCode >= 200 && res.statusCode < 300);
    });
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.on('error', () => resolve(false));
    req.end();
  });
}

/**
 * Launch + supervise the Python router.
 * @returns {{ url: string, pid: number|null, ready: () => Promise<string>, stop: () => Promise<object> }}
 *  - ready(): resolves with the base url once /health is reachable; rejects with a
 *    RouterLaunchError — ROUTER_START_FAILED (child exited before becoming ready) or
 *    ROUTER_START_TIMEOUT (/health never came up within startTimeoutMs; child is killed).
 *  - stop(): signals the child (stopSignal, escalating to SIGKILL after stopTimeoutMs)
 *    and resolves once it has exited. Idempotent; safe before ready() or multiple times.
 */
export function startRouterLauncher(options = {}) {
  const host = options.host || DEFAULT_HOST;
  const port = Number(options.port) || DEFAULT_PORT;
  const healthPath = options.healthPath || DEFAULT_HEALTH_PATH;
  const startTimeoutMs = options.startTimeoutMs ?? DEFAULT_START_TIMEOUT_MS;
  const healthIntervalMs = options.healthIntervalMs ?? DEFAULT_HEALTH_INTERVAL_MS;
  const healthTimeoutMs = options.healthTimeoutMs ?? DEFAULT_HEALTH_TIMEOUT_MS;
  const stopSignal = options.stopSignal || DEFAULT_STOP_SIGNAL;
  const stopTimeoutMs = options.stopTimeoutMs ?? DEFAULT_STOP_TIMEOUT_MS;

  if (!options.command) {
    throw new RouterLaunchError('ROUTER_START_NOT_CONFIGURED', 'startRouterLauncher requires options.command');
  }
  const args = Array.isArray(options.args) ? options.args : [];
  const url = `http://${host}:${port}`;

  let child;
  try {
    child = spawn(options.command, args, {
      env: options.env || process.env,
      stdio: options.stdio || 'inherit',
    });
  } catch (err) {
    const rejected = Promise.reject(new RouterLaunchError('ROUTER_START_FAILED', `failed to spawn router: ${err.message}`));
    rejected.catch(() => {}); // not unhandled if caller never calls ready()
    return { url, pid: null, ready: () => rejected, stop: () => Promise.resolve({ code: null, signal: null }) };
  }

  let exited = false;
  let exitInfo = null;
  const exitPromise = new Promise((resolve) => {
    child.once('exit', (code, signal) => { exited = true; exitInfo = exitInfo || { code, signal }; resolve(exitInfo); });
    child.once('error', (error) => { exited = true; exitInfo = exitInfo || { code: null, signal: null, error }; resolve(exitInfo); });
  });

  const readyPromise = (async () => {
    const deadline = Date.now() + startTimeoutMs;
    while (Date.now() < deadline) {
      if (exited) {
        throw new RouterLaunchError(
          'ROUTER_START_FAILED',
          `router exited before becoming ready (code=${exitInfo?.code ?? ''} signal=${exitInfo?.signal ?? ''}${exitInfo?.error ? ` error=${exitInfo.error.message}` : ''})`,
        );
      }
      if (await probeHealth(host, port, healthPath, healthTimeoutMs)) {
        return url;
      }
      // Wake immediately if the child exits during the wait, else after the interval.
      await Promise.race([delay(healthIntervalMs), exitPromise]);
    }
    if (!exited) { try { child.kill(stopSignal); } catch { /* already gone */ } }
    throw new RouterLaunchError('ROUTER_START_TIMEOUT', `router /health not ready within ${startTimeoutMs}ms at ${url}`);
  })();
  readyPromise.catch(() => {}); // suppress unhandled rejection if caller only stop()s

  let stopPromise = null;
  function stop() {
    if (!stopPromise) {
      stopPromise = (async () => {
        if (exited) return exitInfo;
        try {
          child.kill(stopSignal);
        } catch {
          return exitInfo || { code: null, signal: null };
        }
        const escalate = delay(stopTimeoutMs).then(() => {
          if (!exited) { try { child.kill('SIGKILL'); } catch { /* gone */ } }
        });
        escalate.catch(() => {});
        return exitPromise;
      })();
    }
    return stopPromise;
  }

  return { url, pid: child.pid, ready: () => readyPromise, stop };
}
