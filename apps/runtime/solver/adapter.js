// VemCAD Project Runtime v1 — solver adapter (C / Tier 1).
//
// VEMCAD-PROJECT -> CADGF-PROJ (cadgamefusion's solver input, project.schema.json),
// per the frozen Tier 1 spec (docs/VEMCAD_RUNTIME_V1_SOLVER_TIER1_SPEC_20260525.md):
//   - decompose inline-coord entities into minted points (deterministic, dot-free
//     INTERNAL ids + a reversible map back to (entityId, role));
//   - expand SEMANTIC constraints into solver VarRefs in the exact order each
//     constraint's residual expects (appendix table, read from solver.cpp);
//   - units in->inch; out-of-scope / malformed entities + constraints -> diagnostic.
//
// The Project truth speaks SEMANTIC SemRefs ({entity, at:role}) only; VarRefs and
// minted point ids are transient adapter products. v1 supported set = 6 types
// (equal/coincident/concentric excluded — see spec). Only point coords are solver
// variables (circle radius / arc angles are fixed params).
import { normalizeProjectModel } from '../project/index.js';

export const ERROR_UNSUPPORTED_UNIT = 'UNSUPPORTED_PROJECT_UNIT';

// VEMCAD project unit -> CADGF-PROJ unit enum (mm/cm/m/inch/ft — note `inch`).
const UNIT_MAP = { mm: 'mm', cm: 'cm', m: 'm', in: 'inch', ft: 'ft' };

// Which points each solvable VEMCAD entity kind contributes, in mint order.
const ENTITY_POINTS = {
  point: [{ role: 'self', coord: (e) => e.point }],
  line: [
    { role: 'start', coord: (e) => e.line?.[0] },
    { role: 'end', coord: (e) => e.line?.[1] },
  ],
  circle: [{ role: 'center', coord: (e) => e.circle?.c }],
  arc: [{ role: 'center', coord: (e) => e.arc?.c }],
};

// v1 supported constraint types. `pointRefs` = number of point-SemRefs; `coords`
// = per-SemRef coordinate keys to emit IN ORDER (matches the solver residual).
const CONSTRAINT_SPECS = {
  horizontal: { pointRefs: 2, value: false, coords: [['y'], ['y']] },
  vertical: { pointRefs: 2, value: false, coords: [['x'], ['x']] },
  distance: { pointRefs: 2, value: true, coords: [['x', 'y'], ['x', 'y']] },
  parallel: { pointRefs: 4, value: false, coords: [['x', 'y'], ['x', 'y'], ['x', 'y'], ['x', 'y']] },
  perpendicular: { pointRefs: 4, value: false, coords: [['x', 'y'], ['x', 'y'], ['x', 'y'], ['x', 'y']] },
  angle: { pointRefs: 4, value: true, coords: [['x', 'y'], ['x', 'y'], ['x', 'y'], ['x', 'y']] },
};

function isVec2(v) {
  return Array.isArray(v) && v.length === 2 && Number.isFinite(v[0]) && Number.isFinite(v[1]);
}

function ok(value, diagnostics = []) {
  return { ok: true, value, diagnostics };
}

function fail(errorCode, error, diagnostics = []) {
  return { ok: false, error_code: errorCode, error, diagnostics };
}

