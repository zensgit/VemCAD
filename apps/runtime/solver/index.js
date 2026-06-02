// VemCAD Project Runtime v1 — solver integration (C2 / Tier 1).
//
// The local loop (frozen Tier 1 spec §D5):
//   project --buildSolverProject--> CADGF-PROJ --runner--> out
//          --applySolvedVars--> evaluatedGeometry
//          --buildEvaluatedProjectView--> transient view
//          --deriveCadgfDocument--> CADGF Document (rendered scene)
//
// Truth = entities(seed) + constraints; the solved geometry is DERIVED (never
// persisted, never in golden). solveProject does NOT mutate the input project.
import { normalizeProjectModel } from '../project/index.js';
import { deriveCadgfDocument } from '../scene/index.js';
import { buildSolverProject } from './adapter.js';
import { createCliSolveRunner } from './runner.js';

export { buildSolverProject } from './adapter.js';
export { createCliSolveRunner } from './runner.js';

export const ERROR_SOLVE_FAILED = 'SOLVE_FAILED'; // runner could not produce a result
export const ERROR_SOLVE_UNSATISFIED = 'SOLVE_UNSATISFIED'; // solver ran but did not converge

function ok(value, diagnostics = []) {
  return { ok: true, value, diagnostics };
}

function fail(errorCode, error, diagnostics = []) {
  return { ok: false, error_code: errorCode, error, diagnostics };
}

// Reverse the mint map: solver `out.vars` ({ "<mintedId>.x|y": value }) ->
// { entityId: { role: { x, y } } }. Ignores unknown ids / non-finite values.
export function applySolvedVars(pointMap, vars) {
  const evaluated = {};
  for (const [key, value] of Object.entries(vars ?? {})) {
    const dot = key.lastIndexOf('.');
    if (dot < 0) continue;
    const mintedId = key.slice(0, dot);
    const coord = key.slice(dot + 1);
    const ref = pointMap?.[mintedId];
    if (!ref || (coord !== 'x' && coord !== 'y') || !Number.isFinite(value)) continue;
    if (!evaluated[ref.entity]) evaluated[ref.entity] = {};
    if (!evaluated[ref.entity][ref.role]) evaluated[ref.entity][ref.role] = {};
    evaluated[ref.entity][ref.role][coord] = value;
  }
  return evaluated;
}

// Build a TRANSIENT project-view with each entity's solvable geometry overlaid
// by the evaluated coords (non-solved params like radius/angles keep their seed).
// This is NOT save/load truth — only fed to deriveCadgfDocument. Returns a result.
export function buildEvaluatedProjectView(project, evaluated) {
  const normalized = normalizeProjectModel(project);
  if (!normalized.ok) return normalized;
  const p = normalized.value;

  const xy = (roles, role, fallback) => {
    const r = roles?.[role];
    return r && Number.isFinite(r.x) && Number.isFinite(r.y) ? [r.x, r.y] : fallback;
  };

  const entities = p.entities.map((e) => {
    const roles = evaluated?.[e.id];
    if (!roles) return e;
    if (e.kind === 'line' && Array.isArray(e.line)) {
      return { ...e, line: [xy(roles, 'start', e.line[0]), xy(roles, 'end', e.line[1])] };
    }
    if (e.kind === 'circle' && e.circle) {
      return { ...e, circle: { ...e.circle, c: xy(roles, 'center', e.circle.c) } };
    }
    if (e.kind === 'arc' && e.arc) {
      return { ...e, arc: { ...e.arc, c: xy(roles, 'center', e.arc.c) } };
    }
    if (e.kind === 'point') {
      return { ...e, point: xy(roles, 'self', e.point) };
    }
    return e;
  });

  return ok({ ...p, entities }, []);
}

function analysisDiagnostics(analysis) {
  if (!analysis || typeof analysis !== 'object') return [];
  return [{
    level: 'info',
    code: 'SOLVE_ANALYSIS',
    message: `dof=${analysis.dof_estimate} state=${analysis.structural_state} conflicts=${analysis.conflict_group_count} redundant=${analysis.redundant_constraint_estimate}`,
    analysis,
  }];
}

