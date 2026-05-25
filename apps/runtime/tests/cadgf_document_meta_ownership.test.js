import test from 'node:test';
import assert from 'node:assert/strict';
import { createProjectModel } from '../project/index.js';
import { deriveCadgfDocument, TARGET_SCHEMA_VERSION, DEFAULT_TARGET_CADGF_VERSION } from '../scene/index.js';

const FIXED = '2026-05-25T00:00:00.000Z';
const CLOCK = { now: () => '2026-09-09T09:09:09.000Z' };

function newProject(overrides = {}) {
  const base = createProjectModel({ id: 'proj-1', name: 'Sample', units: 'mm', createdAt: FIXED, modifiedAt: FIXED });
  assert.equal(base.ok, true);
  return { ...base.value, ...overrides };
}

function passthrough(documentFields) {
  return { resources: { cadgfPassthrough: { document: documentFields, entities: [] } } };
}

test('deriver-owned version fields come from the target, never echoed from passthrough', () => {
  const p = newProject(passthrough({ cadgf_version: '9.9.9', schema_version: 999 }));
  const res = deriveCadgfDocument(p, { clock: CLOCK });
  assert.equal(res.ok, true);
  assert.equal(res.value.schema_version, TARGET_SCHEMA_VERSION);
  assert.equal(res.value.cadgf_version, DEFAULT_TARGET_CADGF_VERSION);
});

test('project-owned fields override: document_id<-id, metadata.label<-name', () => {
  const p = newProject(passthrough({ metadata: { label: 'OLD LABEL' } }));
  const res = deriveCadgfDocument(p, { clock: CLOCK });
  assert.equal(res.value.document_id, 'proj-1');
  assert.equal(res.value.metadata.label, 'Sample');
});

test('passthrough-owned metadata is preserved from the NESTED source document', () => {
  const p = newProject(
    passthrough({ metadata: { author: 'Ada', company: 'ACME', comment: 'hi', created_at: 'T0', modified_at: 'T1', meta: { k: 'v' } } }),
  );
  const m = deriveCadgfDocument(p, { clock: CLOCK }).value.metadata;
  assert.equal(m.author, 'Ada');
  assert.equal(m.company, 'ACME');
  assert.equal(m.comment, 'hi');
  assert.equal(m.created_at, 'T0');
  assert.equal(m.modified_at, 'T1');
  assert.deepEqual(m.meta, { k: 'v' });
});

test('new project (no passthrough): timestamps from project, schema_migrated_at omitted, safe feature_flags', () => {
  const res = deriveCadgfDocument(newProject(), { clock: CLOCK });
  assert.equal(res.value.metadata.created_at, FIXED);
  assert.equal(res.value.metadata.modified_at, FIXED);
  assert.equal('schema_migrated_at' in res.value, false);
  assert.deepEqual(res.value.feature_flags, { earcut: false, clipper2: false });
});

test('schema_migrated_at is preserved when source schema_version matches target', () => {
  const p = newProject(passthrough({ schema_version: TARGET_SCHEMA_VERSION, schema_migrated_at: 'WHEN' }));
  const res = deriveCadgfDocument(p, { clock: CLOCK });
  assert.equal(res.value.schema_migrated_at, 'WHEN');
  assert.equal(res.diagnostics.some((d) => d.code === 'SCHEMA_VERSION_MIGRATED'), false);
});

test('schema_migrated_at uses injected clock + diagnostic when source version differs', () => {
  const p = newProject(passthrough({ schema_version: TARGET_SCHEMA_VERSION + 5 }));
  const res = deriveCadgfDocument(p, { clock: CLOCK });
  assert.equal(res.value.schema_migrated_at, '2026-09-09T09:09:09.000Z');
  assert.ok(res.diagnostics.some((d) => d.code === 'SCHEMA_VERSION_MIGRATED'));
});

test('feature_flags are passthrough-owned when present', () => {
  const p = newProject(passthrough({ feature_flags: { earcut: true, clipper2: false } }));
  assert.deepEqual(deriveCadgfDocument(p, { clock: CLOCK }).value.feature_flags, { earcut: true, clipper2: false });
});

test('derive is deterministic for the same project + options', () => {
  const p = newProject(passthrough({ metadata: { author: 'Ada' } }));
  const a = deriveCadgfDocument(p, { clock: CLOCK }).value;
  const b = deriveCadgfDocument(p, { clock: CLOCK }).value;
  assert.equal(JSON.stringify(a), JSON.stringify(b));
});
