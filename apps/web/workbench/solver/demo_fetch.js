import { SOLVE_WORKBENCH_DEMOS } from './demo_projects.js';

const ANALYSIS = Object.freeze({
  solved: Object.freeze({
    dof_estimate: 1,
    structural_state: 'underconstrained',
    conflict_group_count: 0,
    redundant_constraint_estimate: 0,
  }),
  blocked: Object.freeze({
    dof_estimate: 0,
    structural_state: 'overconstrained',
    conflict_group_count: 1,
    redundant_constraint_estimate: 0,
  }),
});

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function response(status, envelope) {
  return {
    status,
    ok: status >= 200 && status < 300,
    async json() {
      return clone(envelope);
    },
    async text() {
      return JSON.stringify(envelope);
    },
  };
}

function analysisDiagnostic(analysis) {
  return {
    level: 'info',
    code: 'SOLVE_ANALYSIS',
    message: `dof=${analysis.dof_estimate} state=${analysis.structural_state} conflicts=${analysis.conflict_group_count} redundant=${analysis.redundant_constraint_estimate}`,
    analysis,
  };
}

function solvedLine(project) {
  const evaluatedView = clone(project);
  evaluatedView.entities = evaluatedView.entities.map((entity) => (
    entity.id === 'L1'
      ? { ...entity, line: [[0, 3], [10, 3]] }
      : entity
  ));
  return {
    ok: true,
    value: {
      evaluatedView,
      evaluatedGeometry: {
        L1: {
          start: { x: 0, y: 3 },
          end: { x: 10, y: 3 },
        },
      },
      solve: { ok: true, iterations: 4, finalError: 1e-9 },
    },
    diagnostics: [analysisDiagnostic(ANALYSIS.solved)],
  };
}

function passthroughSolved(project) {
  return {
    ok: true,
    value: {
      evaluatedView: clone(project),
      evaluatedGeometry: {},
      solve: { ok: true, iterations: 0, finalError: 0 },
    },
    diagnostics: [analysisDiagnostic(ANALYSIS.solved)],
  };
}

function blockedConflict() {
  return {
    ok: false,
    error_code: 'SOLVE_UNSATISFIED',
    error: 'demo sketch is intentionally overconstrained',
    diagnostics: [analysisDiagnostic(ANALYSIS.blocked)],
    analysis: clone(ANALYSIS.blocked),
    solve: { ok: false, iterations: 100, finalError: 1.2 },
  };
}

function parseProject(init) {
  if (typeof init?.body !== 'string') {
    return null;
  }
  try {
    return JSON.parse(init.body);
  } catch {
    return null;
  }
}

export function createSolveDemoFetch() {
  return async function solveDemoFetch(_url, init = {}) {
    const method = (init.method ?? 'GET').toUpperCase();
    if (method !== 'POST') {
      return response(405, {
        ok: false,
        error_code: 'SOLVE_DEMO_METHOD_NOT_ALLOWED',
        error: 'demo solve endpoint only accepts POST',
        diagnostics: [],
      });
    }

    const project = parseProject(init);
    if (!project?.project?.id) {
      return response(400, {
        ok: false,
        error_code: 'SOLVE_DEMO_BAD_PROJECT',
        error: 'request body must be a VEMCAD-PROJECT object',
        diagnostics: [],
      });
    }

    if (project.project.id === SOLVE_WORKBENCH_DEMOS.solvableLine.project.id) {
      return response(200, solvedLine(project));
    }
    if (project.project.id === SOLVE_WORKBENCH_DEMOS.conflictingLine.project.id) {
      return response(422, blockedConflict());
    }
    if (project.project.id === SOLVE_WORKBENCH_DEMOS.passthroughUnsupported.project.id) {
      return response(200, passthroughSolved(project));
    }

    return response(400, {
      ok: false,
      error_code: 'SOLVE_DEMO_PROJECT_NOT_FOUND',
      error: `unknown demo project: ${project.project.id}`,
      diagnostics: [],
    });
  };
}