// Build a CADGF-PROJ solver-input document from a VEMCAD-PROJECT.
// Returns { ok, value: { cadgfProject, pointMap }, diagnostics } where pointMap
// is the reversible mint map: mintedPointId -> { entity, role } (for writeback).
export function buildSolverProject(project, options = {}) {
  const normalized = normalizeProjectModel(project);
  if (!normalized.ok) return normalized;
  const p = normalized.value;
  const diagnostics = [];

  const units = UNIT_MAP[p.project.units];
  if (!units) {
    return fail(ERROR_UNSUPPORTED_UNIT, `unsupported project unit: ${JSON.stringify(p.project.units)}`);
  }

  // ---- entity decomposition: mint dot-free internal point ids + reversible map ----
  const sceneEntities = [];
  const pointMap = {}; // mintedId -> { entity, role }
  const pointByEntityRole = new Map(); // `${entityId} ${role}` -> mintedId
  // Mint dot-free internal ids that never collide with a source entity id.
  const sourceIds = new Set(p.entities.map((ent) => ent.id));
  let mintCounter = 0;
  const mintPointId = () => {
    let id = `__p${mintCounter}`;
    mintCounter += 1;
    while (sourceIds.has(id)) {
      id = `__p${mintCounter}`;
      mintCounter += 1;
    }
    return id;
  };

  for (const e of p.entities) {
    const roles = ENTITY_POINTS[e.kind];
    if (!roles) {
      diagnostics.push({ level: 'info', code: 'ENTITY_NOT_SOLVABLE', message: `entity ${JSON.stringify(e.id)} (${e.kind}) is not a solvable kind; excluded from the solve scene` });
      continue;
    }

    // Validate ALL geometry + fixed params BEFORE committing anything, so a
    // malformed entity leaves no half-minted point / map entry behind.
    const staged = [];
    let bad = null;
    for (const role of roles) {
      const c = role.coord(e);
      if (!isVec2(c)) { bad = `${role.role} point`; break; }
      staged.push({ role: role.role, x: c[0], y: c[1] });
    }
    if (!bad && e.kind === 'circle' && !(Number.isFinite(e.circle?.r) && e.circle.r > 0)) bad = 'radius';
    if (!bad && e.kind === 'arc') {
      if (!(Number.isFinite(e.arc?.r) && e.arc.r > 0)) bad = 'radius';
      else if (!(Number.isFinite(e.arc?.a0) && Number.isFinite(e.arc?.a1))) bad = 'startAngle/endAngle';
    }
    if (bad) {
      diagnostics.push({ level: 'warn', code: 'ENTITY_BAD_GEOMETRY', message: `entity ${JSON.stringify(e.id)} (${e.kind}) has malformed ${bad}; excluded` });
      continue;
    }

    // Commit: mint points, then the higher entity referencing them.
    const minted = {};
    for (const sp of staged) {
      const id = mintPointId();
      sceneEntities.push({ id, type: 'point', params: { x: sp.x, y: sp.y } });
      pointMap[id] = { entity: e.id, role: sp.role };
      pointByEntityRole.set(`${e.id} ${sp.role}`, id);
      minted[sp.role] = id;
    }
    if (e.kind === 'line') {
      sceneEntities.push({ id: e.id, type: 'line', params: { p0: minted.start, p1: minted.end } });
    } else if (e.kind === 'circle') {
      sceneEntities.push({ id: e.id, type: 'circle', params: { center: minted.center, radius: e.circle.r } });
    } else if (e.kind === 'arc') {
      sceneEntities.push({ id: e.id, type: 'arc', params: { center: minted.center, radius: e.arc.r, startAngle: e.arc.a0, endAngle: e.arc.a1 } });
    }
    // bare point: the minted point entity already covers it.
  }

  // ---- constraint expansion: SemRef -> VarRef per the residual-pinned table ----
  const sceneConstraints = [];
  for (const c of p.constraints) {
    const spec = CONSTRAINT_SPECS[c.type];
    if (!spec) {
      diagnostics.push({ level: 'info', code: 'CONSTRAINT_NOT_SUPPORTED', message: `constraint ${JSON.stringify(c.id)} type ${JSON.stringify(c.type)} is not in the v1 supported set; skipped` });
      continue;
    }
    const refs = Array.isArray(c.refs) ? c.refs : [];
    if (refs.length !== spec.pointRefs) {
      diagnostics.push({ level: 'warn', code: 'CONSTRAINT_BAD_ARITY', message: `constraint ${JSON.stringify(c.id)} (${c.type}) needs ${spec.pointRefs} point refs, got ${refs.length}; skipped` });
      continue;
    }
    if (spec.value && !Number.isFinite(c.value)) {
      diagnostics.push({ level: 'warn', code: 'CONSTRAINT_MISSING_VALUE', message: `constraint ${JSON.stringify(c.id)} (${c.type}) requires a numeric value; skipped` });
      continue;
    }
    const varRefs = [];
    let resolveOk = true;
    for (let i = 0; i < refs.length; i += 1) {
      const ref = refs[i];
      const mintedId = pointByEntityRole.get(`${ref?.entity} ${ref?.at}`);
      if (!mintedId) {
        diagnostics.push({ level: 'warn', code: 'CONSTRAINT_REF_UNRESOLVED', message: `constraint ${JSON.stringify(c.id)} ref {entity:${JSON.stringify(ref?.entity)}, at:${JSON.stringify(ref?.at)}} does not resolve to a solvable point; skipped` });
        resolveOk = false;
        break;
      }
      for (const key of spec.coords[i]) varRefs.push(`${mintedId}.${key}`);
    }
    if (!resolveOk) continue;
    const out = { id: c.id, type: c.type, refs: varRefs };
    if (spec.value) out.value = c.value;
    sceneConstraints.push(out);
  }

  const cadgfProject = {
    header: { format: 'CADGF-PROJ', version: 1 },
    project: { id: p.project.id, units },
    scene: { entities: sceneEntities, constraints: sceneConstraints, parameters: {} },
    featureTree: { nodes: [], edges: [] },
    resources: {},
  };

  return ok({ cadgfProject, pointMap }, diagnostics);
}
