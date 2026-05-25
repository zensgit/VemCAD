import test from 'node:test';
import assert from 'node:assert/strict';
import { importProjectFromCadgfDocument } from '../scene/index.js';

const CLOCK = { now: () => '2026-09-09T09:09:09.000Z' };

function minimalDoc(extra = {}) {
  return {
    document_id: 'd',
    cadgf_version: '0.0.0',
    schema_version: 1,
    feature_flags: { earcut: false, clipper2: false },
    metadata: { label: 'L', author: 'A', company: '', comment: '', created_at: 'T0', modified_at: 'T1', unit_name: 'mm', meta: { k: 'v' } },
    settings: { unit_scale: 1 },
    layers: [{ id: 0, name: '0', color: 0, visible: 1, locked: 0, printable: 1, frozen: 0, construction: 0 }],
    entities: [],
    ...extra,
  };
}

test('import reports a degraded-import diagnostic and yields empty constraints/features', () => {
  const res = importProjectFromCadgfDocument(minimalDoc(), { clock: CLOCK });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value.constraints, []);
  assert.deepEqual(res.value.features, []);
  assert.ok(res.diagnostics.some((d) => d.code === 'DEGRADED_IMPORT'));
});

test('source document-level fields land complete in cadgfPassthrough.document', () => {
  const res = importProjectFromCadgfDocument(minimalDoc({ schema_migrated_at: 'WHEN' }), { clock: CLOCK });
  const pd = res.value.resources.cadgfPassthrough.document;
  assert.equal(pd.cadgf_version, '0.0.0');
  assert.equal(pd.schema_version, 1);
  assert.equal(pd.schema_migrated_at, 'WHEN');
  assert.deepEqual(pd.feature_flags, { earcut: false, clipper2: false });
  assert.equal(pd.metadata.author, 'A');
  assert.deepEqual(pd.metadata.meta, { k: 'v' });
  assert.deepEqual(pd.settings, { unit_scale: 1 });
});

test('project-owned fields come from the document: id<-document_id, name<-label', () => {
  const res = importProjectFromCadgfDocument(minimalDoc(), { clock: CLOCK });
  assert.equal(res.value.project.id, 'd');
  assert.equal(res.value.project.name, 'L');
});

test('a missing document_id falls back to a stable default id', () => {
  const doc = minimalDoc();
  delete doc.document_id;
  const res = importProjectFromCadgfDocument(doc, { clock: CLOCK });
  assert.equal(res.value.project.id, 'imported-project');
});

test('a non-object input is rejected', () => {
  const res = importProjectFromCadgfDocument('nope');
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_CADGF_DOCUMENT');
});
