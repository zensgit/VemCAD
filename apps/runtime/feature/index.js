// VemCAD Project Runtime — `feature` module (v0 / S2 + Tier 1 rebuild).
//
// Two distinct axes meet here:
//   - the FEATURE-execution plan (buildRebuildPlan): a deterministic order of
//     feature ids. v0 has no feature tree, so the plan is still a NO-OP (zero
//     executable steps); its shape is stable for the future rebuild engine.
//   - the project REBUILD (rebuildProject): for a v1 constraint sketch, geometry
//     is DERIVED from the constraints, so the rebuild IS the constraint solve.
//     This is the host-facing rebuild seam; it delegates to the solver today and
//     is where feature-plan execution and the solve will compose later.

import { byId, validateUniqueRecordIds } from '../shared/ordering.js';
import { solveProject } from '../solver/index.js';

export const ERROR_INVALID_FEATURE_LIST = 'INVALID_FEATURE_LIST';

function ok(value, diagnostics = []) {
  return { ok: true, value, diagnostics };
}

function fail(errorCode, error, diagnostics = []) {
  return { ok: false, error_code: errorCode, error, diagnostics };
}

// Normalize a feature list: validate shape/ids, return a stably-ordered copy.
// Missing/empty input → empty list (not an error).
export function normalizeFeatureList(features) {
  if (features === undefined || features === null) return ok([], []);
  if (!Array.isArray(features)) {
    return fail(ERROR_INVALID_FEATURE_LIST, 'features must be an array');
  }
  const invalid = validateUniqueRecordIds(features, 'features', ERROR_INVALID_FEATURE_LIST);
  if (invalid) return fail(invalid.code, invalid.message);
  return ok([...features].sort(byId), []);
}

// Build the FEATURE-execution plan from a feature list. Still a deterministic
// NO-OP in v1 (no feature tree): the plan lists feature ids in stable order with
// zero executable steps. The `noop: true` marker is explicit so callers do not
// mistake it for a real plan. NOTE: the v1 constraint solve is rebuildProject,
// not this — features and constraints are separate axes (see module header).
export function buildRebuildPlan(features) {
  const normalized = normalizeFeatureList(features);
  if (!normalized.ok) return normalized;
  return ok(
    {
      order: normalized.value.map((feature) => feature.id),
      steps: [],
      noop: true,
    },
    [],
  );
}

// Rebuild a project. For a v1 constraint sketch the geometry is DERIVED from the
// constraints, so the rebuild IS the constraint solve: this delegates to the
// solver and returns its result verbatim (the same ok / SOLVE_UNSATISFIED /
// SOLVE_FAILED / input-error contract). The solved geometry is transient —
// derived on rebuild, never persisted back into the Project truth. This is the
// single host-facing "rebuild this project" entry; when a feature tree lands,
// buildRebuildPlan's ordered steps and this solve compose here.
export function rebuildProject(project, options = {}) {
  return solveProject(project, options);
}
