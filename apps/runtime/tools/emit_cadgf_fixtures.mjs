#!/usr/bin/env node
// Derive representative CADGF Documents from VEMCAD-PROJECTs and write them to a
// directory, for the independent schema acceptance step (S6). A fixed clock
// keeps output reproducible. The malformed "edge" project proves derive cleanses
// to schema-valid output; the round-trip exercises import + re-derive.
//
// Usage: emit_cadgf_fixtures.mjs [outDir]   (defaults to a fresh temp dir)
// Prints the output directory and one line per fixture; exits non-zero if any
// derive fails.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createProjectModel } from '../project/index.js';
import { deriveCadgfDocument, importProjectFromCadgfDocument } from '../scene/index.js';

const CLOCK = { now: () => '2026-05-25T00:00:00.000Z' };

// Rich, well-formed project covering every modeled kind + a passthrough ellipse.
function richProject() {
  const base = createProjectModel({
    id: 'fixture-rich', name: 'Rich Fixture', units: 'in',
    createdAt: '2026-01-01T00:00:00.000Z', modifiedAt: '2026-01-02T00:00:00.000Z',
  }).value;
  return {
    ...base,
    layers: [{ id: 0, name: '0' }, { id: 1, name: 'Outline', color: '#202020' }],
    entities: [
      { id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [100, 0]], color: '#ff0000' },
      { id: 'e2', kind: 'circle', layerId: 1, circle: { c: [50, 25], r: 10 } },
      { id: 'e3', kind: 'arc', layerId: 1, arc: { c: [0, 0], r: 5, a0: 0, a1: 1.5, cw: 0 } },
      { id: 'e4', kind: 'point', layerId: 0, point: [2, 3] },
      { id: 'e5', kind: 'polyline', layerId: 0, polyline: [[0, 0], [1, 0], [1, 1]] },
      { id: 'e6', kind: 'text', layerId: 1, text: { pos: [5, 7], h: 2.5, rot: 0, value: 'hi' } },
    ],
    resources: {
      cadgfPassthrough: {
        document: { metadata: { author: 'Ada' } },
        entities: [{ id: 9, type: 5, layer_id: 1, name: '', ellipse: { c: [0, 0], rx: 2, ry: 1, rot: 0, a0: 0, a1: 6 } }],
      },
    },
  };
}

// Edge project: every field deliberately malformed; derive MUST cleanse it into
// a schema-valid document (the whole point of the acceptance check).
function edgeProject() {
  return {
    header: { format: 'VEMCAD-PROJECT', version: 1 },
    project: { id: 'fixture-edge', name: 'Edge Fixture', units: 'mm', createdAt: '2026-01-01T00:00:00.000Z', modifiedAt: '2026-01-02T00:00:00.000Z' },
    layers: [{ id: 0, name: '0', line_weight: NaN }, { id: 1, name: 'L', color: '#202020' }],
    entities: [
      { id: 'e1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]], line_type_scale: 'bad', color: 'red', foo: { x: 1 } },
      { id: 'e2', kind: 'text', layerId: 1, text: { pos: [0, 0], h: 2.5, rot: 0, value: 'hi' }, color_aci: 999 },
    ],
    constraints: [],
    features: [],
    resources: {
      cadgfPassthrough: {
        document: { schema_version: 1, schema_migrated_at: 123, metadata: { author: 42, meta: { bad: 7 } } },
        entities: [{ id: 9, type: 6, layer_id: 0, name: '', spline: 'broken' }],
      },
    },
    meta: {},
  };
}

const outDir = process.argv[2] || fs.mkdtempSync(path.join(os.tmpdir(), 'vemcad-cadgf-'));
fs.mkdirSync(outDir, { recursive: true });

const fixtures = {
  'rich.cadgf.json': deriveCadgfDocument(richProject(), { clock: CLOCK }),
  'edge.cadgf.json': deriveCadgfDocument(edgeProject(), { clock: CLOCK }),
};
// Round-trip: derive -> import -> derive, validating the re-derived document.
const roundTrip = fixtures['rich.cadgf.json'].ok
  ? deriveCadgfDocument(importProjectFromCadgfDocument(fixtures['rich.cadgf.json'].value, { clock: CLOCK }).value, { clock: CLOCK })
  : { ok: false, error: 'rich derive failed' };
fixtures['roundtrip.cadgf.json'] = roundTrip;

console.log(`output dir: ${outDir}`);
let failed = 0;
for (const [name, result] of Object.entries(fixtures)) {
  if (!result.ok) {
    console.error(`derive failed for ${name}: ${result.error}`);
    failed += 1;
    continue;
  }
  fs.writeFileSync(path.join(outDir, name), `${JSON.stringify(result.value, null, 2)}\n`);
  console.log(`wrote ${name} (${result.diagnostics.length} diagnostic(s))`);
}

process.exit(failed ? 1 : 0);
