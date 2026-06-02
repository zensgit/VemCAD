// Editor NATIVE solve (path A) — solve the editor's OWN (VarRef) constraints and write the solved
// geometry back. The editor command `solver.export-project` produces a CADGF-PROJ (point entities
// `e<id>_<role>` + VarRef constraints, authored via select→constraint in the editor); POST it to
// `/solve-cadgf` (the CADGF-PROJ-direct solve path); the solved vars (keyed by "<pointId>.x|y")
// map back to editor entity geometry by parsing the `e<id>_<role>` point ids, and are applied via
// the undoable `entity.applyGeometry` command.
//
// This is distinct from the SEMANTIC path (editor_solve.js, VEMCAD-PROJECT -> /solve): that one is
// for semantic projects (demo / imported / runtime); this one is the editor's own constraint loop.
// Pure composition: commandBus + fetch are injected, so it is unit-testable without the editor.

// Point ids minted by solver.export-project: e<editorEntityId>_<role>, role in {start,end,center}.
const POINT_KEY = /^e(\d+)_(start|end|center)$/;

export const NATIVE_SOLVE_ENDPOINT = '/solve-cadgf';

// Solved vars { "e<id>_<role>.x|y": value } -> [{ id:<editorEntityId>, patch }] with the editor's
// own field names (line start/end, circle/arc center). Incomplete points (missing x or y) and
// non-point vars are skipped, so a partial solve writes back only the points it fully resolved.
export function parseSolvedVarsToUpdates(vars) {
  const byEntity = new Map(); // editorId -> { start?:{x,y}, end?:{x,y}, center?:{x,y} }
  for (const [key, value] of Object.entries(vars ?? {})) {
    if (!Number.isFinite(value)) continue;
    const dot = key.lastIndexOf('.');
    if (dot < 0) continue;
    const coord = key.slice(dot + 1);
    if (coord !== 'x' && coord !== 'y') continue;
    const match = POINT_KEY.exec(key.slice(0, dot));
    if (!match) continue;
    const id = Number(match[1]);
    const role = match[2];
    if (!byEntity.has(id)) byEntity.set(id, {});
    const roles = byEntity.get(id);
    (roles[role] ??= {})[coord] = value;
  }
  const updates = [];
  for (const [id, roles] of byEntity) {
    const patch = {};
    for (const role of ['start', 'end', 'center']) {
      const p = roles[role];
      if (p && Number.isFinite(p.x) && Number.isFinite(p.y)) patch[role] = { x: p.x, y: p.y };
    }
    if (Object.keys(patch).length > 0) updates.push({ id, patch });
  }
  return updates;
}

// Run the editor native solve loop: solver.export-project -> POST /solve-cadgf -> writeback.
//   { commandBus, endpoint?, fetchImpl? }
// Returns { ok, status, updates?, envelope?, error? }. status: 'solved' | 'blocked' (unsatisfied)
// | 'no-constraints' | 'failed'. Writes back ONLY on a successful solve (never applies a partial /
// unsatisfied result), undoably via entity.applyGeometry.
export async function solveEditorNative({ commandBus, endpoint = NATIVE_SOLVE_ENDPOINT, fetchImpl = globalThis.fetch } = {}) {
  if (!commandBus || typeof commandBus.execute !== 'function') {
    return { ok: false, status: 'failed', error: 'command bus unavailable' };
  }
  const exported = commandBus.execute('solver.export-project');
  if (!exported || exported.ok !== true || !exported.project) {
    return { ok: false, status: 'no-constraints', error: exported?.message ?? 'no constraints to solve' };
  }
  if (typeof fetchImpl !== 'function') {
    return { ok: false, status: 'failed', error: 'fetch is not available' };
  }
  let envelope;
  try {
    const response = await fetchImpl(endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(exported.project),
    });
    envelope = await response.json();
  } catch (err) {
    return { ok: false, status: 'failed', error: err?.message ?? String(err), };
  }
  if (envelope?.ok !== true) {
    return {
      ok: false,
      status: envelope?.error_code === 'SOLVE_UNSATISFIED' ? 'blocked' : 'failed',
      error: envelope?.error ?? null,
      envelope,
    };
  }
  const updates = parseSolvedVarsToUpdates(envelope?.value?.vars ?? {});
  if (updates.length > 0) commandBus.execute('entity.applyGeometry', { updates });
  return { ok: true, status: 'solved', updates, envelope };
}
