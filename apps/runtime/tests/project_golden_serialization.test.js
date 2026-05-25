import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { serializeProjectModel, parseProjectModel } from '../project/index.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const GOLDEN_PATH = path.join(__dirname, 'fixtures', 'project_golden_v1.json');

const FIXED_CREATED = '2026-01-02T03:04:05.000Z';
const FIXED_MODIFIED = '2026-03-04T05:06:07.000Z';

// A representative VEMCAD-PROJECT covering every collection. Keys and arrays are
// deliberately given OUT of canonical order so the golden proves serialization
// imposes the canonical form (stable id order + sorted keys), not just echoes
// the input. Regenerate after an INTENTIONAL format change with:
//   UPDATE_GOLDEN=1 node --test apps/runtime/tests/project_golden_serialization.test.js
function goldenInput() {
  return {
    header: { format: 'VEMCAD-PROJECT', version: 1 },
    project: {
      units: 'mm',
      name: 'Golden Sample',
      id: 'proj-golden-001',
      modifiedAt: FIXED_MODIFIED,
      createdAt: FIXED_CREATED,
    },
    layers: [
      { id: 2, name: 'Dimensions', color: '#ff0000', visible: true },
      { id: 0, name: '0' },
      { id: 1, name: 'Outline', color: '#202020', visible: true },
    ],
    entities: [
      { id: 'e3', kind: 'text', layerId: 1, text: 'D20', x: 5, y: 7, height: 2.5 },
      { id: 'e1', kind: 'line', layerId: 0, a: [0, 0], b: [100, 0] },
      { id: 'e2', kind: 'circle', layerId: 1, center: [50, 25], radius: 10 },
    ],
    constraints: [
      { id: 'c2', kind: 'distance', between: ['e1', 'e2'], value: 25 },
      { id: 'c1', kind: 'coincident', of: ['e1', 'e2'] },
    ],
    features: [
      { id: 'f2', kind: 'noop', label: 'second' },
      { id: 'f1', kind: 'noop', label: 'first' },
    ],
    resources: {
      cadgfPassthrough: {
        document: { schema_version: 1, cadgf_version: '0.4.0', feature_flags: { earcut: true, clipper2: true } },
        entities: [
          { cadgfId: 7, type: 11, note: 'ellipse passthrough' },
          { cadgfId: 3, type: 9, note: 'spline passthrough' },
        ],
      },
    },
    meta: { gamma: '3', alpha: '1', beta: '2' },
  };
}

test('serialized golden project matches the committed golden file', () => {
  const result = serializeProjectModel(goldenInput());
  assert.equal(result.ok, true);

  if (process.env.UPDATE_GOLDEN) {
    fs.mkdirSync(path.dirname(GOLDEN_PATH), { recursive: true });
    fs.writeFileSync(GOLDEN_PATH, result.value);
  }

  const golden = fs.readFileSync(GOLDEN_PATH, 'utf8');
  assert.equal(result.value, golden);
});

test('the golden file itself round-trips (parse -> serialize) to identical bytes', () => {
  const golden = fs.readFileSync(GOLDEN_PATH, 'utf8');
  const parsed = parseProjectModel(golden);
  assert.equal(parsed.ok, true);
  const reserialized = serializeProjectModel(parsed.value);
  assert.equal(reserialized.ok, true);
  assert.equal(reserialized.value, golden);
});

test('a shuffled but equivalent input still serializes to the golden bytes', () => {
  const input = goldenInput();
  input.layers.reverse();
  input.entities.reverse();
  input.constraints.reverse();
  input.features.reverse();
  input.resources.cadgfPassthrough.entities.reverse();
  input.meta = { beta: '2', gamma: '3', alpha: '1' };

  const result = serializeProjectModel(input);
  assert.equal(result.ok, true);
  const golden = fs.readFileSync(GOLDEN_PATH, 'utf8');
  assert.equal(result.value, golden);
});
