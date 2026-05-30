const FIXED_AT = '2026-05-25T00:00:00.000Z';

function baseProject({ id, name, entities, constraints }) {
  return {
    header: { format: 'VEMCAD-PROJECT', version: 1 },
    project: { id, name, units: 'mm', createdAt: FIXED_AT, modifiedAt: FIXED_AT },
    layers: [{ id: 0, name: 'Default' }],
    entities,
    constraints,
    features: [],
    resources: { cadgfPassthrough: { document: {}, entities: [] } },
    meta: {},
  };
}

export const SOLVE_WORKBENCH_DEMOS = Object.freeze({
  solvableLine: baseProject({
    id: 'demo-solvable-line',
    name: 'Solvable line',
    entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 3], [10, 5]] }],
    constraints: [
      { id: 'c-horizontal', type: 'horizontal', refs: [{ entity: 'L1', at: 'start' }, { entity: 'L1', at: 'end' }] },
      { id: 'c-distance', type: 'distance', refs: [{ entity: 'L1', at: 'start' }, { entity: 'L1', at: 'end' }], value: 10 },
    ],
  }),
  conflictingLine: baseProject({
    id: 'demo-conflicting-line',
    name: 'Conflicting line',
    entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 0], [10, 0]] }],
    constraints: [
      { id: 'c-horizontal', type: 'horizontal', refs: [{ entity: 'L1', at: 'start' }, { entity: 'L1', at: 'end' }] },
      { id: 'c-vertical', type: 'vertical', refs: [{ entity: 'L1', at: 'start' }, { entity: 'L1', at: 'end' }] },
      { id: 'c-distance', type: 'distance', refs: [{ entity: 'L1', at: 'start' }, { entity: 'L1', at: 'end' }], value: 10 },
    ],
  }),
  passthroughUnsupported: baseProject({
    id: 'demo-passthrough-unsupported',
    name: 'Passthrough unsupported',
    entities: [
      { id: 'T1', kind: 'text', layerId: 0, text: { p: [0, 0], value: 'note', height: 2 } },
      { id: 'P1', kind: 'polyline', layerId: 0, polyline: [[0, 0], [2, 0], [2, 2]] },
    ],
    constraints: [],
  }),
});
