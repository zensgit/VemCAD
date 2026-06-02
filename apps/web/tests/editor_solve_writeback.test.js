import test from 'node:test';
import assert from 'node:assert/strict';

// Submodule-backed round-trip: proves the writeback FIELD-NAME contract end-to-end against the
// REAL editor DocumentState. translateEvaluatedViewToUpdates() emits editor-native patch keys
// (start/end, center); this confirms updateEntity() honors exactly those keys so the geometry
// actually moves. (The pure-DI tests in editor_solve.test.js stub the apply, so they can't
// catch a wrong key — a wrong key would merge as a junk field, normalize would drop it, and the
// geometry would silently not move. This test closes that hop with the real document.)
import { DocumentState } from '../../../deps/cadgamefusion/tools/web_viewer/state/documentState.js';
import { SelectionState } from '../../../deps/cadgamefusion/tools/web_viewer/state/selectionState.js';
import { translateEvaluatedViewToUpdates, shouldClearHighlight } from '../workbench/solver/editor_solve.js';

// Mirror of app.js's clearHighlight closure (clear only if the selection is still ours), exercised
// against the REAL SelectionState so the runtime link (entityIds + setSelection + shouldClearHighlight)
// is proven, not assumed — the DI tests stub clearHighlight and can't catch a SelectionState API drift.
function clearHighlightAgainst(selection, ids) {
  if (!selection || typeof selection.setSelection !== 'function') return;
  if (shouldClearHighlight(selection.entityIds, ids)) selection.setSelection([], null);
}

test('writeback: translated patches actually move line/circle/arc geometry in a real DocumentState', () => {
  const doc = new DocumentState();
  const line = doc.addEntity({ type: 'line', start: { x: 0, y: 0 }, end: { x: 10, y: 0 }, layerId: 0 });
  const circle = doc.addEntity({ type: 'circle', center: { x: 0, y: 0 }, radius: 5, layerId: 0 });
  const arc = doc.addEntity({ type: 'arc', center: { x: 0, y: 0 }, radius: 5, startAngle: 0, endAngle: 1, layerId: 0 });

  // A solved view keyed by the editor's OWN ids (export coerces editor id -> project id; import
  // keeps it numeric) — exactly what /solve returns.
  const evaluatedView = {
    entities: [
      { id: line.id, kind: 'line', line: [[1, 2], [9, 8]] },
      { id: circle.id, kind: 'circle', circle: { c: [3, 4], r: 5 } },
      { id: arc.id, kind: 'arc', arc: { c: [5, 6] } },
    ],
  };

  const updates = translateEvaluatedViewToUpdates(evaluatedView);
  assert.equal(updates.length, 3);
  for (const update of updates) {
    assert.equal(doc.updateEntity(update.id, update.patch), true, `updateEntity should accept patch for ${update.id}`);
  }

  const movedLine = doc.getEntity(line.id);
  assert.deepEqual({ x: movedLine.start.x, y: movedLine.start.y }, { x: 1, y: 2 });
  assert.deepEqual({ x: movedLine.end.x, y: movedLine.end.y }, { x: 9, y: 8 });

  const movedCircle = doc.getEntity(circle.id);
  assert.deepEqual({ x: movedCircle.center.x, y: movedCircle.center.y }, { x: 3, y: 4 });
  assert.equal(movedCircle.radius, 5, 'radius untouched (only the solved center is written)');

  const movedArc = doc.getEntity(arc.id);
  assert.deepEqual({ x: movedArc.center.x, y: movedArc.center.y }, { x: 5, y: 6 });
  assert.equal(movedArc.radius, 5, 'radius untouched');
});

test('clear highlight: clears OUR conflict highlight from a real SelectionState, once', () => {
  const selection = new SelectionState();
  selection.setSelection([1, 2], 1);            // solver highlighted the conflicting entities
  assert.deepEqual([...selection.entityIds].sort(), [1, 2]);

  clearHighlightAgainst(selection, [1, 2]);     // conflict-free solve -> clear our highlight
  assert.deepEqual(selection.entityIds, []);
  assert.equal(selection.primaryId, null);
});

test('clear highlight: does NOT wipe a selection the user changed after the highlight', () => {
  const selection = new SelectionState();
  selection.setSelection([1, 2], 1);            // solver highlight
  selection.setSelection([5], 5);               // user then selected something else
  clearHighlightAgainst(selection, [1, 2]);     // must NOT clear the user's [5]
  assert.deepEqual(selection.entityIds, [5]);
  assert.equal(selection.primaryId, 5);
});
