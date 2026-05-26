#!/usr/bin/env node
// Real /solve HTTP acceptance (Tier 3): start the server with the REAL solve_cli +
// solver binary and assert the end-to-end HTTP contract over the wire. Needs
// VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH. NOT part of node --test.
import { createSolveServer } from '../server.mjs';
import { createProjectModel } from '../../../apps/runtime/project/index.js';

const FIXED = '2026-05-25T00:00:00.000Z';
const project = (entities, constraints, units = 'mm') => ({
  ...createProjectModel({ id: 'http-acc', name: 'http-acc', units, createdAt: FIXED, modifiedAt: FIXED }).value,
  entities,
  constraints,
});
const line = (id, a, b) => ({ id, kind: 'line', layerId: 0, line: [a, b] });
const point = (id, xy) => ({ id, kind: 'point', layerId: 0, point: xy });
const endpoints = (id) => [{ entity: id, at: 'start' }, { entity: id, at: 'end' }];

const server = createSolveServer();
await new Promise((resolve) => server.listen(0, resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const post = (body) => fetch(`${base}/solve`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: typeof body === 'string' ? body : JSON.stringify(body),
});

let failed = 0;
async function expect(name, res, status, check) {
  const body = await res.json().catch(() => null);
  const ok = res.status === status && (!check || check(body));
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name} (got status ${res.status})`);
  if (!ok) failed += 1;
}

await expect(
  'solved -> 200',
  await post(project([line('L1', [0, 0], [10, 5])], [{ id: 'h', type: 'horizontal', refs: endpoints('L1') }])),
  200,
  (b) => b?.ok === true && b?.value?.solve?.ok === true,
);
await expect(
  'conflict -> 422 SOLVE_UNSATISFIED',
  await post(project([point('P1', [0, 0]), point('P2', [3, 0])], [
    { id: 'd10', type: 'distance', value: 10, refs: [{ entity: 'P1', at: 'self' }, { entity: 'P2', at: 'self' }] },
    { id: 'd20', type: 'distance', value: 20, refs: [{ entity: 'P1', at: 'self' }, { entity: 'P2', at: 'self' }] },
  ])),
  422,
  (b) => b?.error_code === 'SOLVE_UNSATISFIED' && !!b?.analysis,
);
await expect(
  'bad unit -> 400',
  await post(createProjectModel({ id: 'u', name: 'u', units: 'league', createdAt: FIXED, modifiedAt: FIXED }).value),
  400,
);
await expect('malformed body -> 400', await post('not json at all'), 400);
await expect('health -> 200', await fetch(`${base}/health`), 200, (b) => b?.ok === true);

server.closeAllConnections?.();
server.close();
console.log(`/solve http acceptance: ${5 - failed}/5 ok`);
process.exit(failed ? 1 : 0);
