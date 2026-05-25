// VemCAD Project Runtime — `project` module (v0 / S1).
//
// Owns the official engineering source-of-truth envelope: the `VEMCAD-PROJECT`
// model, its parse/normalize/serialize lifecycle, and version migration.
// This module is geometry-agnostic: entities/layers/constraints/features are
// stored opaquely (sorted by `id`); their CADGF semantics live in `scene` (S4).
//
// Determinism contract (frozen, see
// docs/VEMCAD_PROJECT_RUNTIME_V0_DEVELOPMENT_20260525.md §7):
//   - normalize/serialize never touch `createdAt`/`modifiedAt`.
//   - layers/entities/constraints/features/passthrough.entities serialize in
//     stable id order; all object keys serialize in a deterministic order.
//
// All public functions return the unified result object:
//   { ok: true,  value, diagnostics: [] }
//   { ok: false, error_code, error, diagnostics: [] }

export const PROJECT_FORMAT = 'VEMCAD-PROJECT';
export const PROJECT_VERSION = 1;

export const DEFAULT_UNITS = 'mm';
export const DEFAULT_LAYER_ID = 0;
export const DEFAULT_LAYER_NAME = '0';

export const ERROR_INVALID_FORMAT = 'INVALID_PROJECT_FORMAT';
export const ERROR_UNSUPPORTED_VERSION = 'UNSUPPORTED_PROJECT_VERSION';

// ---- result helpers ---------------------------------------------------------

function ok(value, diagnostics = []) {
  return { ok: true, value, diagnostics };
}

function fail(errorCode, error, diagnostics = []) {
  return { ok: false, error_code: errorCode, error, diagnostics };
}

// ---- small pure utilities ---------------------------------------------------

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