// Resolve the editor entity ids involved in the solver's CONFLICT action panels by mapping each
// conflicting solver variable key ("<mintedPointId>.<coord>") back through the adapter pointMap
// (mintedId -> { entity, role }). This is id-keyed, so it is robust to the solver's internal
// constraint reordering / evaluable-filtering (NO constraint-index alignment is assumed); minted
// point ids are dot-free, so a key splits cleanly at its single dot. Owning entities dedup (a
// line's start+end points roll up to the one line). Returns editor entity ids ready to highlight.
export function resolveConflictEntityIds(analysis, pointMap) {
  if (!pointMap || typeof pointMap !== 'object') return [];
  const panels = Array.isArray(analysis?.action_panels) ? analysis.action_panels : [];
  const ids = new Set();
  for (const panel of panels) {
    if (panel?.category !== 'conflict' || panel?.enabled !== true) continue;
    const keys = Array.isArray(panel.variable_keys) ? panel.variable_keys : [];
    for (const key of keys) {
      if (typeof key !== 'string') continue;
      const dot = key.lastIndexOf('.');
      const mintedId = dot > 0 ? key.slice(0, dot) : key;
      const mapped = pointMap[mintedId];
      if (mapped && mapped.entity !== undefined && mapped.entity !== null) ids.add(mapped.entity);
    }
  }
  return [...ids];
}

// Solve a project: build solver-input, run the solver (injectable runner;
// defaults to the CLI shell-out), write solved vars back to a transient
// evaluated view. Does NOT touch the input project (seed). Returns
// { ok, value: { evaluatedView, evaluatedGeometry, solve }, diagnostics }.
export function solveProject(project, options = {}) {
  const built = buildSolverProject(project, options);
  if (!built.ok) return built;
  const { cadgfProject, pointMap } = built.value;
  const diagnostics = [...built.diagnostics];

  const runner = options.runner ?? createCliSolveRunner(options);
  let out;
  try {
    out = runner(cadgfProject);
  } catch (err) {
    return fail(ERROR_SOLVE_FAILED, err?.message ?? String(err), diagnostics);
  }
  if (!out || typeof out !== 'object') {
    return fail(ERROR_SOLVE_FAILED, 'solve runner returned no result object', diagnostics);
  }
  // Enrich the analysis with the editor entity ids involved in conflicts, resolved server-side
  // via the adapter pointMap (the only place the minted-point <-> entity map lives). It rides
  // WITH the analysis so it reaches the controller on BOTH paths — conflicts surface as ok:false.
  const analysis = out.analysis && typeof out.analysis === 'object'
    ? { ...out.analysis, conflict_entity_ids: resolveConflictEntityIds(out.analysis, pointMap) }
    : out.analysis;
  // A solver failure (unsatisfiable / non-converged) must NOT be treated as a
  // solve: return ok:false WITHOUT writing back or deriving, preserving the
  // structured analysis (conflict / redundancy / action panels) and message.
  if (out.ok !== true) {
    return {
      ok: false,
      error_code: ERROR_SOLVE_UNSATISFIED,
      error: typeof out.message === 'string' && out.message ? out.message : 'solver did not converge / constraints unsatisfiable',
      diagnostics: [...diagnostics, ...analysisDiagnostics(analysis)],
      analysis,
      solve: { ok: false, iterations: out.iterations, finalError: out.final_error },
    };
  }

  const evaluatedGeometry = applySolvedVars(pointMap, out.vars);
  const view = buildEvaluatedProjectView(project, evaluatedGeometry);
  if (!view.ok) return view;

  return ok(
    {
      evaluatedView: view.value,
      evaluatedGeometry,
      solve: { ok: !!out.ok, iterations: out.iterations, finalError: out.final_error },
    },
    [...diagnostics, ...analysisDiagnostics(analysis)],
  );
}

// Full local loop: solve, then derive the rendered CADGF Document from the
// evaluated view. Returns { ok, value: { cadgfDocument, solve, evaluatedGeometry }, diagnostics }.
export function solveAndDeriveScene(project, options = {}) {
  const solved = solveProject(project, options);
  if (!solved.ok) return solved;
  const derived = deriveCadgfDocument(solved.value.evaluatedView, options);
  if (!derived.ok) return { ...derived, diagnostics: [...solved.diagnostics, ...(derived.diagnostics ?? [])] };
  return ok(
    { cadgfDocument: derived.value, solve: solved.value.solve, evaluatedGeometry: solved.value.evaluatedGeometry },
    [...solved.diagnostics, ...derived.diagnostics],
  );
}
