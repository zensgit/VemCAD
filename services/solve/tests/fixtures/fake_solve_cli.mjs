#!/usr/bin/env node
// Test double for solve_cli.mjs. Scripts (stdout, exit code) from the request body
// so the server's HTTP-status mapping is testable without the real solver binary:
//   { exit, stdout }      -> write JSON.stringify(stdout) to stdout, exit `exit`
//   { raw_stdout, exit }  -> write raw_stdout verbatim (to test non-JSON output)
// A malformed JSON body is handled exactly like the real solve_cli: exit 2.
import fs from 'node:fs';

let input;
try {
  input = JSON.parse(fs.readFileSync(0, 'utf8'));
} catch (e) {
  process.stdout.write(`${JSON.stringify({ ok: false, error_code: 'INVALID_INPUT', error: String(e), diagnostics: [] })}\n`);
  process.exit(2);
}

if (input.raw_stdout !== undefined) {
  process.stdout.write(input.raw_stdout);
  process.exit(input.exit ?? 0);
}

process.stdout.write(`${JSON.stringify(input.stdout ?? { ok: true })}\n`);
process.exit(input.exit ?? 0);
