// Product-layer bridge between the editor's DocumentState and the Project
// Runtime. It goes THROUGH the CADGF Document interchange format, so the Runtime
// never couples to the editor's internal entity shape — "the web bridge speaks
// CADGF". Thin composition of existing pieces:
//
//   DocumentState --exportCadgfDocument--> CADGF --importProjectFromCadgfDocument--> Project
//   Project --deriveCadgfDocument--> CADGF --resolveEditorImportPayload/apply--> DocumentState
//
// (S7 verification confirmed exportCadgfDocument already provides the
// DocumentState -> CADGF numeric-snapshot direction, so no new export adapter
// was needed.)
import { deriveCadgfDocument, importProjectFromCadgfDocument } from '../../runtime/scene/index.js';
import { exportCadgfDocument } from '../../../deps/cadgamefusion/tools/web_viewer/adapters/cadgf_document_adapter.js';
import { resolveEditorImportPayload, applyResolvedEditorImport } from '../../../deps/cadgamefusion/tools/web_viewer/adapters/editor_import_adapter.js';

function invalidDocumentState() {
  return { ok: false, error_code: 'INVALID_DOCUMENT_STATE', error: 'a DocumentState is required', diagnostics: [] };
}

// DocumentState -> VEMCAD-PROJECT (via a CADGF Document).
// Returns the unified runtime result { ok, value: project, diagnostics }.
//
// Determinism: exportCadgfDocument injects wall-clock in two places —
// metadata.created_at/modified_at (`new Date()`) and a default
// document_id (`web-${Date.now()}`). When `options.clock` is given the bridge
// pins BOTH (timestamps from the clock; document_id from `options.documentId`
// or a fixed default) so the export is reproducible. WITHOUT a clock the bridge
// inherits that wall-clock and is NOT deterministic across calls.
export function exportRuntimeProjectFromDocumentState(documentState, options = {}) {
  if (!documentState || typeof documentState.listEntities !== 'function') {
    return invalidDocumentState();
  }
  const cadgfDocument = exportCadgfDocument(documentState, { baseCadgfJson: options.baseCadgfJson ?? null });
  if (options.clock && typeof options.clock.now === 'function') {
    const now = options.clock.now();
    if (cadgfDocument.metadata && typeof cadgfDocument.metadata === 'object') {
      cadgfDocument.metadata.created_at = now;
      cadgfDocument.metadata.modified_at = now;
    }
    cadgfDocument.document_id = options.documentId ?? 'web-export';
  } else if (options.documentId !== undefined) {
    cadgfDocument.document_id = options.documentId;
  }
  return importProjectFromCadgfDocument(cadgfDocument, options);
}

// VEMCAD-PROJECT -> DocumentState (via a CADGF Document + the editor import
// adapter). Loads document content into `documentState`. selection/snap/view are
// passed as null (this bridges document content, not session UI state); note the
// editor adapter additionally resets currentSpaceContext for non-editor payloads.
// Returns { ok, value: documentState, diagnostics }, a derive failure, or a
// BRIDGE_LOAD_FAILED result (the editor import adapter throws on bad input — we
// convert that to the unified result so the bridge has a single contract).
export function importRuntimeProjectToDocumentState(documentState, project, options = {}) {
  if (!documentState || typeof documentState.restore !== 'function') {
    return invalidDocumentState();
  }
  const derived = deriveCadgfDocument(project, options);
  if (!derived.ok) return derived;

  let resolved;
  try {
    resolved = resolveEditorImportPayload(derived.value);
    applyResolvedEditorImport(documentState, resolved, null, null, null, { silent: options.silent ?? false });
  } catch (err) {
    return {
      ok: false,
      error_code: 'BRIDGE_LOAD_FAILED',
      error: err?.message ?? String(err),
      diagnostics: [...(derived.diagnostics ?? [])],
    };
  }

  const warnings = (resolved.warnings ?? []).map((w) => ({ level: 'info', code: 'EDITOR_IMPORT_WARNING', message: String(w) }));
  return { ok: true, value: documentState, diagnostics: [...(derived.diagnostics ?? []), ...warnings] };
}
