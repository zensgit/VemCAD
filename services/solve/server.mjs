// VemCAD /solve service — Tier 3 prototype (product-repo side, no submodule).
//
// A thin node:http -> CLI adapter: it shells out to apps/runtime/tools/solve_cli.mjs
// (the host-agnostic solve unit) and maps the CLI's exit code + JSON envelope onto
// HTTP. No solver logic is re-implemented here; the router is a dumb pipe so any
// language host (this node service, the python Router, the Electron shell) maps the
// SAME contract. Zero dependencies (node built-ins only).
//
// Contract:
//   POST /solve   body = VEMCAD-PROJECT JSON           -> the solve_cli envelope (JSON)
//   GET  /health                                       -> {ok:true}
// HTTP status (exit code -> status; exit 1 is split by the envelope's error_code,
// because the CLI exit code conflates "unsolvable" with "server-side failure"):
//   exit 0  solved                                     -> 200
//   exit 2  bad input (malformed JSON / invalid PROJECT)-> 400
//   exit 1  SOLVE_UNSATISFIED (the sketch has no soln) -> 422
//   exit 1  SOLVE_FAILED (binary missing / runner threw)-> 500  (client can't fix it)
//   CLI emitted non-JSON / spawn failed                 -> 500
// The body is ALWAYS the JSON envelope (never swaps format mid-contract).
//
// The real solver still needs VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH in the env;
// the service passes its env straight through to solve_cli.
//
// Prototype scope — CHOSEN, not forgotten: no request-size limit, no per-request
// timeout, no concurrency cap. A hardened deployment must add these before exposure.
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// Default solve unit, resolved relative to this file (not cwd) so the service runs
// from anywhere. Overridable for tests / alternate layouts via options or env.
const DEFAULT_CLI = fileURLToPath(new URL('../../apps/runtime/tools/solve_cli.mjs', import.meta.url));

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

// Run the solve CLI with `body` on stdin; resolve { code, stdout, stderr } or
// { spawnError } if the process could not be started at all.
function runCli(command, cliPath, body, env) {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(command, [cliPath, '-'], { env });
    } catch (err) {
      resolve({ spawnError: err });
      return;
    }
    const out = [];
    const errOut = [];
    child.on('error', (err) => resolve({ spawnError: err }));
    child.stdout.on('data', (c) => out.push(c));
    child.stderr.on('data', (c) => errOut.push(c));
    child.on('close', (code) => resolve({ code, stdout: Buffer.concat(out).toString('utf8'), stderr: Buffer.concat(errOut).toString('utf8') }));
    child.stdin.on('error', () => {}); // ignore EPIPE if the child exits before reading
    child.stdin.end(body); // body is a Buffer, passed through unmodified so solve_cli reads exact UTF-8 bytes
  });
}

// exit code (+ error_code for the conflated exit 1) -> HTTP status.
export function statusForResult(code, envelope) {
  if (code === 0) return 200;
  if (code === 2) return 400;
  if (code === 1) return envelope?.error_code === 'SOLVE_UNSATISFIED' ? 422 : 500;
  return 500;
}

function sendJson(res, status, obj) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
  res.end(`${JSON.stringify(obj)}\n`);
}

export function createSolveServer(options = {}) {
  const cliPath = options.cliPath || process.env.VEMCAD_SOLVE_CLI || DEFAULT_CLI;
  const command = options.command || process.env.VEMCAD_SOLVE_NODE || process.execPath;
  const env = options.env || process.env;

  return http.createServer(async (req, res) => {
    try {
      const path = (req.url || '').split('?')[0];

      if (path === '/health') {
        if (req.method !== 'GET') return sendJson(res, 405, { ok: false, error_code: 'METHOD_NOT_ALLOWED' });
        return sendJson(res, 200, { ok: true });
      }

      if (path === '/solve') {
        if (req.method !== 'POST') return sendJson(res, 405, { ok: false, error_code: 'METHOD_NOT_ALLOWED' });
        const body = await readBody(req);
        const r = await runCli(command, cliPath, body, env);
        if (r.spawnError) {
          return sendJson(res, 500, { ok: false, error_code: 'ROUTER_SPAWN_FAILED', error: String(r.spawnError?.message ?? r.spawnError), diagnostics: [] });
        }
        let envelope;
        try {
          envelope = JSON.parse(r.stdout);
        } catch {
          return sendJson(res, 500, { ok: false, error_code: 'ROUTER_BAD_CLI_OUTPUT', error: 'solve CLI did not emit JSON', stderr: (r.stderr || '').slice(0, 500), diagnostics: [] });
        }
        // Self-consistency guard: solve_cli's contract is "exit 0 iff ok". If the
        // exit code and envelope.ok disagree (CLI/host drift), don't return a
        // 200+{ok:false} (or a failure status + ok:true) — treat the contradiction
        // as a server-side anomaly, like non-JSON output. Original envelope kept for
        // debugging.
        if ((r.code === 0) !== (envelope?.ok === true)) {
          return sendJson(res, 500, { ok: false, error_code: 'ROUTER_BAD_CLI_OUTPUT', error: `solve CLI exit code ${r.code} disagrees with envelope.ok=${JSON.stringify(envelope?.ok)}`, envelope, diagnostics: [] });
        }
        return sendJson(res, statusForResult(r.code, envelope), envelope);
      }

      return sendJson(res, 404, { ok: false, error_code: 'NOT_FOUND' });
    } catch (err) {
      sendJson(res, 500, { ok: false, error_code: 'ROUTER_INTERNAL_ERROR', error: String(err?.message ?? err), diagnostics: [] });
    }
  });
}
