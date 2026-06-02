// Canonical solve-export builders — the ONE source of truth for the shapes/filenames the product
// hands out, so the demo and the editor (current project) export the SAME Project JSON, Solve
// Repro Bundle, CADGF Preview, and solve-evidence text rather than each rolling their own.
//
// Pure + DOM-free (string/object/filename builders only); the DOM IO (copy/download) stays at the
// call site. The repro bundle keeps a versioned `schema` so a copied bundle is self-describing,
// and a `source` field identifies where it came from (a demo key, or the editor) — that is the
// only thing that differs between callers.

export const SOLVE_REPRO_SCHEMA = 'vemcad-solve-demo-repro/v1';

function safeFilenameStem(raw, fallback) {
  const base = raw || fallback;
  return String(base).replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || fallback;
}

// One-line-per-fact solve evidence (also embedded in the repro bundle). Stable, greppable.
export function solveEvidenceText(envelope, summary) {
  if (!envelope || !summary) return 'No solve result yet.';
  const lines = [
    `ok=${envelope.ok === true ? 'true' : 'false'}`,
    Number.isFinite(summary.httpStatus) ? `http=${summary.httpStatus}` : null,
    summary.status ? `status=${summary.status}` : null,
    summary.errorCode ? `error=${summary.errorCode}` : null,
    summary.structuralState ? `state=${summary.structuralState}` : null,
    Number.isFinite(summary.dofEstimate) ? `dof=${summary.dofEstimate}` : null,
    Number.isFinite(summary.conflictGroupCount) ? `conflicts=${summary.conflictGroupCount}` : null,
    Number.isFinite(summary.redundantConstraintEstimate) ? `redundant=${summary.redundantConstraintEstimate}` : null,
    Number.isFinite(summary.iterations) ? `iters=${summary.iterations}` : null,
    Number.isFinite(summary.finalError) ? `err=${summary.finalError}` : null,
    Number.isFinite(summary.diagnosticCount) ? `diagnostics=${summary.diagnosticCount}` : null,
  ].filter(Boolean);
  return lines.join('\n') || 'Solve result has no summary.';
}

export function projectJsonText(project) {
  return `${JSON.stringify(project, null, 2)}\n`;
}

// A self-describing reproduction bundle: project INPUT + solve OUTPUT + evidence together, so a
// solve can be replayed/triaged from one paste. `demoKey` carries the source (a demo key, or e.g.
// 'editor'); `shareUrl` is the link that reproduces it (null when there is none).
export function reproBundleJsonText({ project, solveEnvelope, solveEvidence, demoKey, shareUrl }) {
  return `${JSON.stringify({
    schema: SOLVE_REPRO_SCHEMA,
    demo: demoKey,
    share_url: shareUrl || null,
    project,
    solve_result: solveEnvelope,
    solve_evidence: solveEvidence || null,
  }, null, 2)}\n`;
}

export function filenameForProject(project, key) {
  return `${safeFilenameStem(project?.project?.id || key, 'vemcad-project')}.vemcad-project.json`;
}

export function filenameForPreviewDocument(document, key) {
  return `${safeFilenameStem(document?.document_id || key, 'vemcad-preview')}.cadgf-document.json`;
}

export function filenameForSolveResult(envelope, project, key) {
  const raw = project?.project?.id || envelope?.value?.evaluatedView?.project?.id || key;
  return `${safeFilenameStem(raw, 'vemcad-solve-result')}.solve-result.json`;
}