// Deterministic, locale-independent string comparison (code-unit order).
// NOTE: deliberately not `localeCompare`, which varies by environment locale.
function compareStrings(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

// Numeric ids compare numerically (layer 0,1,2,10); otherwise by string.
function compareIds(a, b) {
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return compareStrings(String(a), String(b));
}

function byId(a, b) {
  return compareIds(a?.id, b?.id);
}

// Recursively rebuild objects with alphabetically sorted keys so that
// JSON.stringify emits a deterministic byte stream. Arrays keep their order
// (the caller pre-sorts record arrays by id).
function sortKeysDeep(value) {
  if (Array.isArray(value)) return value.map(sortKeysDeep);
  if (isObject(value)) {
    const out = {};
    for (const key of Object.keys(value).sort(compareStrings)) {
      out[key] = sortKeysDeep(value[key]);
    }
    return out;
  }
  return value;
}

// Passthrough CADGF entities have no VemCAD id. Order by numeric `cadgfId`
// when present (nicer, matches source), else fall back to canonical JSON so
// the order is still fully deterministic.
function comparePassthroughEntities(a, b) {
  const ca = Number.isFinite(a?.cadgfId) ? a.cadgfId : null;
  const cb = Number.isFinite(b?.cadgfId) ? b.cadgfId : null;
  if (ca !== null && cb !== null && ca !== cb) return ca - cb;
  if (ca !== null && cb === null) return -1;
  if (ca === null && cb !== null) return 1;
  return compareStrings(JSON.stringify(sortKeysDeep(a)), JSON.stringify(sortKeysDeep(b)));
}

function ensureDefaultLayer(layers) {
  if (layers.some((layer) => layer?.id === DEFAULT_LAYER_ID)) return layers;
  return [{ id: DEFAULT_LAYER_ID, name: DEFAULT_LAYER_NAME }, ...layers];
}

// ---- envelope validation ----------------------------------------------------

// Returns null when the envelope is acceptable, else { code, message }.
// Validates only the format envelope; it does NOT repair or validate content
// (frozen rule: invalid project → ok:false, no implicit repair).
function validateEnvelope(project) {
  if (!isObject(project)) {
    return { code: ERROR_INVALID_FORMAT, message: 'project must be an object' };
  }
  const header = project.header;
  if (!isObject(header)) {
    return { code: ERROR_INVALID_FORMAT, message: 'missing project header' };
  }
  if (header.format !== PROJECT_FORMAT) {
    return { code: ERROR_INVALID_FORMAT, message: `unexpected header.format: ${String(header.format)}` };
  }
  if (!Number.isInteger(header.version)) {
    return { code: ERROR_INVALID_FORMAT, message: 'header.version must be an integer' };
  }
  if (header.version < 1) {
    return { code: ERROR_INVALID_FORMAT, message: `header.version must be >= 1 (got ${header.version})` };
  }
  if (header.version > PROJECT_VERSION) {
    return {
      code: ERROR_UNSUPPORTED_VERSION,
      message: `project version ${header.version} exceeds supported version ${PROJECT_VERSION}`,
    };
  }
  if (!isObject(project.project) || typeof project.project.id !== 'string' || project.project.id.length === 0) {
    return { code: ERROR_INVALID_FORMAT, message: 'project.id must be a non-empty string' };
  }
  return null;
}

// Project-owned record collections: must be arrays-when-present and every
// record must carry a present, unique id (so stable ordering is unambiguous).
const PROJECT_OWNED_COLLECTIONS = ['layers', 'entities', 'constraints', 'features'];

// Returns null when content is structurally sound for canonicalization, else
// { code, message }. Distinguishes "missing → may be defaulted" from "wrong
// type → reject" so canonicalize never silently drops data (P1), and enforces
// present + unique ids on Project-owned collections so stable ordering is
// deterministic even with otherwise-equivalent inputs (P2).
//
// Applied by normalize/serialize (the produce/persist boundaries), NOT by parse
// (an envelope-only read boundary — see parseProjectModel).
function validateStructure(project) {
  for (const key of PROJECT_OWNED_COLLECTIONS) {
    const value = project[key];
    if (value === undefined) continue; // missing → defaulted in canonicalize
    if (!Array.isArray(value)) {
      return { code: ERROR_INVALID_FORMAT, message: `${key} must be an array when present` };
    }
    const seen = new Set();
    for (const record of value) {
      if (!isObject(record)) {
        return { code: ERROR_INVALID_FORMAT, message: `${key} entries must be objects` };
      }
      const id = record.id;
      const hasUsableId =
        (typeof id === 'number' && Number.isFinite(id)) || (typeof id === 'string' && id.length > 0);
      if (!hasUsableId) {
        return {
          code: ERROR_INVALID_FORMAT,
          message: `${key} entries require a finite numeric or non-empty string id`,
        };
      }
      // Dedup key matches the sort comparator's equality:
      // compareIds(a, b) === 0  ⟺  String(a) === String(b).
      // (so numeric 0 and string "0" collide, consistent with their ordering.)
      const idKey = String(id);
      if (seen.has(idKey)) {
        return { code: ERROR_INVALID_FORMAT, message: `${key} has a duplicate id: ${JSON.stringify(id)}` };
      }
      seen.add(idKey);
    }
  }

  if (project.meta !== undefined && !isObject(project.meta)) {
    return { code: ERROR_INVALID_FORMAT, message: 'meta must be an object when present' };
  }

  if (project.resources !== undefined) {
    if (!isObject(project.resources)) {
      return { code: ERROR_INVALID_FORMAT, message: 'resources must be an object when present' };
    }
    const passthrough = project.resources.cadgfPassthrough;
    if (passthrough !== undefined) {
      if (!isObject(passthrough)) {
        return { code: ERROR_INVALID_FORMAT, message: 'resources.cadgfPassthrough must be an object when present' };
      }
      if (passthrough.document !== undefined && !isObject(passthrough.document)) {
        return {
          code: ERROR_INVALID_FORMAT,
          message: 'resources.cadgfPassthrough.document must be an object when present',
        };
      }
      if (passthrough.entities !== undefined && !Array.isArray(passthrough.entities)) {
        return {
          code: ERROR_INVALID_FORMAT,
          message: 'resources.cadgfPassthrough.entities must be an array when present',
        };
      }
      // passthrough.entities intentionally do NOT require ids: they are opaque
      // CADGF records ordered by cadgfId with a canonical-JSON tiebreaker.
    }
  }

  return null;
}

// Envelope + structural validation, for the canonicalization/save boundary.
function validateCanonicalInput(project) {
  return validateEnvelope(project) ?? validateStructure(project);
}

// ---- canonicalization -------------------------------------------------------

// Pure: returns a fresh canonical model. Does not mutate the input. Timestamps
// are copied verbatim (never recomputed). Assumes a valid envelope.
function canonicalize(project) {
  const header = project.header ?? {};
  const proj = project.project ?? {};
  const resources = isObject(project.resources) ? project.resources : {};
  const passthrough = isObject(resources.cadgfPassthrough) ? resources.cadgfPassthrough : {};

  const layers = ensureDefaultLayer(asArray(project.layers));

  return {
    header: {
      format: PROJECT_FORMAT,
      version: header.version ?? PROJECT_VERSION,
    },
    project: {
      id: proj.id,
      name: proj.name ?? '',
      units: proj.units ?? DEFAULT_UNITS,
      createdAt: proj.createdAt ?? null,
      modifiedAt: proj.modifiedAt ?? null,
    },
    layers: [...layers].sort(byId).map(sortKeysDeep),
    entities: [...asArray(project.entities)].sort(byId).map(sortKeysDeep),
    constraints: [...asArray(project.constraints)].sort(byId).map(sortKeysDeep),
    features: [...asArray(project.features)].sort(byId).map(sortKeysDeep),
    resources: {
      cadgfPassthrough: {
        document: sortKeysDeep(isObject(passthrough.document) ? passthrough.document : {}),
        entities: [...asArray(passthrough.entities)].sort(comparePassthroughEntities).map(sortKeysDeep),
      },
    },
    meta: sortKeysDeep(isObject(project.meta) ? project.meta : {}),
  };
}

// ---- public API -------------------------------------------------------------

// Create a fresh, canonical VEMCAD-PROJECT model.
// Timestamps come from explicit `createdAt`/`modifiedAt`, else an injectable
// `clock.now()`, else wall-clock (creation path only — derive must not do this).
export function createProjectModel(options = {}) {
  const { id, name = '', units = DEFAULT_UNITS, createdAt, modifiedAt, clock } = options;
  if (typeof id !== 'string' || id.length === 0) {
    return fail(ERROR_INVALID_FORMAT, 'createProjectModel requires a non-empty string id');
  }
  const stamp = createdAt ?? clock?.now?.() ?? new Date().toISOString();
  const seed = {
    header: { format: PROJECT_FORMAT, version: PROJECT_VERSION },
    project: {
      id,
      name: String(name),
      units: String(units),
      createdAt: stamp,
      modifiedAt: modifiedAt ?? stamp,
    },
    layers: [{ id: DEFAULT_LAYER_ID, name: DEFAULT_LAYER_NAME }],
    entities: [],
    constraints: [],
    features: [],
    resources: { cadgfPassthrough: { document: {}, entities: [] } },
    meta: {},
  };
  // Route through normalize so a fresh model is self-validated, not just built.
  return normalizeProjectModel(seed);
}

// Validate + read a project from a JSON string or a plain object.
// Returns the validated (un-canonicalized) model; callers normalize as needed.
export function parseProjectModel(input) {
  let obj = input;
  if (typeof input === 'string') {
    try {
      obj = JSON.parse(input);
    } catch (e) {
      return fail(ERROR_INVALID_FORMAT, `malformed project JSON: ${e.message}`);
    }
  }
  const invalid = validateEnvelope(obj);
  if (invalid) return fail(invalid.code, invalid.message);
  return ok(obj);
}

// Canonicalize a project (stable ordering, default layer, completed structure)
// without altering timestamps.
export function normalizeProjectModel(project) {
  const invalid = validateCanonicalInput(project);
  if (invalid) return fail(invalid.code, invalid.message);
  return ok(canonicalize(project));
}

// Deterministic save: canonical JSON with a trailing newline. Byte-identical
// for equivalent inputs regardless of incoming key/array order.
export function serializeProjectModel(project) {
  const invalid = validateCanonicalInput(project);
  if (invalid) return fail(invalid.code, invalid.message);
  return ok(`${JSON.stringify(canonicalize(project), null, 2)}\n`);
}

// Migrate a project to the current version. Only v1 exists, so a valid project
// is already current → no-op. Future version steps slot in here.
export function migrateProjectModel(project) {
  const invalid = validateEnvelope(project);
  if (invalid) return fail(invalid.code, invalid.message);
  return ok(project, [
    { level: 'info', code: 'NO_MIGRATION_NEEDED', message: `project already at version ${PROJECT_VERSION}` },
  ]);
}
