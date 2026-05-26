import test from 'node:test';
import assert from 'node:assert/strict';
import { DocumentState } from '../../../deps/cadgamefusion/tools/web_viewer/state/documentState.js';
import { exportRuntimeProjectFromDocumentState, importRuntimeProjectToDocumentState } from '../shared/runtime_bridge.js';

const CLOCK = { now: () => '2026-05-25T00:00:00.000Z' };

function seededDocument() {
  const ds = new DocumentState();
  ds.addEntities([
    { type: 'line', layerId: 0, start: { x: 0, y: 0 }, end: { x: 10, y: 0 } },
    { type: 'circle', layerId: 0, center: { x: 5, y: 5 }, radius: 3 },
    { type: 'text', layerId: 0, position: { x: 1, y: 1 }, value: 'hi', height: 2 },
  ]);
  return ds;
}

test('exportRuntimeProjectFromDocumentState bridges through CADGF (kinds + cadgfId)', () => {
  const res = exportRuntimeProjectFromDocumentState(seededDocument(), { clock: CLOCK });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value.entities.map((e) => e.kind).sort(), ['circle', 'line', 'text']);
  for (const entity of res.value.entities) {
    assert.equal(typeof entity.cadgfId, 'number');
  }
  // CADGF carries no constraints/features, so the degraded-import diagnostic surfaces.
  assert.ok(res.diagnostics.some((d) => d.code === 'DEGRADED_IMPORT'));
});

test('export is deterministic across calls when a clock is injected', () => {
  const ds = seededDocument();
  const a = exportRuntimeProjectFromDocumentState(ds, { clock: CLOCK }).value;
  const b = exportRuntimeProjectFromDocumentState(ds, { clock: CLOCK }).value;
  assert.equal(JSON.stringify(a), JSON.stringify(b));
  // neither of the adapter's wall-clock sources may leak: metadata timestamps...
  assert.equal(a.resources.cadgfPassthrough.document.metadata.created_at, '2026-05-25T00:00:00.000Z');
  assert.equal(a.resources.cadgfPassthrough.document.metadata.modified_at, '2026-05-25T00:00:00.000Z');
  // ...nor the `web-${Date.now()}` default document_id (project.id is pinned).
  assert.equal(a.project.id, 'web-export');
});

test('a caller-supplied documentId becomes the project id', () => {
  const res = exportRuntimeProjectFromDocumentState(seededDocument(), { clock: CLOCK, documentId: 'proj-42' });
  assert.equal(res.value.project.id, 'proj-42');
});

test('DocumentState -> Project -> DocumentState round-trips entities, layers and geometry', () => {
  const src = seededDocument();
  const exported = exportRuntimeProjectFromDocumentState(src, { clock: CLOCK });
  assert.equal(exported.ok, true);

  const dst = new DocumentState();
  const imported = importRuntimeProjectToDocumentState(dst, exported.value, { clock: CLOCK });
  assert.equal(imported.ok, true);

  assert.equal(dst.listEntities().length, src.listEntities().length);
  assert.equal(dst.listLayers().length, src.listLayers().length);
  assert.deepEqual(
    dst.listEntities().map((e) => e.type).sort(),
    src.listEntities().map((e) => e.type).sort(),
  );

  // geometry sample: the line endpoints survive the round-trip (not degenerate)
  const srcLine = src.listEntities().find((e) => e.type === 'line');
  const dstLine = dst.listEntities().find((e) => e.type === 'line');
  assert.deepEqual(dstLine.start, srcLine.start);
  assert.deepEqual(dstLine.end, srcLine.end);
  assert.deepEqual(dstLine.start, { x: 0, y: 0 });
  assert.deepEqual(dstLine.end, { x: 10, y: 0 });
});

test('the bridge rejects a non-DocumentState argument', () => {
  assert.equal(exportRuntimeProjectFromDocumentState(null).error_code, 'INVALID_DOCUMENT_STATE');
  // half-shaped: has listEntities but not listLayers (which exportCadgfDocument needs)
  assert.equal(exportRuntimeProjectFromDocumentState({ listEntities: () => [] }).error_code, 'INVALID_DOCUMENT_STATE');
  assert.equal(importRuntimeProjectToDocumentState({}, {}).error_code, 'INVALID_DOCUMENT_STATE');
});

test('export keeps the {ok:false} contract when the adapter throws', () => {
  const throwingState = { listEntities: () => [], listLayers: () => { throw new Error('boom'); } };
  const res = exportRuntimeProjectFromDocumentState(throwingState, { clock: CLOCK });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'BRIDGE_EXPORT_FAILED');
});

test('importRuntimeProjectToDocumentState propagates a derive failure', () => {
  const badProject = {
    header: { format: 'VEMCAD-PROJECT', version: 1 },
    project: { id: 'x', name: 'x', units: 'league', createdAt: '', modifiedAt: '' },
    layers: [{ id: 0, name: '0' }],
    entities: [],
    constraints: [],
    features: [],
    resources: { cadgfPassthrough: { document: {}, entities: [] } },
    meta: {},
  };
  const res = importRuntimeProjectToDocumentState(new DocumentState(), badProject, { clock: CLOCK });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'UNSUPPORTED_PROJECT_UNIT');
});
