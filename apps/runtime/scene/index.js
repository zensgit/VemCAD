// VemCAD Project Runtime — `scene` module (v0 / S4).
//
// deriveCadgfDocument(project, options): derive a CADGF Document (the派生 scene /
// interchange format) from a VEMCAD-PROJECT. The Project is the source of truth;
// the CADGF Document is produced fresh and must validate against
// deps/cadgamefusion/schemas/document.schema.json (checked independently in S6).
//
// Field ownership is frozen (docs/VEMCAD_PROJECT_RUNTIME_V0_DEVELOPMENT_20260525.md §3):
//   - deriver-owned : cadgf_version, schema_version (target), schema_migrated_at (conditional)
//   - project-owned : document_id←id, metadata.label←name, unit_name+unit_scale←units
//   - passthrough   : feature_flags, metadata.{author,company,comment,created_at,modified_at,meta}
//
// Two conventions used here (and read back identically by S5 import):
//   - unit_scale is millimetres-per-unit (mm=1, cm=10, m=1000, in=25.4, ft=304.8).
//   - Project entities carry CADGF-SHAPED geometry (e.g. line:[[x,y],[x,y]],
//     circle:{c,r}), not friendly aliases — so derive is envelope translation
//     (kind→type, string id→numeric, layerId→layer_id, +name) with geometry
//     passed through verbatim. This matches the CADGF C API / web convention.

import { normalizeProjectModel } from '../project/index.js';
import { compareIds } from '../shared/ordering.js';

export const ERROR_UNSUPPORTED_UNIT = 'UNSUPPORTED_PROJECT_UNIT';
export const ERROR_INVALID_LAYER_ID = 'INVALID_LAYER_ID';

// Deriver-owned defaults. cadgf_version/schema_version describe what the deriver
// PRODUCES (the target), never echoed from an imported source.
export const TARGET_SCHEMA_VERSION = 1;
export const DEFAULT_TARGET_CADGF_VERSION = '0.0.0';

// Project entity kind ↔ CADGF numeric type. Only the v0-modeled kinds; ellipse
// (5) / spline (6) / block (8) / hatch / dimension are carried via passthrough.
const KIND_TO_TYPE = {
  polyline: 0,
  point: 1,
  line: 2,
  arc: 3,
  circle: 4,
  text: 7,
};

// units → { unit_name, unit_scale } where unit_scale is millimetres per unit.
const UNITS = {
  mm: { unit_name: 'mm', unit_scale: 1 },
  cm: { unit_name: 'cm', unit_scale: 10 },
  m: { unit_name: 'm', unit_scale: 1000 },
  in: { unit_name: 'in', unit_scale: 25.4 },
  ft: { unit_name: 'ft', unit_scale: 304.8 },
};

function ok(value, diagnostics = []) {
  return { ok: true, value, diagnostics };
}

