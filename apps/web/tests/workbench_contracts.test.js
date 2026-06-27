import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// VemCAD product-layer workbench contract guard (P2 / S1).
//
// Pins the stable facade surface declared in
// apps/web/workbench/contracts/index.js and documented in
// docs/VEMCAD_APP_P2_WORKBENCH_SPLIT_TASKBOOK_20260626.md §2. The later P2
// slices (S3+) extract large CADGameFusion command/preview modules behind these
// facades; this guard fails fast if a re-export is renamed or dropped, or if the
// documented contract list silently drifts from the actual exports.
//
// Lives in apps/web/tests so it runs under `npm run test:web` (the
// submodule-aware web-integration job). The barrel transitively re-exports from
// deps/cadgamefusion, so it is intentionally NOT part of the no-submodule core
// `npm test` glob.

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..', '..');
const contractsUrl = pathToFileURL(
  path.join(repoRoot, 'apps/web/workbench/contracts/index.js'),
).href;

const EXPECTED_STABLE_EXPORTS = [
  'registerCadCommands(commandBus, context)',
  'computeRotatePayload(center, referencePoint, targetPoint)',
  'computeScalePayload(center, referencePoint, targetPoint)',
  'bootstrapCadWorkspace({ params })',
  'createSolveWorkbenchController({ endpoint, fetchImpl })',
  'createSolveWorkbenchPanel({ root, project, controller })',
  'mountSolveWorkbenchDemo({ root, appBridge })',
  'renderCadgfPreviewCanvas({ root, cadgfDocument })',
];

const EXPECTED_GLOBAL_CONTRACTS = [
  'window.__vemcadApp.switchToEditor(documentJson)',
  'window.__vemcadApp.mountSolvePanel(root, { project, controller })',
  'window.__cadDebug',
];

// Mirror the repo idiom (web_bootstrap_entry.test.js): evaluate the barrel and
// its transitive CADGameFusion re-exports at call time via dynamic import, so a
// broken module graph surfaces as a failing assertion rather than a
// collection-time crash. The cache-buster keeps each load independent.
async function loadContracts() {
  return import(`${contractsUrl}?workbench-contracts`);
}

function exportName(signature) {
  return signature.split('(')[0].trim();
}

test('WORKBENCH_STABLE_EXPORTS is frozen and matches the documented contract surface', async () => {
  const { WORKBENCH_STABLE_EXPORTS } = await loadContracts();
  assert.ok(Array.isArray(WORKBENCH_STABLE_EXPORTS), 'WORKBENCH_STABLE_EXPORTS must be an array');
  assert.ok(Object.isFrozen(WORKBENCH_STABLE_EXPORTS), 'WORKBENCH_STABLE_EXPORTS must be frozen');
  assert.deepEqual([...WORKBENCH_STABLE_EXPORTS], EXPECTED_STABLE_EXPORTS);
});

test('WORKBENCH_GLOBAL_CONTRACTS is frozen and matches the documented globals', async () => {
  const { WORKBENCH_GLOBAL_CONTRACTS } = await loadContracts();
  assert.ok(Object.isFrozen(WORKBENCH_GLOBAL_CONTRACTS), 'WORKBENCH_GLOBAL_CONTRACTS must be frozen');
  assert.deepEqual([...WORKBENCH_GLOBAL_CONTRACTS], EXPECTED_GLOBAL_CONTRACTS);
});

// Load-bearing anti-drift guard for S3+ extraction: every documented stable
// export must resolve to a real callable on the barrel. A renamed or dropped
// re-export (e.g. when command_registry.js helpers move to commands/shared/*)
// fails here instead of silently breaking the product facade.
test('every documented stable export resolves to a callable on the barrel', async () => {
  const contracts = await loadContracts();
  for (const signature of EXPECTED_STABLE_EXPORTS) {
    const name = exportName(signature);
    assert.equal(
      typeof contracts[name],
      'function',
      `${name} must be exported as a function from apps/web/workbench/contracts/index.js`,
    );
  }
});
