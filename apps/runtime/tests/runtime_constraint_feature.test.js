import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeConstraintSet, validateV1ConstraintSet, V1_CONSTRAINT_VOCABULARY, ENTITY_ROLES } from '../constraint/index.js';
import { normalizeFeatureList, buildRebuildPlan } from '../feature/index.js';
import { ENTITY_POINTS } from '../solver/adapter.js';

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

// ---- validateV1ConstraintSet — the v1 semantic vocabulary (Tier 1 / §D1b) ----

const ENTS = [
  { id: 'L1', kind: 'line' },
  { id: 'L2', kind: 'line' },
  { id: 'P1', kind: 'point' },
  { id: 'C1', kind: 'circle' },
  { id: 'T1', kind: 'text' }, // not a solvable kind
];
const semref = (entity, at) => ({ entity, at });

test('validateV1ConstraintSet keeps well-formed constraints (legal type/arity/value/roles)', () => {
  const res = validateV1ConstraintSet([
    { id: 'h', type: 'horizontal', refs: [semref('L1', 'start'), semref('L1', 'end')] },
    { id: 'd', type: 'distance', value: 10, refs: [semref('P1', 'self'), semref('L1', 'start')] },
    { id: 'pp', type: 'parallel', refs: [semref('L1', 'start'), semref('L1', 'end'), semref('L2', 'start'), semref('L2', 'end')] },
  ], ENTS);
  assert.equal(res.ok, true);
  assert.deepEqual(res.value.map((c) => c.id), ['h', 'd', 'pp']);
  assert.deepEqual(res.diagnostics, []);
});

test('validateV1ConstraintSet drops unsupported types with CONSTRAINT_NOT_SUPPORTED (info)', () => {
  const res = validateV1ConstraintSet([{ id: 'e', type: 'equal', refs: [semref('L1', 'start'), semref('L1', 'end')] }], ENTS);
  assert.deepEqual(res.value, []);
  const d = res.diagnostics.find((x) => x.code === 'CONSTRAINT_NOT_SUPPORTED');
  assert.ok(d && d.level === 'info');
});

test('validateV1ConstraintSet drops a wrong ref count with CONSTRAINT_BAD_ARITY (warn)', () => {
  const res = validateV1ConstraintSet([{ id: 'pp', type: 'parallel', refs: [semref('L1', 'start'), semref('L1', 'end')] }], ENTS);
  assert.deepEqual(res.value, []);
  const d = res.diagnostics.find((x) => x.code === 'CONSTRAINT_BAD_ARITY');
  assert.ok(d && d.level === 'warn');
});

test('validateV1ConstraintSet drops a value-type missing its value with CONSTRAINT_MISSING_VALUE (warn)', () => {
  const res = validateV1ConstraintSet([{ id: 'd', type: 'distance', refs: [semref('P1', 'self'), semref('L1', 'start')] }], ENTS);
  assert.deepEqual(res.value, []);
  const d = res.diagnostics.find((x) => x.code === 'CONSTRAINT_MISSING_VALUE');
  assert.ok(d && d.level === 'warn');
});

test('validateV1ConstraintSet drops a NON-value type carrying a value with CONSTRAINT_UNEXPECTED_VALUE (warn)', () => {
  // horizontal takes no value; a stray value must be surfaced, not silently dropped
  // downstream by the adapter (which emits no value for a non-value type).
  const res = validateV1ConstraintSet([{ id: 'h', type: 'horizontal', value: 123, refs: [semref('L1', 'start'), semref('L1', 'end')] }], ENTS);
  assert.deepEqual(res.value, []);
  const d = res.diagnostics.find((x) => x.code === 'CONSTRAINT_UNEXPECTED_VALUE');
  assert.ok(d && d.level === 'warn');
  // value: null / undefined is "absent" (not "provided") — a non-value type stays valid
  assert.deepEqual(
    validateV1ConstraintSet([{ id: 'h2', type: 'horizontal', value: null, refs: [semref('L1', 'start'), semref('L1', 'end')] }], ENTS).value.map((c) => c.id),
    ['h2'],
  );
});

test('validateV1ConstraintSet drops an illegal role for the entity kind — exactly one CONSTRAINT_REF_UNRESOLVED', () => {
  // a line exposes start/end, never center
  const res = validateV1ConstraintSet([{ id: 'h', type: 'horizontal', refs: [semref('L1', 'center'), semref('L1', 'end')] }], ENTS);
  assert.deepEqual(res.value, []);
  const refDiags = res.diagnostics.filter((x) => x.code === 'CONSTRAINT_REF_UNRESOLVED');
  assert.equal(refDiags.length, 1);
  assert.equal(refDiags[0].level, 'warn');
});

test('validateV1ConstraintSet drops a ref to an unknown / non-solvable entity with CONSTRAINT_REF_UNRESOLVED', () => {
  const unknown = validateV1ConstraintSet([{ id: 'h', type: 'horizontal', refs: [semref('ZZ', 'start'), semref('L1', 'end')] }], ENTS);
  assert.deepEqual(unknown.value, []);
  assert.ok(unknown.diagnostics.some((x) => x.code === 'CONSTRAINT_REF_UNRESOLVED'));
  const text = validateV1ConstraintSet([{ id: 'h2', type: 'horizontal', refs: [semref('T1', 'start'), semref('T1', 'end')] }], ENTS);
  assert.deepEqual(text.value, []);
  assert.ok(text.diagnostics.some((x) => x.code === 'CONSTRAINT_REF_UNRESOLVED'));
});

test('validateV1ConstraintSet treats missing input as an empty set and rejects non-arrays', () => {
  assert.deepEqual(validateV1ConstraintSet(undefined, ENTS).value, []);
  assert.deepEqual(validateV1ConstraintSet(null, ENTS).value, []);
  assert.equal(validateV1ConstraintSet({ not: 'array' }, ENTS).ok, false);
});

test('the v1 vocabulary is exactly the 6 supported types (equal/coincident/concentric excluded)', () => {
  assert.deepEqual(
    Object.keys(V1_CONSTRAINT_VOCABULARY).sort(),
    ['angle', 'distance', 'horizontal', 'parallel', 'perpendicular', 'vertical'],
  );
});

// ENTITY_ROLES (constraint/, semantic) MUST mirror ENTITY_POINTS (adapter, what it
// actually mints). If they drift, validateV1ConstraintSet would silently drop
// legitimate constraints (or admit unmintable ones). This makes the sync enforced.
test('ENTITY_ROLES mirrors the adapter ENTITY_POINTS exactly (kinds + roles in order)', () => {
  assert.deepEqual(Object.keys(ENTITY_ROLES).sort(), Object.keys(ENTITY_POINTS).sort());
  for (const kind of Object.keys(ENTITY_ROLES)) {
    assert.deepEqual(ENTITY_ROLES[kind], ENTITY_POINTS[kind].map((r) => r.role), `roles for ${kind} must match`);
  }
});
