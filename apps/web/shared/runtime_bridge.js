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
export function exportRuntimeProjectFromDocumentState(documentState, options = {}) {
  if (!documentState || typeof documentState.listEntities !== 'function') {
    return invalidDocumentState();
  }
  const cadgfDocument = exportCadgfDocument(documentState, { baseCadgfJson: options.baseCadgfJson ?? null });
  return importProjectFromCadgfDocument(cadgfDocument, options);
}

// VEMCAD-PROJECT -> DocumentState (via a CADGF Document + the editor import
// adapter). Loads document content into `documentState`; selection/snap/view are
// intentionally left untouched (this bridges document content, not session UI
// state). Returns { ok, value: documentState, diagnostics } or a derive failure.
export function importRuntimeProjectToDocumentState(documentState, project, options = {}) {
  if (!documentState || typeof documentState.restore !== 'function') {
    return invalidDocumentState();
  }
  const derived = deriveCadgfDocument(project, options);
  if (!derived.ok) return derived;

  const resolved = resolveEditorImportPayload(derived.value);
  applyResolvedEditorImport(documentState, resolved, null, null, null, { silent: options.silent ?? false });

  const warnings = (resolved.warnings ?? []).map((w) => ({ level: 'info', code: 'EDITOR_IMPORT_WARNING', message: String(w) }));
  return { ok: true, value: documentState, diagnostics: [...(derived.diagnostics ?? []), ...warnings] };
}
