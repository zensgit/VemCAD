// VemCAD Project Runtime — `feature` module (v0 / S2).
//
// v0 scope: store + normalize a feature list and build a NO-OP rebuild plan.
// There is no parametric rebuild yet — the plan records a deterministic
// execution order (feature ids in stable order) with no executable steps, so
// its shape is stable for the future rebuild engine to fill in. The dependency
// graph and real rebuild arrive in a later phase.

import { byId, validateUniqueRecordIds } from '../shared/ordering.js';

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

// Build a rebuild plan from a feature list. v0 is a deterministic NO-OP: the
// plan lists feature ids in stable order with zero executable steps. The
// `noop: true` marker is explicit so callers do not mistake it for a real plan.
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
