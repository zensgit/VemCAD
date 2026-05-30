#!/usr/bin/env node
// Test fixture: a FAKE router — a tiny loopback HTTP server that mimics ONLY the
// /health readiness contract the launcher polls. It is NOT the real Python router; it
// lets the launcher's spawn / readiness / lifecycle / shutdown be exercised in pure node
// with no Python, no submodule, and no converter. Behaviour controlled by flags:
//   --port <n>             bind 127.0.0.1:<n> (required for the listening modes)
//   --health-delay-ms <n>  respond 503 to /health until <n>ms after start, then 200
//   --crash                exit(1) immediately, never listening (simulate start failure)
//   --ignore-sigterm       do NOT exit on SIGTERM (simulate a stuck child -> SIGKILL path)
import http from 'node:http';

function argValue(name, fallback) {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : fallback;
}
const hasFlag = (name) => process.argv.includes(name);

if (hasFlag('--crash')) {
  process.stderr.write('fake_router: crashing before listen\n');
  process.exit(1);
}

const port = Number(argValue('--port', '0'));
const healthDelayMs = Number(argValue('--health-delay-ms', '0'));
const startedAt = Date.now();

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    const ready = Date.now() - startedAt >= healthDelayMs;
    res.writeHead(ready ? 200 : 503, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ status: ready ? 'ok' : 'starting', service: 'fake-router', ready }));
    return;
  }
  res.writeHead(404, { 'content-type': 'application/json' });
  res.end('{"status":"error","error_code":"UNKNOWN_ENDPOINT"}');
});

// Exit cleanly on a bind failure (e.g. the rare free-port race in the test harness) so
// the launcher observes a quick ROUTER_START_FAILED that the test can retry, rather than
// an ugly uncaught EADDRINUSE.
server.on('error', () => process.exit(1));
server.listen(port, '127.0.0.1');

if (hasFlag('--ignore-sigterm')) {
  // Install a NO-OP handler so SIGTERM is genuinely ignored (overriding node's default
  // terminate-on-SIGTERM) — only SIGKILL can stop us. Simulates a stuck child so the
  // launcher's SIGTERM->SIGKILL escalation is actually exercised.
  process.on('SIGTERM', () => { /* deliberately ignored */ });
} else {
  process.on('SIGTERM', () => server.close(() => process.exit(0)));
}
