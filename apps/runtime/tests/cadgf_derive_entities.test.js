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

test('malformed modeled geometry is skipped with a diagnostic, never emitted (P1)', () => {
  const p = proj({
    entities: [
      { id: 'e1', kind: 'line', layerId: 0, line: 'not-a-line' }, // malformed
      { id: 'e2', kind: 'circle', layerId: 0, circle: { c: [0, 0], r: 5 } }, // valid
    ],
  });
  const res = deriveCadgfDocument(p);
  assert.equal(res.ok, true);
  assert.equal(res.value.entities.length, 1);
  assert.equal(res.value.entities[0].type, 4);
  assert.ok(res.diagnostics.some((d) => d.code === 'INVALID_ENTITY_GEOMETRY'));
});

test('object geometry is reconstructed to schema keys only (additionalProperties:false)', () => {
  const p = proj({ entities: [{ id: 'e1', kind: 'circle', layerId: 0, circle: { c: [0, 0], r: 5, extra: 'nope' } }] });
  const circle = deriveCadgfDocument(p).value.entities[0].circle;
  assert.deepEqual(Object.keys(circle).sort(), ['c', 'r']);
});

test('entity color: invalid dropped with diagnostic, hex coerced to integer', () => {
  const bad = proj({ entities: [{ id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]], color: 'red' }] });
  const resBad = deriveCadgfDocument(bad);
  assert.equal('color' in resBad.value.entities[0], false);
  assert.ok(resBad.diagnostics.some((d) => d.code === 'ENTITY_FIELD_DROPPED'));

  const good = proj({ entities: [{ id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]], color: '#ff0000' }] });
  assert.equal(deriveCadgfDocument(good).value.entities[0].color, 0xff0000);
});

test('a foreign geometry field on a modeled entity is dropped with a diagnostic', () => {
  const p = proj({ entities: [{ id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]], circle: { c: [0, 0], r: 1 } }] });
  const res = deriveCadgfDocument(p);
  assert.equal('circle' in res.value.entities[0], false);
  assert.ok(res.value.entities[0].line, 'kept its own line geometry');
  assert.ok(res.diagnostics.some((d) => d.code === 'FOREIGN_GEOMETRY_DROPPED'));
});

test('a known typed entity field with the wrong type is dropped, not emitted (P1a)', () => {
  const p = proj({
    entities: [{
      id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]],
      line_type_scale: 'bad', text_halign: 1.5, attribute_invisible: 'yes',
    }],
  });
  const res = deriveCadgfDocument(p);
  const e = res.value.entities[0];
  assert.equal('line_type_scale' in e, false); // schema wants number
  assert.equal('text_halign' in e, false); // schema wants integer
  assert.equal('attribute_invisible' in e, false); // schema wants boolean
  assert.ok(res.diagnostics.some((d) => d.code === 'ENTITY_FIELD_DROPPED'));
});

test('valid known typed fields and truly-unknown fields are both kept', () => {
  const p = proj({
    entities: [{
      id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]],
      line_type_scale: 2.5, line_type: 'DASHED', myCustom: { anything: true },
    }],
  });
  const e = deriveCadgfDocument(p).value.entities[0];
  assert.equal(e.line_type_scale, 2.5);
  assert.equal(e.line_type, 'DASHED');
  assert.deepEqual(e.myCustom, { anything: true }); // unknown -> passthrough (additionalProperties:true)
});

test('passthrough entity optional fields are cleansed too (P1b)', () => {
  const p = proj({
    entities: [{ id: 'e1', kind: 'line', layerId: 0, cadgfId: 1, line: [[0, 0], [1, 1]] }],
    resources: {
      cadgfPassthrough: {
        document: {},
        entities: [{ id: 9, type: 5, layer_id: 0, name: '', ellipse: { c: [0, 0], rx: 2, ry: 1, rot: 0, a0: 0, a1: 6 }, line_weight: 'bad' }],
      },
    },
  });
  const res = deriveCadgfDocument(p);
  const pe = res.value.entities.find((e) => e.id === 9);
  assert.ok(pe.ellipse, 'valid passthrough geometry kept');
  assert.equal('line_weight' in pe, false, 'bad passthrough scalar dropped');
  assert.ok(res.diagnostics.some((d) => d.code === 'PASSTHROUGH_FIELD_DROPPED'));
});

test('passthrough entity with malformed geometry drops the field but keeps the entity', () => {
  const p = proj({
    entities: [{ id: 'e1', kind: 'line', layerId: 0, cadgfId: 1, line: [[0, 0], [1, 1]] }],
    resources: {
      cadgfPassthrough: { document: {}, entities: [{ id: 9, type: 5, layer_id: 0, name: 'kept', ellipse: 'not-an-ellipse' }] },
    },
  });
  const res = deriveCadgfDocument(p);
  const pe = res.value.entities.find((e) => e.id === 9);
  assert.ok(pe, 'entity kept despite bad optional geometry');
  assert.equal('ellipse' in pe, false);
  assert.equal(pe.name, 'kept');
  assert.ok(res.diagnostics.some((d) => d.code === 'PASSTHROUGH_FIELD_DROPPED'));
});

test('layer line_weight rejects NaN/Infinity (P2a)', () => {
  const p = proj({ layers: [{ id: 0, name: '0', line_weight: NaN }, { id: 1, name: 'L', line_weight: 0.5 }] });
  const layers = deriveCadgfDocument(p).value.layers;
  assert.equal('line_weight' in layers.find((l) => l.id === 0), false);
  assert.equal(layers.find((l) => l.id === 1).line_weight, 0.5);
});
