# VemCAD One-Week Render-Fidelity Development Plan (2026-06-28)

## Goal

Execute one focused week of VemCAD render-fidelity development around G11/B11:
turn the current diagnostic boundary into a repeatable, evidence-backed
AutoCAD comparison loop without reopening renderer tweaks from aggregate pixel
scores.

The week is intentionally scoped to **view-space contract and comparison
methodology**. The recent text-layout line is closed:

- `text_placement` provenance exists.
- `HC_BTL_BLK` title-block rows have no corrected layout flags.
- remaining rotated-text notes are non-risk overlay caveats.

## Non-Goals

- No GUI AutoCAD automation or screenshot hunting.
- No global text, lineweight, or scale multiplier from G11's low X3 score.
- No X3 threshold relaxation.
- No renderer behavior change unless a matched-view comparison isolates a
  concrete class/entity defect.
- No CADGameFusion A to C bump unless a CADGameFusion fix is actually needed.

## Week Plan

### Day 1 — Matched-View Input Contract

Deliverable:

- Add a small manifest/contract format for AutoCAD reference inputs:
  `acad_png`, `drawing_id`, `source_dxf`, `capture_method`,
  `view_contract`, expected pixel size, and allowed trust tier.
- Add validator logic that fails closed when the AutoCAD PNG is missing,
  wrong-sized, or explicitly marked as viewport/screenshot instead of
  plot/export.

Verification:

- Unit tests for accepted plot/export references.
- Unit tests for rejected screenshot/viewport references.
- No private drawing committed by default.

### Day 2 — Matched-Window Harness

Deliverable:

- Add a helper that takes the manifest and invokes the existing
  `compare_vs_acad.py --viewspace-report --require-viewspace-match` path.
- Record candidate render provenance: image path, report path, semantic mask
  path, render image digest when available, and `X-Diff-*`/diagnostic metadata
  if produced by the service.

Verification:

- Synthetic manifest tests with generated PNGs.
- A local dry-run mode that validates manifests without requiring Docker or
  proprietary drawings.

### Day 3 — Batch Summary and Triage Output

Deliverable:

- Produce a stable per-case summary JSON/TSV:
  view-space status, X3 band, semantic-class rows if available, text-layout
  flags/notes if a render report is present.
- Add a contact-sheet or artifact index if enough PNG artifacts exist.

Verification:

- Synthetic batch tests proving:
  - view-space mismatch remains non-equivalence;
  - matched clean pairs pass;
  - text-layout flags and notes are surfaced separately.

### Day 4 — First Real G11 Run, If Inputs Exist

Gate:

- Requires a clean AutoCAD export PNG for B11/G11 or an explicit user-approved
  private fixture path. If the input is not available, this day becomes a
  no-op evidence update, not a renderer change.

Deliverable when input exists:

- Run the matched-view harness.
- Produce the comparison artifact bundle.
- Classify result:
  - `viewspace_mismatch`: stop; request corrected input/window.
  - `matched_pass`: record closeout.
  - `matched_fail`: identify the smallest candidate class/entity path for a
    later CADGameFusion fix.

Verification:

- Store command, artifact paths, scores, and verdict in the DEV/V ledger.

### Day 5 — Closeout and Next-Action Decision

Deliverable:

- Update the development and verification MD with the week's actual commits,
  commands, outputs, and remaining gates.
- If there was a safe code slice, merge it through normal PR + CI.
- If no safe code slice existed, land the boundary/closeout doc rather than
  inventing another renderer tweak.

Verification:

- All touched tests pass.
- PR CI green before merge.
- Final state includes exact `origin/main` SHA and any render image/run IDs
  used as evidence.

## Definition of Done

The week is complete when:

1. Each merged slice has a PR, tests, and a stated boundary.
2. `docs/DEV_AND_VERIFICATION_G11_RENDER_FIDELITY_WEEK_20260628.md` records
   the actual development and verification trail.
3. G11's state is one of:
   - matched-view pass;
   - matched-view fail with a specific next CADGameFusion target;
   - blocked on missing/invalid AutoCAD reference input.
4. No claim of AutoCAD equivalence is made while
   `compare_vs_acad.py --require-viewspace-match` fails.

## Current Start State

- VemCAD `origin/main`: `295b040`
- CADGameFusion gitlink: unchanged from current VemCAD main.
- Open VemCAD PRs: only pre-existing `#1` WIP.
- Current text-layout result:
  - all G11 text records: flags none, notes `rotated_bbox_is_approximate=7`;
  - `HC_BTL_BLK`: flags none, notes none.
