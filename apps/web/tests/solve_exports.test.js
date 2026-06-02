import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SOLVE_REPRO_SCHEMA,
  solveEvidenceText,
  projectJsonText,
  reproBundleJsonText,
  filenameForProject,
  filenameForPreviewDocument,
  filenameForSolveResult,
  extractImportedProject,
} from '../shared/solve_exports.js';

test('solveEvidenceText: one fact per line; placeholder without inputs', () => {
  assert.equal(solveEvidenceText(null, null), 'No solve result yet.');
  assert.equal(solveEvidenceText({ ok: true }, null), 'No solve result yet.');
  const text = solveEvidenceText(
    { ok: false },
    { httpStatus: 422, status: 'blocked', errorCode: 'SOLVE_UNSATISFIED', structuralState: 'overconstrained', dofEstimate: 0, conflictGroupCount: 1, redundantConstraintEstimate: 0, iterations: 100, finalError: 1.2, diagnosticCount: 3 },
  );
  assert.equal(text, [
    'ok=false', 'http=422', 'status=blocked', 'error=SOLVE_UNSATISFIED', 'state=overconstrained',
    'dof=0', 'conflicts=1', 'redundant=0', 'iters=100', 'err=1.2', 'diagnostics=3',
  ].join('\n'));
});

test('projectJsonText: pretty JSON with a trailing newline', () => {
  assert.equal(projectJsonText({ a: 1 }), '{\n  "a": 1\n}\n');
});

test('reproBundleJsonText: self-describing bundle (schema + source + project + result + evidence)', () => {
  const bundle = JSON.parse(reproBundleJsonText({
    project: { project: { id: 'demo-line' } },
    solveEnvelope: { ok: true },
    solveEvidence: 'ok=true',
    demoKey: 'solvableLine',
    shareUrl: 'http://x/?mode=solve-demo&demo=solvableLine',
  }));
  assert.equal(bundle.schema, SOLVE_REPRO_SCHEMA);
  assert.equal(bundle.demo, 'solvableLine');
  assert.equal(bundle.share_url, 'http://x/?mode=solve-demo&demo=solvableLine');
  assert.deepEqual(bundle.project, { project: { id: 'demo-line' } });
  assert.deepEqual(bundle.solve_result, { ok: true });
  assert.equal(bundle.solve_evidence, 'ok=true');
  // editor-style use: no share url -> null
  const editorBundle = JSON.parse(reproBundleJsonText({ project: {}, solveEnvelope: { ok: false }, solveEvidence: '', demoKey: 'editor' }));
  assert.equal(editorBundle.demo, 'editor');
  assert.equal(editorBundle.share_url, null);
  assert.equal(editorBundle.solve_evidence, null);
});

test('filename builders: id-based, sanitized, with stable fallbacks', () => {
  assert.equal(filenameForProject({ project: { id: 'My Part/01' } }), 'My-Part-01.vemcad-project.json');
  assert.equal(filenameForProject(null, 'key1'), 'key1.vemcad-project.json');
  assert.equal(filenameForProject(null, null), 'vemcad-project.vemcad-project.json');

  assert.equal(filenameForPreviewDocument({ document_id: 'doc 9' }), 'doc-9.cadgf-document.json');
  assert.equal(filenameForPreviewDocument(null, null), 'vemcad-preview.cadgf-document.json');

  assert.equal(filenameForSolveResult(null, { project: { id: 'P2' } }), 'P2.solve-result.json');
  assert.equal(filenameForSolveResult({ value: { evaluatedView: { project: { id: 'EV3' } } } }, null), 'EV3.solve-result.json');
  assert.equal(filenameForSolveResult(null, null, null), 'vemcad-solve-result.solve-result.json');
});

test('extractImportedProject: unwraps a repro bundle, passes a raw project, rejects non-objects', () => {
  const project = { project: { id: 'p' }, entities: [] };
  // raw project passes through
  assert.equal(extractImportedProject(project), project);
  // repro bundle -> its .project
  const bundle = { schema: SOLVE_REPRO_SCHEMA, demo: 'editor', project };
  assert.equal(extractImportedProject(bundle), project);
  // a repro bundle missing its project -> null
  assert.equal(extractImportedProject({ schema: SOLVE_REPRO_SCHEMA }), null);
  // non-objects -> null
  assert.equal(extractImportedProject(42), null);
  assert.equal(extractImportedProject('x'), null);
  assert.equal(extractImportedProject(null), null);
});
