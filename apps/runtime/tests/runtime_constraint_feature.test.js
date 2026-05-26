import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeConstraintSet } from '../constraint/index.js';
import { normalizeFeatureList, buildRebuildPlan } from '../feature/index.js';

test('normalizeConstraintSet sorts by id and leaves diagnostics empty (no solve in v0)', () => {
  const res = normalizeConstraintSet([{ id: 'c2', kind: 'parallel' }, { id: 'c1', kind: 'coincident' }]);
  assert.equal(res.ok, true);
  assert.deepEqual(res.value.map((c) => c.id), ['c1', 'c2']);
  assert.deepEqual(res.diagnostics, []);
});

test('normalizeConstraintSet treats missing input as an empty set', () => {
  assert.deepEqual(normalizeConstraintSet(undefined).value, []);
  assert.deepEqual(normalizeConstraintSet(null).value, []);
});

test('normalizeConstraintSet rejects malformed sets', () => {
  assert.equal(normalizeConstraintSet({ not: 'an array' }).ok, false);
  assert.equal(normalizeConstraintSet([{ kind: 'noId' }]).ok, false);
  assert.equal(normalizeConstraintSet([{ id: 'c1' }, { id: 'c1' }]).ok, false);
  assert.equal(normalizeConstraintSet([{ kind: 'noId' }]).error_code, 'INVALID_CONSTRAINT_SET');
});

test('normalizeFeatureList sorts by id', () => {
  const res = normalizeFeatureList([{ id: 'f2' }, { id: 'f1' }]);
  assert.equal(res.ok, true);
  assert.deepEqual(res.value.map((f) => f.id), ['f1', 'f2']);
});

test('buildRebuildPlan returns a deterministic no-op plan in stable order', () => {
  const res = buildRebuildPlan([{ id: 'f2' }, { id: 'f1' }, { id: 'f3' }]);
  assert.equal(res.ok, true);
  assert.deepEqual(res.value.order, ['f1', 'f2', 'f3']);
  assert.deepEqual(res.value.steps, []);
  assert.equal(res.value.noop, true);
});

test('buildRebuildPlan propagates validation failure', () => {
  const res = buildRebuildPlan([{ noId: true }]);
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'INVALID_FEATURE_LIST');
});

test('numeric and string ids follow the shared ordering rule', () => {
  // numeric ids sort numerically; consistent with the project module.
  assert.deepEqual(normalizeFeatureList([{ id: 10 }, { id: 2 }, { id: 1 }]).value.map((f) => f.id), [1, 2, 10]);
  assert.deepEqual(
    normalizeConstraintSet([{ id: 'c10' }, { id: 'c2' }, { id: 'c1' }]).value.map((c) => c.id),
    ['c1', 'c10', 'c2'],
  );
});
