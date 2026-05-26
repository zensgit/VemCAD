// VemCAD Project Runtime v1 — solve runner (C2 / Tier 1, prototype).
//
// The solver is C++-only (not in the C ABI); the existing callable boundary is
// the `solve_from_project --json` CLI. This factory returns a runner that writes
// the CADGF-PROJ to a temp file, shells out to the CLI (wrapping the library path
// so the binary's stale @rpath finds libcore), and parses the JSON `out`
// ({ ok, iterations, final_error, vars, analysis, ... }).
//
// This is the PROTOTYPE path (Tier 1). The stable /solve contract (binary
// discovery, timeout, input validation, version/tolerance pinning, concurrency
// isolation, or a C-ABI in-process call) is Tier 3. Kept out of `node --test`:
// the local-loop tests inject a fake runner; the real binary runs only in the
// independent acceptance (C3).
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// options: { binaryPath, libraryPath, timeoutMs }
//   binaryPath  — solve_from_project binary (or env VEMCAD_SOLVE_BIN)
//   libraryPath — dir holding libcore.* (or env VEMCAD_SOLVE_LIBPATH); set on
//                 DYLD_LIBRARY_PATH (macOS) + LD_LIBRARY_PATH (linux)
export function createCliSolveRunner(options = {}) {
  const binaryPath = options.binaryPath ?? process.env.VEMCAD_SOLVE_BIN ?? '';
  const libraryPath = options.libraryPath ?? process.env.VEMCAD_SOLVE_LIBPATH ?? '';
  const timeoutMs = options.timeoutMs ?? 30000;

  return function runCliSolve(cadgfProject) {
    if (!binaryPath) {
      throw new Error('solve runner: binaryPath (or env VEMCAD_SOLVE_BIN) is required');
    }
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'vemcad-solve-'));
    const file = path.join(dir, 'project.json');
    try {
      fs.writeFileSync(file, JSON.stringify(cadgfProject));
      const env = { ...process.env };
      if (libraryPath) {
        env.DYLD_LIBRARY_PATH = libraryPath;
        env.LD_LIBRARY_PATH = libraryPath;
      }
      try {
        const stdout = execFileSync(binaryPath, ['--json', file], {
          env,
          encoding: 'utf8',
          timeout: timeoutMs,
          maxBuffer: 32 * 1024 * 1024,
        });
        return JSON.parse(stdout);
      } catch (execErr) {
        // solve_from_project --json prints the JSON result THEN exits 1 when
        // res.ok is false; recover that structured output (analysis/message)
        // from the failed process's stdout instead of losing it to the throw.
        const recovered = typeof execErr?.stdout === 'string' ? execErr.stdout.trim() : '';
        if (recovered) {
          try { return JSON.parse(recovered); } catch { /* not JSON — fall through */ }
        }
        throw execErr;
      }
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  };
}
