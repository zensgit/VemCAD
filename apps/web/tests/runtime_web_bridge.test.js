import test from 'node:test';
import assert from 'node:assert/strict';
import { DocumentState } from '../../../deps/cadgamefusion/tools/web_viewer/state/documentState.js';
import { exportRuntimeProjectFromDocumentState, importRuntimeProjectToDocumentState } from '../shared/runtime_bridge.js';

const CLOCK = { now: () => '2026-05-25T00:00:00.000Z' };

function seededDocument() {
  const ds = new DocumentState();
  ds.addEntities([
    { type: 'line', layerId: 0, a: [0, 0], b: [10, 0] },
    { type: 'circle', layerId: 0, center: [5, 5], radius: 3 },
    { type: 'text', layerId: 0, position: [1, 1], text: 'hi', height: 2 },
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

test('DocumentState -> Project -> DocumentState round-trips the visible entities', () => {
  const src = seededDocument();
  const exported = exportRuntimeProjectFromDocumentState(src, { clock: CLOCK });
  assert.equal(exported.ok, true);

  const dst = new DocumentState();
  const imported = importRuntimeProjectToDocumentState(dst, exported.value, { clock: CLOCK });
  assert.equal(imported.ok, true);

  assert.deepEqual(
    dst.listEntities().map((e) => e.type).sort(),
    src.listEntities().map((e) => e.type).sort(),
  );
});

test('the bridge rejects a non-DocumentState argument', () => {
  assert.equal(exportRuntimeProjectFromDocumentState(null).error_code, 'INVALID_DOCUMENT_STATE');
  assert.equal(importRuntimeProjectToDocumentState({}, {}).error_code, 'INVALID_DOCUMENT_STATE');
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
