import test from 'node:test';
import assert from 'node:assert/strict';
import { createProjectModel } from '../project/index.js';
import { deriveCadgfDocument, importProjectFromCadgfDocument } from '../scene/index.js';

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

// --- import (lenient) direction ---

function unitDoc(unitName, unitScale) {
  return { metadata: { unit_name: unitName }, settings: { unit_scale: unitScale }, layers: [], entities: [] };
}

test('import resolves units by unit_name (case-insensitive)', () => {
  for (const [name, unit] of [['mm', 'mm'], ['CM', 'cm'], ['M', 'm'], ['in', 'in'], ['ft', 'ft']]) {
    const res = importProjectFromCadgfDocument(unitDoc(name, 1));
    assert.equal(res.value.project.units, unit, `unit_name ${name}`);
  }
});

test('import falls back to unit_scale when unit_name is unknown', () => {
  const res = importProjectFromCadgfDocument(unitDoc('Millimeters', 25.4));
  assert.equal(res.value.project.units, 'in'); // 25.4 mm/unit -> inches
});

test('import falls back to mm + diagnostic when neither name nor scale is recognized', () => {
  const res = importProjectFromCadgfDocument(unitDoc('league', 999));
  assert.equal(res.value.project.units, 'mm');
  assert.ok(res.diagnostics.some((d) => d.code === 'UNIT_FALLBACK'));
});
