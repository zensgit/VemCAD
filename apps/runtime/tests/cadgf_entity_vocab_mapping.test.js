import test from 'node:test';
import assert from 'node:assert/strict';
import { deriveCadgfDocument, importProjectFromCadgfDocument } from '../scene/index.js';

const CLOCK = { now: () => '2026-09-09T09:09:09.000Z' };

function cadgfDoc(entities) {
  return {
    document_id: 'd1',
    cadgf_version: '0.0.0',
    schema_version: 1,
    feature_flags: { earcut: false, clipper2: false },
    metadata: { label: 'Doc', author: '', company: '', comment: '', created_at: 'T', modified_at: 'T', unit_name: 'mm', meta: {} },
    settings: { unit_scale: 1 },
    layers: [{ id: 0, name: '0', color: 16777215, visible: 1, locked: 0, printable: 1, frozen: 0, construction: 0 }],
    entities,
  };
}

test('CADGF numeric types import to the right kind; cadgfId preserved; id is e<id>', () => {
  const doc = cadgfDoc([
    { id: 2, type: 2, layer_id: 0, name: '', line: [[0, 0], [1, 1]] },
    { id: 5, type: 4, layer_id: 0, name: '', circle: { c: [0, 0], r: 3 } },
    { id: 7, type: 7, layer_id: 0, name: 'T', text: { pos: [0, 0], h: 2, rot: 0, value: 'hi' } },
  ]);
  const res = importProjectFromCadgfDocument(doc, { clock: CLOCK });
  assert.equal(res.ok, true);
  const byCadgfId = Object.fromEntries(res.value.entities.map((e) => [e.cadgfId, e]));
  assert.equal(byCadgfId[2].kind, 'line');
  assert.equal(byCadgfId[2].id, 'e2');
  assert.equal(byCadgfId[5].kind, 'circle');
  assert.equal(byCadgfId[7].kind, 'text');
});

test('unsupported CADGF types are preserved as passthrough, not modeled', () => {
  const doc = cadgfDoc([
    { id: 1, type: 2, layer_id: 0, name: '', line: [[0, 0], [1, 1]] },
    { id: 2, type: 5, layer_id: 0, name: '', ellipse: { c: [0, 0], rx: 2, ry: 1, rot: 0, a0: 0, a1: 6 } },
    { id: 3, type: 6, layer_id: 0, name: '', spline: { degree: 3, control: [[0, 0], [1, 1]], knots: [0, 1] } },
  ]);
  const res = importProjectFromCadgfDocument(doc, { clock: CLOCK });
  assert.equal(res.value.entities.length, 1); // only the line is modeled
  assert.equal(res.value.resources.cadgfPassthrough.entities.length, 2);
  assert.ok(res.diagnostics.some((d) => d.code === 'UNSUPPORTED_ENTITY_PASSTHROUGH'));
});

test('round-trip derive(import(doc)) preserves modeled + passthrough entities and ids', () => {
  const doc = cadgfDoc([
    { id: 2, type: 2, layer_id: 0, name: '', line: [[0, 0], [1, 1]] },
    { id: 4, type: 5, layer_id: 0, name: '', ellipse: { c: [0, 0], rx: 2, ry: 1, rot: 0, a0: 0, a1: 6 } },
  ]);
  const project = importProjectFromCadgfDocument(doc, { clock: CLOCK }).value;
  const redoc = deriveCadgfDocument(project, { clock: CLOCK }).value;

  const typeById = Object.fromEntries(redoc.entities.map((e) => [e.id, e.type]));
  assert.equal(typeById[2], 2, 'modeled line round-trips to id 2 / type 2');
  assert.equal(typeById[4], 5, 'passthrough ellipse round-trips to id 4 / type 5');

  const line = redoc.entities.find((e) => e.id === 2);
  assert.deepEqual(line.line, [[0, 0], [1, 1]]);
});

test('duplicate CADGF entity ids degrade gracefully (unique project ids + diagnostic), not abort', () => {
  const doc = cadgfDoc([
    { id: 1, type: 2, layer_id: 0, name: '', line: [[0, 0], [1, 1]] },
    { id: 1, type: 4, layer_id: 0, name: '', circle: { c: [0, 0], r: 2 } }, // same numeric id
  ]);
  const res = importProjectFromCadgfDocument(doc, { clock: CLOCK });
  assert.equal(res.ok, true); // does NOT fail the whole import
  assert.equal(res.value.entities.length, 2); // both entities kept
  const ids = res.value.entities.map((e) => e.id);
  assert.equal(new Set(ids).size, 2); // project ids are unique
  assert.deepEqual(res.value.entities.map((e) => e.cadgfId).sort(), [1, 1]); // cadgfId preserved
  assert.ok(res.diagnostics.some((d) => d.code === 'IMPORT_ID_COLLISION'));
});

test('duplicate CADGF layer ids degrade gracefully (keep first + diagnostic), not abort', () => {
  const doc = cadgfDoc([{ id: 1, type: 2, layer_id: 0, name: '', line: [[0, 0], [1, 1]] }]);
  doc.layers = [
    { id: 0, name: '0', color: 16777215, visible: 1, locked: 0, printable: 1, frozen: 0, construction: 0 },
    { id: 0, name: 'dup', color: 0, visible: 1, locked: 0, printable: 1, frozen: 0, construction: 0 },
  ];
  const res = importProjectFromCadgfDocument(doc, { clock: CLOCK });
  assert.equal(res.ok, true); // not aborted
  assert.equal(res.value.layers.length, 1); // duplicate dropped, first kept
  assert.equal(res.value.layers[0].name, '0');
  assert.equal(res.value.entities.length, 1); // entity referencing layer 0 survives
  assert.ok(res.diagnostics.some((d) => d.code === 'IMPORT_LAYER_ID_COLLISION'));
});

test('the single type<->kind mapping is mutually consistent (no second rule set)', () => {
  // import a doc that has one entity of each modeled type, re-derive, and check
  // every modeled entity kept its numeric type.
  const entities = [
    { id: 0, type: 0, layer_id: 0, name: '', polyline: [[0, 0], [1, 0]] },
    { id: 1, type: 1, layer_id: 0, name: '', point: [2, 3] },
    { id: 2, type: 2, layer_id: 0, name: '', line: [[0, 0], [1, 1]] },
    { id: 3, type: 3, layer_id: 0, name: '', arc: { c: [0, 0], r: 5, a0: 0, a1: 1, cw: 0 } },
    { id: 4, type: 4, layer_id: 0, name: '', circle: { c: [0, 0], r: 2 } },
    { id: 7, type: 7, layer_id: 0, name: '', text: { pos: [0, 0], h: 1, rot: 0, value: 'x' } },
  ];
  const project = importProjectFromCadgfDocument(cadgfDoc(entities), { clock: CLOCK }).value;
  const redoc = deriveCadgfDocument(project, { clock: CLOCK }).value;
  assert.deepEqual(redoc.entities.map((e) => e.type).sort((a, b) => a - b), [0, 1, 2, 3, 4, 7]);
});
