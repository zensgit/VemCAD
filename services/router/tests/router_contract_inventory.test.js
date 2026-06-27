import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CONTRACT_PATH = resolve(__dirname, '../CONTRACT.md');

const STABLE_ROUTES = [
  'GET /health',
  'POST /convert',
  'GET /status/{task_id}',
  'GET /manifest/{task_id}',
  'GET /history',
  'GET /projects',
  'GET /projects/{project_id}/documents',
  'GET /documents/{document_id}/versions',
];

test('services/router contract inventories the stable reference-router routes', () => {
  const text = readFileSync(CONTRACT_PATH, 'utf8');
  for (const route of STABLE_ROUTES) {
    assert.ok(text.includes(`- \`${route}\``), `missing route inventory entry: ${route}`);
  }
});

test('services/router contract does not drift to stale job/artifact route names', () => {
  const text = readFileSync(CONTRACT_PATH, 'utf8');
  assert.doesNotMatch(text, /`GET \/jobs\/\{job_id\}`/);
  assert.doesNotMatch(text, /`GET \/artifacts\/\{artifact_id\}`/);
});
