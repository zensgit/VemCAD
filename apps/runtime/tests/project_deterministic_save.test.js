import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createProjectModel,
  normalizeProjectModel,
  serializeProjectModel,
} from '../project/index.js';

const FIXED = '2026-01-02T03:04:05.000Z';

function projectWith(overrides = {}) {
  const base = createProjectModel({ id: 'p-det', name: 'Det', units: 'mm', createdAt: FIXED, modifiedAt: FIXED });
  assert.equal(base.ok, true);
  return { ...base.value, ...overrides };
}

test('repeated serialization yields byte-identical output', () => {
  const p = projectWith();
  const a = serializeProjectModel(p);
  const b = serializeProjectModel(p);
  assert.equal(a.ok, true);
  assert.equal(b.ok, true);
  assert.equal(a.value, b.value);
});

test('shuffled input collections + keys normalize to identical bytes', () => {
  const ordered = projectWith({
    layers: [{ id: 0, name: '0' }, { id: 1, name: 'L1' }, { id: 2, name: 'L2' }],
    entities: [{ id: 'e1', kind: 'line' }, { id: 'e2', kind: 'circle' }, { id: 'e3', kind: 'arc' }],
    meta: { alpha: '1', beta: '2', gamma: '3' },
  });
  const shuffled = projectWith({
    layers: [{ id: 2, name: 'L2' }, { id: 0, name: '0' }, { id: 1, name: 'L1' }],
    entities: [{ kind: 'circle', id: 'e2' }, { kind: 'arc', id: 'e3' }, { kind: 'line', id: 'e1' }],
    meta: { gamma: '3', alpha: '1', beta: '2' },
  });

  const sOrdered = serializeProjectModel(ordered);
  const sShuffled = serializeProjectModel(shuffled);
  assert.equal(sOrdered.ok, true);
  assert.equal(sShuffled.ok, true);
  assert.equal(sShuffled.value, sOrdered.value);
});

test('normalize and serialize never mutate timestamps', () => {
  const p = projectWith();
  const created = p.project.createdAt;
  const modified = p.project.modifiedAt;

  const norm = normalizeProjectModel(p);
  assert.equal(norm.ok, true);
  assert.equal(norm.value.project.createdAt, created);
  assert.equal(norm.value.project.modifiedAt, modified);

  // input must not be mutated by normalize
  assert.equal(p.project.createdAt, created);
  assert.equal(p.project.modifiedAt, modified);

  // serialize preserves the timestamps verbatim
  const text = serializeProjectModel(p);
  assert.equal(text.ok, true);
  assert.ok(text.value.includes(created));
});

test('all record collections serialize in stable id order', () => {
  const p = projectWith({
    layers: [{ id: 2, name: 'b' }, { id: 0, name: '0' }, { id: 10, name: 'c' }, { id: 1, name: 'a' }],
    entities: [{ id: 'e2' }, { id: 'e10' }, { id: 'e1' }],
    constraints: [{ id: 'c2' }, { id: 'c1' }],
    features: [{ id: 'f2' }, { id: 'f1' }],
  });
  const norm = normalizeProjectModel(p);
  assert.equal(norm.ok, true);

  // numeric ids sort numerically; string ids sort by code-unit order
  assert.deepEqual(norm.value.layers.map((l) => l.id), [0, 1, 2, 10]);
  assert.deepEqual(norm.value.entities.map((e) => e.id), ['e1', 'e10', 'e2']);
  assert.deepEqual(norm.value.constraints.map((c) => c.id), ['c1', 'c2']);
  assert.deepEqual(norm.value.features.map((f) => f.id), ['f1', 'f2']);
});

test('passthrough entities are deterministically ordered', () => {
  const a = projectWith({
    resources: {
      cadgfPassthrough: {
        document: {},
        entities: [{ cadgfId: 3, kind: 'hatch' }, { cadgfId: 1, kind: 'spline' }, { cadgfId: 2, kind: 'ellipse' }],
      },
    },
  });
  const b = projectWith({
    resources: {
      cadgfPassthrough: {
        document: {},
        entities: [{ kind: 'ellipse', cadgfId: 2 }, { kind: 'hatch', cadgfId: 3 }, { kind: 'spline', cadgfId: 1 }],
      },
    },
  });
  const sa = serializeProjectModel(a);
  const sb = serializeProjectModel(b);
  assert.equal(sa.ok, true);
  assert.equal(sb.ok, true);
  assert.equal(sa.value, sb.value);

  const norm = normalizeProjectModel(a).value;
  assert.deepEqual(norm.resources.cadgfPassthrough.entities.map((e) => e.cadgfId), [1, 2, 3]);
});

// P2 — duplicate/missing ids make ordering ambiguous (stable sort keeps input
// order), so Project-owned collections must reject them rather than serialize
// two equivalent inputs to different bytes.
test('duplicate ids in a Project-owned collection are rejected', () => {
  const dup = projectWith({ entities: [{ id: 'e1', kind: 'line' }, { id: 'e1', kind: 'circle' }] });
  assert.equal(normalizeProjectModel(dup).ok, false);
  const res = serializeProjectModel(dup);
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_PROJECT_FORMAT');
});

test('records without a usable id are rejected', () => {
  const noId = projectWith({ entities: [{ kind: 'line' }] });
  assert.equal(normalizeProjectModel(noId).ok, false);
  assert.equal(serializeProjectModel(noId).ok, false);
});

test('numeric and string ids that collide under ordering are treated as duplicates', () => {
  const collide = projectWith({ layers: [{ id: 0, name: 'a' }, { id: '0', name: 'b' }] });
  assert.equal(serializeProjectModel(collide).ok, false);
});
