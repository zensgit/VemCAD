import test from 'node:test';
import assert from 'node:assert/strict';
import { createProjectModel } from '../project/index.js';
import { deriveCadgfDocument } from '../scene/index.js';

const FIXED = '2026-05-25T00:00:00.000Z';

function projectWithUnit(units) {
  return createProjectModel({ id: 'u', name: 'U', units, createdAt: FIXED, modifiedAt: FIXED }).value;
}

// --- derive (export) direction: strict unit table ---
// (S5 will add the lenient import direction to this file.)

test('derive maps each supported unit to unit_name + unit_scale (mm per unit)', () => {
  const cases = [
    ['mm', 1],
    ['cm', 10],
    ['m', 1000],
    ['in', 25.4],
    ['ft', 304.8],
  ];
  for (const [unit, scale] of cases) {
    const res = deriveCadgfDocument(projectWithUnit(unit));
    assert.equal(res.ok, true, `${unit} should derive`);
    assert.equal(res.value.metadata.unit_name, unit);
    assert.equal(res.value.settings.unit_scale, scale);
  }
});

test('derive strictly rejects an unknown project unit', () => {
  const res = deriveCadgfDocument(projectWithUnit('league'));
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'UNSUPPORTED_PROJECT_UNIT');
});
