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
export const ERROR_INVALID_CADGF_DOCUMENT = 'INVALID_CADGF_DOCUMENT';

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

// Reverse of KIND_TO_TYPE (single source of truth). CADGF types not present
// here (ellipse 5 / spline 6 / block 8 / unknown) are imported as passthrough.
const TYPE_TO_KIND = Object.fromEntries(Object.entries(KIND_TO_TYPE).map(([kind, type]) => [type, kind]));

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
// "#RRGGBB"/"RRGGBB" hex string; return null if not a valid color.
function coerceColor(color) {
  if (Number.isInteger(color) && color >= 0 && color <= 16777215) return color;
  if (typeof color === 'string') {
    const hex = color.trim().replace(/^#/, '');
    if (/^[0-9a-fA-F]{6}$/.test(hex)) return parseInt(hex, 16);
  }
  return null;
}

// CADGF entity geometry field names (schema-defined). For a modeled kind, the
// geometry field name equals the kind (point/line/polyline/circle/arc/text).
const GEOMETRY_FIELDS = ['point', 'line', 'polyline', 'arc', 'circle', 'ellipse', 'spline', 'text'];

function isFiniteNum(v) {
  return typeof v === 'number' && Number.isFinite(v);
}

function isVec2(v) {
  return Array.isArray(v) && v.length === 2 && isFiniteNum(v[0]) && isFiniteNum(v[1]);
}

function isBoolInt(v) {
  return v === true || v === false || v === 0 || v === 1;
}

// Validate a geometry value against its CADGF schema shape and return a clean
// value containing ONLY schema-defined keys (object geometries are
// additionalProperties:false), or null when malformed. Covers every geometry
// kind so it serves both modeled entities and passthrough.
function buildGeometry(geomKind, value) {
  switch (geomKind) {
    case 'point':
      return isVec2(value) ? value : null;
    case 'line':
      return Array.isArray(value) && value.length === 2 && value.every(isVec2) ? value : null;
    case 'polyline':
      return Array.isArray(value) && value.every(isVec2) ? value : null;
    case 'circle':
      return isObject(value) && isVec2(value.c) && isFiniteNum(value.r)
        ? { c: value.c, r: value.r }
        : null;
    case 'arc':
      return isObject(value) && isVec2(value.c) && isFiniteNum(value.r)
        && isFiniteNum(value.a0) && isFiniteNum(value.a1) && isBoolInt(value.cw)
        ? { c: value.c, r: value.r, a0: value.a0, a1: value.a1, cw: value.cw }
        : null;
    case 'ellipse':
      return isObject(value) && isVec2(value.c) && isFiniteNum(value.rx) && isFiniteNum(value.ry)
        && isFiniteNum(value.rot) && isFiniteNum(value.a0) && isFiniteNum(value.a1)
        ? { c: value.c, rx: value.rx, ry: value.ry, rot: value.rot, a0: value.a0, a1: value.a1 }
        : null;
    case 'spline':
      return isObject(value) && Number.isInteger(value.degree)
        && Array.isArray(value.control) && value.control.every(isVec2)
        && Array.isArray(value.knots) && value.knots.every(isFiniteNum)
        ? { degree: value.degree, control: value.control, knots: value.knots }
        : null;
    case 'text':
      return isObject(value) && isVec2(value.pos) && isFiniteNum(value.h)
        && isFiniteNum(value.rot) && typeof value.value === 'string'
        ? { pos: value.pos, h: value.h, rot: value.rot, value: value.value }
        : null;
    default:
      return null;
  }
}

// Schema-known NON-geometry entity field types (from document.schema.json's
// entity properties). Every known field is validated/cleansed so derive never
// emits a schema-invalid value; truly-unknown fields pass through unchanged
// (the entity schema is additionalProperties:true). If the schema gains a typed
// field this table doesn't cover, the worst case is derive emits no value for
// it, and the independent schema validation step (S6) flags the drift.
const SCALAR_FIELD_SPECS = {
  line_type: 'string', color_source: 'string', text_kind: 'string',
  attribute_tag: 'string', attribute_default: 'string', attribute_prompt: 'string',
  dim_style: 'string', source_anchor_driver_type: 'string', source_anchor_driver_kind: 'string',
  line_weight: 'number', line_type_scale: 'number', text_width: 'number',
  text_width_factor: 'number', dim_text_rotation: 'number',
  attribute_flags: 'int', text_attachment: 'int', text_halign: 'int', text_valign: 'int',
  dim_type: 'int', source_bundle_id: 'int', source_anchor_driver_id: 'int',
  color_aci: 'int:0:255',
  attribute_invisible: 'boolean', attribute_constant: 'boolean', attribute_verify: 'boolean',
  attribute_preset: 'boolean', attribute_lock_position: 'boolean',
  dim_text_pos: 'vec2', source_anchor: 'vec2', leader_landing: 'vec2', leader_elbow: 'vec2',
  color: 'color',
};

function scalarOk(spec, value) {
  switch (spec) {
    case 'string': return typeof value === 'string';
    case 'number': return isFiniteNum(value);
    case 'int': return Number.isInteger(value);
    case 'int:0:255': return Number.isInteger(value) && value >= 0 && value <= 255;
    case 'boolean': return typeof value === 'boolean';
    case 'vec2': return isVec2(value);
    default: return false;
  }
}

// Cleanse one entity field: geometry is validated + reconstructed; color is
// coerced (hex -> int); other typed fields are validated and dropped if the
// wrong type; truly-unknown fields pass through. Returns { keep, value }.
function sanitizeKnownField(name, value) {
  if (GEOMETRY_FIELDS.includes(name)) {
    const geometry = buildGeometry(name, value);
    return geometry === null ? { keep: false } : { keep: true, value: geometry };
  }
  const spec = SCALAR_FIELD_SPECS[name];
  if (!spec) return { keep: true, value };
  if (spec === 'color') {
    const c = coerceColor(value);
    return c === null ? { keep: false } : { keep: true, value: c };
  }
  return scalarOk(spec, value) ? { keep: true, value } : { keep: false };
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
    color: coerceColor(layer.color) ?? 16777215,
    visible: toBoolInt(layer.visible, true),
    locked: toBoolInt(layer.locked, false),
    printable: toBoolInt(layer.printable, true),
    frozen: toBoolInt(layer.frozen, false),
    construction: toBoolInt(layer.construction, false),
  };
  if (layer.line_type !== undefined) out.line_type = String(layer.line_type);
  if (isFiniteNum(layer.line_weight)) out.line_weight = layer.line_weight;
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
  let schemaMigratedAt; // string → emit, otherwise omit
  if (passDoc && passDoc.schema_version !== undefined) {
    if (passDoc.schema_version === targetSchemaVersion) {
      const preserved = passDoc.schema_migrated_at;
      if (typeof preserved === 'string') {
        schemaMigratedAt = preserved;
      } else if (preserved !== undefined) {
        diagnostics.push({ level: 'warn', code: 'SCHEMA_MIGRATED_AT_DROPPED', message: `schema_migrated_at was ${typeof preserved}; dropped (must be a string)` });
      }
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

    // A modeled entity must carry valid geometry for its kind; reconstruct it
    // (schema keys only) and skip the entity if missing/malformed.
    const geometry = buildGeometry(kind, e[kind]);
    if (geometry === null) {
      diagnostics.push({ level: 'warn', code: 'INVALID_ENTITY_GEOMETRY', message: `entity ${JSON.stringify(id)} (${kind}) has missing or malformed geometry; skipped` });
      continue;
    }

    const out = {
      id: idFor.get(e),
      type: KIND_TO_TYPE[kind],
      layer_id: resolveEntityLayerId(layerId, id, diagnostics),
      name: typeof name === 'string' ? name : '',
      [kind]: geometry,
    };
    for (const [k, v] of Object.entries(rest)) {
      if (k === kind) continue; // this kind's geometry already emitted
      if (GEOMETRY_FIELDS.includes(k)) {
        diagnostics.push({ level: 'warn', code: 'FOREIGN_GEOMETRY_DROPPED', message: `entity ${JSON.stringify(id)} (${kind}) carried a ${k} field; dropped` });
        continue;
      }
      const cleansed = sanitizeKnownField(k, v);
      if (cleansed.keep) out[k] = cleansed.value;
      else diagnostics.push({ level: 'warn', code: 'ENTITY_FIELD_DROPPED', message: `entity ${JSON.stringify(id)} field ${JSON.stringify(k)} failed its CADGF type; dropped` });
    }
    entities.push(out);
  }
  for (const e of passthrough) {
    // Envelope was validated (id/type/layer_id/name). Cleanse every other field
    // (geometry included) so a malformed optional field can't invalidate the doc.
    const out = { id: idFor.get(e), type: e.type, layer_id: e.layer_id, name: e.name };
    for (const [k, v] of Object.entries(e)) {
      if (k === 'id' || k === 'type' || k === 'layer_id' || k === 'name') continue;
      const cleansed = sanitizeKnownField(k, v);
      if (cleansed.keep) out[k] = cleansed.value;
      else diagnostics.push({ level: 'warn', code: 'PASSTHROUGH_FIELD_DROPPED', message: `passthrough entity ${JSON.stringify(e.id)} field ${JSON.stringify(k)} failed its CADGF type; dropped` });
    }
    entities.push(out);
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
  if (typeof schemaMigratedAt === 'string') doc.schema_migrated_at = schemaMigratedAt;

  return ok(doc, diagnostics);
}

// Lenient inverse of the derive unit table: resolve a project unit from a CADGF
// metadata.unit_name (preferred) then settings.unit_scale; fall back to mm with
// a diagnostic rather than rejecting. The original name/scale are preserved in
// cadgfPassthrough.document so nothing is lost.
function importUnits(unitName, unitScale, diagnostics) {
  if (typeof unitName === 'string' && UNITS[unitName.trim().toLowerCase()]) {
    return unitName.trim().toLowerCase();
  }
  if (isFiniteNum(unitScale)) {
    for (const [unit, spec] of Object.entries(UNITS)) {
      if (spec.unit_scale === unitScale) return unit;
    }
  }
  diagnostics.push({ level: 'warn', code: 'UNIT_FALLBACK', message: `CADGF unit (name=${JSON.stringify(unitName)}, scale=${JSON.stringify(unitScale)}) not recognized; defaulted to mm (original kept in passthrough)` });
  return 'mm';
}

// Import a CADGF Document into a VEMCAD-PROJECT. This is a DEGRADED, one-way
// import — not the inverse of deriveCadgfDocument:
//   - CADGF carries no VemCAD constraints/features -> they come back empty.
//   - supported entity types are modeled; ellipse/spline/block/unknown are
//     preserved verbatim in cadgfPassthrough.entities.
//   - source document-level fields land in cadgfPassthrough.document so a later
//     derive can restore passthrough-owned metadata/flags/version.
// Re-uses the derive unit table, type<->kind map, and passthrough convention;
// it does NOT cleanse fields — a later deriveCadgfDocument is the single place
// that guarantees schema-valid output.
export function importProjectFromCadgfDocument(cadgfDocument, options = {}) {
  if (!isObject(cadgfDocument)) {
    return fail(ERROR_INVALID_CADGF_DOCUMENT, 'cadgf document must be an object');
  }
  const doc = cadgfDocument;
  const diagnostics = [];

  const units = importUnits(doc.metadata?.unit_name, doc.settings?.unit_scale, diagnostics);

  const stamp = options.clock?.now?.() ?? '';
  const projectId = typeof doc.document_id === 'string' && doc.document_id.length > 0
    ? doc.document_id
    : (options.projectId ?? 'imported-project');
  const name = typeof doc.metadata?.label === 'string' ? doc.metadata.label : '';

  // Layers preserve their CADGF fields (id stays the integer; re-derive cleanses).
  const layers = (Array.isArray(doc.layers) ? doc.layers : [])
    .filter((l) => isObject(l))
    .map((l) => ({ ...l }));

  // Entities: supported type -> modeled (numeric id -> "e<id>", cadgfId kept);
  // unsupported type -> verbatim passthrough.
  const entities = [];
  const passthroughEntities = [];
  for (const e of Array.isArray(doc.entities) ? doc.entities : []) {
    if (!isObject(e) || !isNonNegInt(e.id) || !Number.isInteger(e.type)) {
      diagnostics.push({ level: 'warn', code: 'INVALID_CADGF_ENTITY', message: `CADGF entity ${JSON.stringify(e?.id)} is missing a valid id/type; skipped` });
      continue;
    }
    const kind = TYPE_TO_KIND[e.type];
    if (kind === undefined) {
      passthroughEntities.push({ ...e });
      diagnostics.push({ level: 'info', code: 'UNSUPPORTED_ENTITY_PASSTHROUGH', message: `CADGF entity ${e.id} (type ${e.type}) is not v0-modeled; preserved as passthrough` });
      continue;
    }
    const { id, type, layer_id: layerIdRaw, name: entityName, ...rest } = e;
    entities.push({
      id: `e${id}`,
      kind,
      layerId: Number.isInteger(layerIdRaw) ? layerIdRaw : 0,
      cadgfId: id,
      name: typeof entityName === 'string' ? entityName : '',
      ...rest,
    });
  }

  // Source document-level fields -> cadgfPassthrough.document (complete set, so
  // a later derive can restore passthrough-owned values).
  const passthroughDocument = {};
  for (const key of ['document_id', 'schema_migrated_at', 'cadgf_version', 'schema_version', 'feature_flags', 'metadata', 'settings']) {
    if (doc[key] !== undefined) passthroughDocument[key] = doc[key];
  }

  diagnostics.push({
    level: 'warn',
    code: 'DEGRADED_IMPORT',
    message: 'CADGF documents carry no VemCAD constraints/features; the imported project has none. Project save/load is the only lossless path.',
  });

  const project = {
    header: { format: 'VEMCAD-PROJECT', version: 1 },
    project: { id: projectId, name, units, createdAt: stamp, modifiedAt: stamp },
    layers,
    entities,
    constraints: [],
    features: [],
    resources: { cadgfPassthrough: { document: passthroughDocument, entities: passthroughEntities } },
    meta: {},
  };

  const normalized = normalizeProjectModel(project);
  if (!normalized.ok) {
    return { ...normalized, diagnostics: [...diagnostics, ...(normalized.diagnostics ?? [])] };
  }
  return ok(normalized.value, diagnostics);
}
