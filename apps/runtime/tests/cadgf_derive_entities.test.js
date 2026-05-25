import test from 'node:test';
import assert from 'node:assert/strict';
import { createProjectModel } from '../project/index.js';
import { deriveCadgfDocument } from '../scene/index.js';

const FIXED = '2026-05-25T00:00:00.000Z';

function proj(overrides = {}) {
  const base = createProjectModel({ id: 'e', name: 'E', units: 'mm', createdAt: FIXED, modifiedAt: FIXED });
  return { ...base.value, ...overrides };
}

test('modeled entity kinds map to the correct CADGF numeric types with geometry passed through', () => {
  const p = proj({
    entities: [
      { id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]] },
      { id: 'e2', kind: 'circle', layerId: 0, circle: { c: [0, 0], r: 5 } },
      { id: 'e3', kind: 'arc', layerId: 0, arc: { c: [0, 0], r: 5, a0: 0, a1: 1, cw: 0 } },
      { id: 'e4', kind: 'point', layerId: 0, point: [2, 3] },
      { id: 'e5', kind: 'polyline', layerId: 0, polyline: [[0, 0], [1, 0], [1, 1]] },
      { id: 'e6', kind: 'text', layerId: 0, text: { pos: [0, 0], h: 2.5, rot: 0, value: 'hi' } },
    ],
  });
  const res = deriveCadgfDocument(p);
  assert.equal(res.ok, true);

  const byType = Object.fromEntries(res.value.entities.map((e) => [e.type, e]));
  assert.ok(byType[2]?.line, 'line -> type 2');
  assert.ok(byType[4]?.circle, 'circle -> type 4');
  assert.ok(byType[3]?.arc, 'arc -> type 3');
  assert.ok(byType[1]?.point, 'point -> type 1');
  assert.ok(byType[0]?.polyline, 'polyline -> type 0');
  assert.ok(byType[7]?.text, 'text -> type 7');

  for (const e of res.value.entities) {
    assert.equal(typeof e.id, 'number');
    assert.equal(typeof e.type, 'number');
    assert.equal(typeof e.layer_id, 'number');
    assert.equal(typeof e.name, 'string');
    assert.equal('kind' in e, false, 'product-only kind must not leak into CADGF');
    assert.equal('layerId' in e, false, 'product-only layerId must not leak');
  }
});

test('existing cadgfId is preserved; entities without one get the smallest free id', () => {
  const p = proj({
    entities: [
      { id: 'e1', kind: 'line', layerId: 0, cadgfId: 5, line: [[0, 0], [1, 1]] },
      { id: 'e2', kind: 'circle', layerId: 0, circle: { c: [0, 0], r: 1 } },
      { id: 'e3', kind: 'point', layerId: 0, cadgfId: 0, point: [0, 0] },
    ],
  });
  const ids = deriveCadgfDocument(p).value.entities.map((e) => e.id).sort((a, b) => a - b);
  assert.deepEqual(ids, [0, 1, 5]); // 0 and 5 claimed; e2 -> smallest free = 1
});

test('an id collision is reported and reassigned so emitted ids stay unique', () => {
  const p = proj({
    entities: [
      { id: 'e1', kind: 'line', layerId: 0, cadgfId: 4, line: [[0, 0], [1, 1]] },
      { id: 'e2', kind: 'circle', layerId: 0, cadgfId: 4, circle: { c: [0, 0], r: 1 } },
    ],
  });
  const res = deriveCadgfDocument(p);
  assert.ok(res.diagnostics.some((d) => d.code === 'ENTITY_ID_COLLISION'));
  const ids = res.value.entities.map((e) => e.id);
  assert.equal(new Set(ids).size, ids.length);
});

test('an unsupported entity kind in entities is skipped with a diagnostic', () => {
  const p = proj({
    entities: [
      { id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]] },
      { id: 'e2', kind: 'ellipse', layerId: 0, ellipse: {} }, // belongs in passthrough, not entities
    ],
  });
  const res = deriveCadgfDocument(p);
  assert.equal(res.value.entities.length, 1);
  assert.ok(res.diagnostics.some((d) => d.code === 'UNSUPPORTED_ENTITY_KIND'));
});

test('valid passthrough entities are emitted verbatim; invalid ones are skipped with a diagnostic', () => {
  const p = proj({
    entities: [{ id: 'e1', kind: 'line', layerId: 0, cadgfId: 1, line: [[0, 0], [1, 1]] }],
    resources: {
      cadgfPassthrough: {
        document: {},
        entities: [
          { id: 9, type: 5, layer_id: 0, name: '', ellipse: { c: [0, 0], rx: 2, ry: 1, rot: 0, a0: 0, a1: 6 } },
          { id: 'bad', type: 6, layer_id: 0, name: '' }, // non-integer id -> required-field check fails
        ],
      },
    },
  });
  const res = deriveCadgfDocument(p);
  const ellipse = res.value.entities.find((e) => e.type === 5);
  assert.ok(ellipse?.ellipse, 'valid passthrough ellipse emitted verbatim');
  assert.ok(res.diagnostics.some((d) => d.code === 'INVALID_PASSTHROUGH_ENTITY'));
});

test('layers gain CADGF-required fields with defaults; hex color is parsed to an integer', () => {
  const p = proj({ layers: [{ id: 0, name: '0' }, { id: 1, name: 'Red', color: '#ff0000', visible: false }] });
  const red = deriveCadgfDocument(p).value.layers.find((l) => l.id === 1);
  assert.equal(red.color, 0xff0000);
  assert.equal(red.visible, 0);
  assert.equal(red.locked, 0);
  assert.equal(red.printable, 1);
  assert.equal(red.frozen, 0);
  assert.equal(red.construction, 0);
});

test('a non-integer layer id fails derive instead of collapsing to 0 (P1)', () => {
  const p = proj({ layers: [{ id: 0, name: '0' }, { id: 'abc', name: 'bad' }] });
  const res = deriveCadgfDocument(p);
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_LAYER_ID');
});

test('an entity with an invalid layerId is defaulted to 0 with a diagnostic (recoverable)', () => {
  const p = proj({ entities: [{ id: 'e1', kind: 'line', layerId: 'nope', line: [[0, 0], [1, 1]] }] });
  const res = deriveCadgfDocument(p);
  assert.equal(res.ok, true);
  assert.equal(res.value.entities[0].layer_id, 0);
  assert.ok(res.diagnostics.some((d) => d.code === 'ENTITY_LAYER_ID_DEFAULTED'));
});
