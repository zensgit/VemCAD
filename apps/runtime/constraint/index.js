// VemCAD Project Runtime — `constraint` module (v0 / S2).
//
// v0 scope: store + normalize a constraint set deterministically and carry a
// diagnostics container. NO solver runs — parameters, solver binding, and
// DOF/conflict analysis arrive in a later phase. Normalization reuses the
// shared id rules so constraints serialize reproducibly inside the Project model.

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
