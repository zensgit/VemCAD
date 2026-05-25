import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createProjectModel,
  parseProjectModel,
  normalizeProjectModel,
  migrateProjectModel,
  serializeProjectModel,
  PROJECT_FORMAT,
  PROJECT_VERSION,
} from '../project/index.js';

const FIXED = '2026-05-25T00:00:00.000Z';

function sampleProject() {
  const res = createProjectModel({ id: 'p-001', name: 'Demo', units: 'mm', createdAt: FIXED, modifiedAt: FIXED });
  assert.equal(res.ok, true);
  return res.value;
}

test('createProjectModel produces a valid VEMCAD-PROJECT v1 envelope', () => {
  const p = sampleProject();
  assert.equal(p.header.format, PROJECT_FORMAT);
  assert.equal(p.header.version, PROJECT_VERSION);
  assert.equal(p.project.id, 'p-001');
  assert.equal(p.project.units, 'mm');
  assert.ok(p.layers.some((layer) => layer.id === 0), 'default layer 0 present');
  assert.deepEqual(p.entities, []);
  assert.deepEqual(p.resources.cadgfPassthrough, { document: {}, entities: [] });
});

test('createProjectModel rejects a missing id', () => {
  const res = createProjectModel({ name: 'no id' });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_PROJECT_FORMAT');
});

test('serialize -> parse -> serialize round-trips to identical bytes', () => {
  const p = sampleProject();
  const text = serializeProjectModel(p);
  assert.equal(text.ok, true);

  const parsed = parseProjectModel(text.value);
  assert.equal(parsed.ok, true);

  const reText = serializeProjectModel(parsed.value);
  assert.equal(reText.ok, true);
  assert.equal(reText.value, text.value);
});

test('parse accepts a plain object as well as a JSON string', () => {
  const p = sampleProject();
  const fromObject = parseProjectModel(p);
  const fromString = parseProjectModel(serializeProjectModel(p).value);
  assert.equal(fromObject.ok, true);
  assert.equal(fromString.ok, true);
});

test('parse rejects a wrong header format', () => {
  const res = parseProjectModel({ header: { format: 'NOT-VEMCAD', version: 1 }, project: { id: 'x' } });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_PROJECT_FORMAT');
});

test('parse rejects malformed JSON text', () => {
  const res = parseProjectModel('{ not valid json ');
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_PROJECT_FORMAT');
});

test('parse rejects a project without a usable id', () => {
  const res = parseProjectModel({ header: { format: PROJECT_FORMAT, version: 1 }, project: { id: '' } });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_PROJECT_FORMAT');
});

test('parse rejects an unsupported future version', () => {
  const p = sampleProject();
  const future = structuredClone(p);
  future.header.version = PROJECT_VERSION + 1;
  const res = parseProjectModel(future);
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'UNSUPPORTED_PROJECT_VERSION');
});

test('migrate is a no-op for a current v1 project', () => {
  const p = sampleProject();
  const res = migrateProjectModel(p);
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, p);
  assert.ok(res.diagnostics.some((d) => d.code === 'NO_MIGRATION_NEEDED'));
});

test('migrate rejects an unsupported future version', () => {
  const p = sampleProject();
  const future = structuredClone(p);
  future.header.version = PROJECT_VERSION + 1;
  const res = migrateProjectModel(future);
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'UNSUPPORTED_PROJECT_VERSION');
});

// P1 — a wrong-typed collection must fail loudly, never be coerced/dropped.
test('serialize rejects a wrong-typed collection instead of dropping data', () => {
  const bad = {
    header: { format: PROJECT_FORMAT, version: 1 },
    project: { id: 'x', name: '', units: 'mm', createdAt: FIXED, modifiedAt: FIXED },
    entities: { sneaky: true },
  };
  const res = serializeProjectModel(bad);
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_PROJECT_FORMAT');
});

// Role split: parse admits the envelope; normalize/serialize guard the save.
test('parse is envelope-only; structural validation is deferred to save', () => {
  const structurallyBad = {
    header: { format: PROJECT_FORMAT, version: 1 },
    project: { id: 'x' },
    entities: { sneaky: true },
  };
  assert.equal(parseProjectModel(structurallyBad).ok, true);
  assert.equal(normalizeProjectModel(structurallyBad).ok, false);
  assert.equal(serializeProjectModel(structurallyBad).ok, false);
});

// Missing (vs wrong-typed) collections are legitimately defaulted, not rejected.
test('missing collections are defaulted rather than treated as malformed', () => {
  const minimal = {
    header: { format: PROJECT_FORMAT, version: 1 },
    project: { id: 'x', name: '', units: 'mm', createdAt: FIXED, modifiedAt: FIXED },
  };
  const res = normalizeProjectModel(minimal);
  assert.equal(res.ok, true);
  assert.deepEqual(res.value.entities, []);
  assert.ok(res.value.layers.some((layer) => layer.id === 0));
});