function fail(errorCode, error, diagnostics = []) {
  return { ok: false, error_code: errorCode, error, diagnostics };
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isNonNegInt(value) {
  return Number.isInteger(value) && value >= 0;
}

function toBoolInt(value, fallback) {
  const v = value === undefined ? fallback : value;
  return v ? 1 : 0;
}

// CADGF layer/entity color is an integer 0xRRGGBB. Accept an int in range or a
// "#RRGGBB"/"RRGGBB" hex string; otherwise fall back (default white).
function resolveColor(color, fallback = 16777215) {
  if (Number.isInteger(color) && color >= 0 && color <= 16777215) return color;
  if (typeof color === 'string') {
    const hex = color.trim().replace(/^#/, '');
    if (/^[0-9a-fA-F]{6}$/.test(hex)) return parseInt(hex, 16);
  }
  return fallback;
}

// CADGF layer ids are integers. Accept a non-negative integer or its canonical
// decimal string ("0","5"); reject "abc","05","-1","5.0" (returns null). Used to
// fail derive loudly rather than silently collapse a bad id to 0 (which could
// duplicate the default layer).
function toCadgfLayerId(id) {
  if (typeof id === 'number' && Number.isInteger(id) && id >= 0) return id;
  if (typeof id === 'string' && /^(0|[1-9]\d*)$/.test(id)) return Number(id);
  return null;
}

function resolveEntityLayerId(layerId, entityId, diagnostics) {
  const id = toCadgfLayerId(layerId);
  if (id !== null) return id;
  diagnostics.push({ level: 'warn', code: 'ENTITY_LAYER_ID_DEFAULTED', message: `entity ${JSON.stringify(entityId)} layerId ${JSON.stringify(layerId)} is not a valid layer id; defaulted to 0` });
  return 0;
}

// CADGF metadata scalars must be strings. Coerce non-strings (reporting it) so
// the derived document validates even when passthrough carried a bad type.
function asMetaString(value, field, diagnostics) {
  if (value === undefined || value === null) return '';
  if (typeof value === 'string') return value;
  diagnostics.push({ level: 'warn', code: 'METADATA_VALUE_COERCED', message: `metadata.${field} was ${typeof value}; coerced to string` });
  return String(value);
}

// CADGF metadata.meta is a string->string map. Coerce non-string values.
function sanitizeMeta(meta, diagnostics) {
  if (!isObject(meta)) return {};
  const out = {};
  for (const [key, value] of Object.entries(meta)) {
    if (typeof value === 'string') {
      out[key] = value;
    } else {
      diagnostics.push({ level: 'warn', code: 'METADATA_VALUE_COERCED', message: `metadata.meta.${JSON.stringify(key)} was ${typeof value}; coerced to string` });
      out[key] = String(value);
    }
  }
  return out;
}

function deriveLayer(layer) {
  const out = {
    id: toCadgfLayerId(layer.id),
    name: String(layer.name ?? ''),
    color: resolveColor(layer.color),
    visible: toBoolInt(layer.visible, true),
    locked: toBoolInt(layer.locked, false),
    printable: toBoolInt(layer.printable, true),
    frozen: toBoolInt(layer.frozen, false),
    construction: toBoolInt(layer.construction, false),
  };
  if (layer.line_type !== undefined) out.line_type = String(layer.line_type);
  if (typeof layer.line_weight === 'number') out.line_weight = layer.line_weight;
  return out;
}

// Resolve a CADGF integer id for every entity that will be emitted, honoring
// explicit ids (modeled cadgfId, passthrough id), allocating the smallest free
// non-negative integer for the rest, and reporting collisions. Deterministic:
// explicit claims are processed passthrough-first then modeled, both in the
// project's canonical order; reassignments and fresh allocations follow.
function resolveEntityIds(modeled, passthrough, diagnostics) {
  const claimed = new Set();
  const resolved = new Map(); // entity object -> integer id
  const needsFresh = []; // entities awaiting allocation, in deterministic order

  const claimExplicit = (entity, id, label) => {
    if (claimed.has(id)) {
      diagnostics.push({ level: 'warn', code: 'ENTITY_ID_COLLISION', message: `${label} id ${id} already in use; reassigning` });
      needsFresh.push(entity);
    } else {
      claimed.add(id);
      resolved.set(entity, id);
    }
  };

  for (const e of passthrough) claimExplicit(e, e.id, 'passthrough entity');
  for (const e of modeled) {
    if (isNonNegInt(e.cadgfId)) claimExplicit(e, e.cadgfId, 'entity');
  }
  for (const e of modeled) {
    if (!isNonNegInt(e.cadgfId)) needsFresh.push(e);
  }

  let next = 0;
  for (const entity of needsFresh) {
    while (claimed.has(next)) next += 1;
    claimed.add(next);
    resolved.set(entity, next);
  }
  return resolved;
}

// Derive a CADGF Document from a VEMCAD-PROJECT.
export function deriveCadgfDocument(project, options = {}) {
  const normalized = normalizeProjectModel(project);
  if (!normalized.ok) return normalized;
  const p = normalized.value;
  const diagnostics = [];

  const units = UNITS[p.project.units];
  if (!units) {
    return fail(ERROR_UNSUPPORTED_UNIT, `unsupported project unit: ${JSON.stringify(p.project.units)}`);
  }

  const clock = options.clock;
  const targetSchemaVersion = options.schemaVersion ?? TARGET_SCHEMA_VERSION;
  const targetCadgfVersion = options.cadgfVersion ?? DEFAULT_TARGET_CADGF_VERSION;

  const passDoc = isObject(p.resources?.cadgfPassthrough?.document) ? p.resources.cadgfPassthrough.document : null;
  const passMeta = isObject(passDoc?.metadata) ? passDoc.metadata : {};

  // ---- metadata (project-owned label/unit_name; passthrough-owned rest) ----
  // Timestamps: passthrough -> project -> injected clock -> '' (never Date.now()).
  // Scalars are string-coerced and meta sanitized so the derived doc validates.
  const metadata = {
    label: asMetaString(p.project.name, 'label', diagnostics),
    author: asMetaString(passMeta.author, 'author', diagnostics),
    company: asMetaString(passMeta.company, 'company', diagnostics),
    comment: asMetaString(passMeta.comment, 'comment', diagnostics),
    created_at: asMetaString(passMeta.created_at ?? p.project.createdAt ?? clock?.now?.(), 'created_at', diagnostics),
    modified_at: asMetaString(passMeta.modified_at ?? p.project.modifiedAt ?? clock?.now?.(), 'modified_at', diagnostics),
    unit_name: units.unit_name,
    meta: sanitizeMeta(passMeta.meta, diagnostics),
  };

  // ---- feature_flags (passthrough-owned; safe default for a fresh project) ----
  const pf = passDoc?.feature_flags;
  const featureFlags = isObject(pf)
    ? { earcut: !!pf.earcut, clipper2: !!pf.clipper2 }
    : { earcut: false, clipper2: false };

  // ---- deriver-owned schema_migrated_at (tri-state) ----
  // A fresh project carries an empty passthrough document ({}); only a real
  // imported source carries a schema_version, so gate on that (not truthiness)
  // to keep new projects from emitting a fake migration timestamp.
  let schemaMigratedAt; // undefined → omit
  if (passDoc && passDoc.schema_version !== undefined) {
    if (passDoc.schema_version === targetSchemaVersion) {
      schemaMigratedAt = passDoc.schema_migrated_at; // preserve (may be undefined)
    } else {
      diagnostics.push({
        level: 'warn',
        code: 'SCHEMA_VERSION_MIGRATED',
        message: `source schema_version ${JSON.stringify(passDoc.schema_version)} -> target ${targetSchemaVersion}`,
      });
      schemaMigratedAt = clock?.now?.() ?? p.project.modifiedAt ?? undefined;
    }
  }

  // ---- layers (CADGF layer id must be a non-negative integer; fail loudly) ----
  for (const layer of p.layers) {
    if (toCadgfLayerId(layer.id) === null) {
      return fail(ERROR_INVALID_LAYER_ID, `layer id ${JSON.stringify(layer.id)} is not a non-negative integer; cannot derive a CADGF layer id`);
    }
  }
  const layers = p.layers.map((layer) => deriveLayer(layer)).sort((a, b) => a.id - b.id);

  // ---- entities: modeled (translated) + passthrough (validated, verbatim) ----
  const modeled = [];
  for (const e of p.entities) {
    if (!(e.kind in KIND_TO_TYPE)) {
      diagnostics.push({ level: 'warn', code: 'UNSUPPORTED_ENTITY_KIND', message: `entity ${JSON.stringify(e.id)} kind ${JSON.stringify(e.kind)} is not a v0-modeled kind; skipped` });
      continue;
    }
    modeled.push(e);
  }

  const passthrough = [];
  for (const e of p.resources?.cadgfPassthrough?.entities ?? []) {
    const okShape = isObject(e) && isNonNegInt(e.id) && isNonNegInt(e.type) && Number.isInteger(e.layer_id) && typeof e.name === 'string';
    if (!okShape) {
      diagnostics.push({ level: 'warn', code: 'INVALID_PASSTHROUGH_ENTITY', message: `passthrough entity ${JSON.stringify(e?.id)} missing required CADGF fields {id,type,layer_id,name}; skipped` });
      continue;
    }
    passthrough.push(e);
  }

  const idFor = resolveEntityIds(modeled, passthrough, diagnostics);

  const entities = [];
  for (const e of modeled) {
    const { id, kind, layerId, name, cadgfId, ...rest } = e;
    entities.push({
      ...rest,
      id: idFor.get(e),
      type: KIND_TO_TYPE[kind],
      layer_id: resolveEntityLayerId(layerId, id, diagnostics),
      name: typeof name === 'string' ? name : '',
    });
  }
  for (const e of passthrough) {
    entities.push({ ...e, id: idFor.get(e) });
  }
  entities.sort((a, b) => a.id - b.id);

  // ---- assemble document (only includes schema_migrated_at when defined) ----
  const doc = {
    document_id: p.project.id,
    cadgf_version: targetCadgfVersion,
    schema_version: targetSchemaVersion,
    feature_flags: featureFlags,
    metadata,
    settings: { unit_scale: units.unit_scale },
    layers,
    entities,
  };
  if (schemaMigratedAt !== undefined) doc.schema_migrated_at = schemaMigratedAt;

  return ok(doc, diagnostics);
}
