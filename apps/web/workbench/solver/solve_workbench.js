import { deriveCadgfDocument } from '../../../runtime/scene/index.js';

export const DEFAULT_SOLVE_ENDPOINT = '/solve';

function ok(value, diagnostics = []) {
  return { ok: true, value, diagnostics };
}

function fail(errorCode, error, diagnostics = []) {
  return { ok: false, error_code: errorCode, error, diagnostics };
}

function diagnosticsOf(envelope) {
  return Array.isArray(envelope?.diagnostics) ? envelope.diagnostics : [];
}

function analysisOf(envelope) {
  if (envelope?.analysis && typeof envelope.analysis === 'object') return envelope.analysis;
  return diagnosticsOf(envelope).find((d) => d?.code === 'SOLVE_ANALYSIS' && d.analysis)?.analysis ?? null;
}

function solveOf(envelope) {
  return envelope?.value?.solve ?? envelope?.solve ?? null;
}

export function summarizeSolveEnvelope(envelope, { httpStatus = null } = {}) {
  const analysis = analysisOf(envelope);
  const solve = solveOf(envelope);
  const errorCode = envelope?.error_code ?? null;
  const status = envelope?.ok === true
    ? 'solved'
    : errorCode === 'SOLVE_UNSATISFIED'
      ? 'blocked'
      : 'failed';

  return {
    status,
    ok: envelope?.ok === true,
    httpStatus,
    errorCode,
    message: envelope?.error ?? null,
    iterations: Number.isFinite(solve?.iterations) ? solve.iterations : null,
    finalError: Number.isFinite(solve?.finalError) ? solve.finalError : null,
    dofEstimate: Number.isFinite(analysis?.dof_estimate) ? analysis.dof_estimate : null,
    structuralState: typeof analysis?.structural_state === 'string' ? analysis.structural_state : null,
    conflictGroupCount: Number.isFinite(analysis?.conflict_group_count) ? analysis.conflict_group_count : null,
    redundantConstraintEstimate: Number.isFinite(analysis?.redundant_constraint_estimate) ? analysis.redundant_constraint_estimate : null,
    diagnosticCount: diagnosticsOf(envelope).length,
  };
}

async function parseJsonResponse(response) {
  if (response && typeof response.json === 'function') {
    return response.json();
  }
  if (response && typeof response.text === 'function') {
    return JSON.parse(await response.text());
  }
  throw new Error('solve response is not JSON-readable');
}

export async function solveRuntimeProject(project, options = {}) {
  const endpoint = options.endpoint ?? DEFAULT_SOLVE_ENDPOINT;
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  if (typeof fetchImpl !== 'function') {
    return fail('SOLVE_FETCH_UNAVAILABLE', 'fetch is not available', []);
  }

  let body;
  try {
    body = JSON.stringify(project);
  } catch (err) {
    return fail('SOLVE_REQUEST_SERIALIZE_FAILED', err?.message ?? String(err), []);
  }

  let response;
  try {
    response = await fetchImpl(endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...(options.headers ?? {}) },
      body,
    });
  } catch (err) {
    return fail('SOLVE_REQUEST_FAILED', err?.message ?? String(err), []);
  }

  let envelope;
  try {
    envelope = await parseJsonResponse(response);
  } catch (err) {
    return fail('SOLVE_BAD_RESPONSE', err?.message ?? String(err), []);
  }

  const httpStatus = Number.isFinite(response?.status) ? response.status : null;
  if (!envelope || typeof envelope !== 'object') {
    return fail('SOLVE_BAD_RESPONSE', 'solve response must be an object', []);
  }
  return { ...envelope, httpStatus, summary: summarizeSolveEnvelope(envelope, { httpStatus }) };
}

export function deriveCadgfPreviewDocument(solveEnvelope, options = {}) {
  if (solveEnvelope?.ok !== true) {
    return fail('SOLVE_RESULT_REQUIRED', 'cannot derive a preview document from a failed solve', diagnosticsOf(solveEnvelope));
  }
  const evaluatedView = solveEnvelope?.value?.evaluatedView;
  if (!evaluatedView || typeof evaluatedView !== 'object') {
    return fail('SOLVE_EVALUATED_VIEW_MISSING', 'solve response did not include an evaluated project view', diagnosticsOf(solveEnvelope));
  }
  const deriveImpl = options.deriveCadgfDocumentImpl ?? deriveCadgfDocument;
  const derived = deriveImpl(evaluatedView, options);
  if (!derived.ok) {
    return { ...derived, diagnostics: [...diagnosticsOf(solveEnvelope), ...(derived.diagnostics ?? [])] };
  }
  return ok(derived.value, [...diagnosticsOf(solveEnvelope), ...(derived.diagnostics ?? [])]);
}

export function createSolveWorkbenchController(options = {}) {
  const listeners = new Set();
  let state = {
    status: 'idle',
    summary: null,
    envelope: null,
    previewDocument: null,
    diagnostics: [],
  };

  const notify = () => {
    for (const listener of listeners) listener(state);
  };
  const setState = (patch) => {
    state = { ...state, ...patch };
    notify();
    return state;
  };

  return {
    getState() {
      return state;
    },
    subscribe(listener) {
      listeners.add(listener);
      listener(state);
      return () => listeners.delete(listener);
    },
    async solve(project, solveOptions = {}) {
      setState({ status: 'solving', summary: null, envelope: null, previewDocument: null, diagnostics: [] });
      const envelope = await solveRuntimeProject(project, { ...options, ...solveOptions });
      const summary = envelope.summary ?? summarizeSolveEnvelope(envelope, { httpStatus: envelope.httpStatus ?? null });
      let previewDocument = null;
      let diagnostics = diagnosticsOf(envelope);
      if (envelope.ok === true && (solveOptions.derivePreview ?? options.derivePreview ?? true)) {
        const preview = deriveCadgfPreviewDocument(envelope, { ...options, ...solveOptions });
        diagnostics = preview.diagnostics ?? diagnostics;
        if (preview.ok) previewDocument = preview.value;
      }
      return setState({
        status: summary.status,
        summary,
        envelope,
        previewDocument,
        diagnostics,
      });
    },
  };
}
