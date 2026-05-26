// VemCAD Project Runtime — `constraint` module (v0 / S2 + Tier 1 / §D1b).
//
// Owns the constraint set at the VEMCAD-PROJECT truth level: structural
// normalization (v0) AND the v1 semantic vocabulary (§D1b) — which constraint
// TYPES exist, how many point-SemRefs each takes, whether it carries a value, and
// which roles a SemRef may target per entity kind. Normalization reuses the shared
// id rules so constraints serialize reproducibly. NO solver runs here; the solver
// adapter CONSUMES this vocabulary to expand SemRefs into solver VarRefs — the
// semantics live here, the expansion lives there.

import { byId, validateUniqueRecordIds } from '../shared/ordering.js';

export const ERROR_INVALID_CONSTRAINT_SET = 'INVALID_CONSTRAINT_SET';

function ok(value, diagnostics = []) {
  return { ok: true, value, diagnostics };
}

function fail(errorCode, error, diagnostics = []) {
  return { ok: false, error_code: errorCode, error, diagnostics };
}

// Normalize a constraint set: validate shape/ids, return a stably-ordered copy.
// Missing/empty input → empty set (not an error). v0 never solves; the returned
// `diagnostics` is the reserved container and stays empty until the solver lands.
export function normalizeConstraintSet(constraints) {
  if (constraints === undefined || constraints === null) return ok([], []);
  if (!Array.isArray(constraints)) {
    return fail(ERROR_INVALID_CONSTRAINT_SET, 'constraints must be an array');
  }
  const invalid = validateUniqueRecordIds(constraints, 'constraints', ERROR_INVALID_CONSTRAINT_SET);
  if (invalid) return fail(invalid.code, invalid.message);
  return ok([...constraints].sort(byId), []);
}

// ---- v1 semantic constraint vocabulary (Tier 1 / spec §D1b) -----------------

// The constraint TYPES v1 understands. Per type: `pointRefs` = how many point
// SemRefs it takes; `value` = whether it carries a numeric value. This is the
// single source the solver adapter reads — it must not re-declare the type set.
export const V1_CONSTRAINT_VOCABULARY = {
  horizontal: { pointRefs: 2, value: false },
  vertical: { pointRefs: 2, value: false },
  distance: { pointRefs: 2, value: true },
  parallel: { pointRefs: 4, value: false },
  perpendicular: { pointRefs: 4, value: false },
  angle: { pointRefs: 4, value: true },
};

// Roles each solvable entity kind exposes as a SemRef target `{ entity, at: role }`.
// MUST mirror the adapter's ENTITY_POINTS (the roles it actually mints); the mirror
// is enforced by a test. `rect` (p0/p1) is named in the §D1b spec but is not yet
// v1-solvable, so it is intentionally absent until the adapter mints rect points.
export const ENTITY_ROLES = {
  point: ['self'],
  line: ['start', 'end'],
  circle: ['center'],
  arc: ['center'],
};

// Validate a constraint set against the v1 vocabulary + the project's entities
// (§D1b). Returns ok(validConstraints, diagnostics): a constraint is KEPT only if
// its type is supported, its ref count matches, a value is present iff required,
// and every SemRef targets a legal role of a known solvable entity kind. Anything
// else is DROPPED with exactly one diagnostic — dropping (not hard-failing) keeps a
// partially-authored sketch solvable. Codes/levels match what the adapter emitted
// inline before this lifted here; resolution to a minted point stays the adapter's
// job (a legal SemRef whose entity was excluded for bad geometry fails THERE).
export function validateV1ConstraintSet(constraints, entities) {
  if (constraints === undefined || constraints === null) return ok([], []);
  if (!Array.isArray(constraints)) {
    return fail(ERROR_INVALID_CONSTRAINT_SET, 'constraints must be an array');
  }
  const kindById = new Map();
  for (const e of Array.isArray(entities) ? entities : []) kindById.set(e?.id, e?.kind);

  const valid = [];
  const diagnostics = [];
  for (const c of constraints) {
    const spec = V1_CONSTRAINT_VOCABULARY[c?.type];
    if (!spec) {
      diagnostics.push({ level: 'info', code: 'CONSTRAINT_NOT_SUPPORTED', message: `constraint ${JSON.stringify(c?.id)} type ${JSON.stringify(c?.type)} is not in the v1 supported set; skipped` });
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
    if (!spec.value && c.value !== undefined && c.value !== null) {
      diagnostics.push({ level: 'warn', code: 'CONSTRAINT_UNEXPECTED_VALUE', message: `constraint ${JSON.stringify(c.id)} (${c.type}) takes no value but one was provided; skipped (the adapter would otherwise silently drop the value)` });
      continue;
    }
    let refBad = false;
    for (const ref of refs) {
      const roles = ENTITY_ROLES[kindById.get(ref?.entity)];
      if (!roles || !roles.includes(ref?.at)) {
        diagnostics.push({ level: 'warn', code: 'CONSTRAINT_REF_UNRESOLVED', message: `constraint ${JSON.stringify(c.id)} ref {entity:${JSON.stringify(ref?.entity)}, at:${JSON.stringify(ref?.at)}} is not a legal role of a known solvable entity; skipped` });
        refBad = true;
        break;
      }
    }
    if (refBad) continue;
    valid.push(c);
  }
  return ok(valid, diagnostics);
}
