# VemCAD G11 Text Layout Diagnostics (2026-06-28)

## Purpose

This slice adds a product-side diagnostic tool for the G11/B11 title-block
investigation. It consumes the `render_cli --report` text placement provenance
that was added in the previous slice and turns it into entity-level review
artifacts.

This is not a renderer behavior change and it does not claim G11 matches
AutoCAD. It is a way to avoid another global pixel tweak: inspect the actual
text entities first.

## Tool

```bash
python3 tools/render_regression/text_provenance_diagnostics.py \
  /path/to/G11_report.json \
  --image /path/to/G11_ours.png \
  --block HC_BTL_BLK \
  --out-dir /tmp/vemcad-fidelity-out/g11_text_layout_diag \
  --print-summary
```

Outputs:

- `text_provenance_summary.json` — machine-readable buckets and per-record rows.
- `text_provenance_records.tsv` — spreadsheet-friendly entity rows.
- `text_provenance_overlay.png` — candidate render with approximate text boxes
  and labels.

The tool reads `text_placement.records[]` and records, per visible text entity:

- `source_type`
- `semantic_class`
- `block_name`
- `text_kind`
- `attribute_tag`
- style/font fields
- `font_target_ratio` and `block_height_target_ratio`
- screen position and approximate screen bbox
- layout flags such as missing provenance, missing attribute tags, suspicious
  visible block-height scaling, or viewport overflow.

## Boundary

The overlay boxes are diagnostic approximations based on report positions,
`max_line_width_px`, and `block_height_px`. They are good enough to locate a
title-block text record, but they are not a renderer glyph-bound proof.

The current G11 view-space contract remains unchanged: G11 is still a
view-space-mismatched AutoCAD comparison until the AutoCAD reference or the
render window is matched.

## Live G11 Smoke

The tool was run against the current live G11 report from the previous
provenance slice:

```bash
python3 tools/render_regression/text_provenance_diagnostics.py \
  /tmp/vemcad-fidelity-out/g11_text_provenance_20260628T120605/G11_report.json \
  --image /tmp/vemcad-fidelity-out/g11_text_provenance_20260628T120605/G11_ours.png \
  --block HC_BTL_BLK \
  --out-dir /tmp/vemcad-fidelity-out/g11_text_layout_diag_20260628T051924 \
  --print-summary
```

Observed:

```text
selected / all     : 15 / 39
buckets            : 2
flags              : font_px_target_ratio_outlier=3
- count=12  source=INSERT    kind=text    block=HC_BTL_BLK     no-tag flags=-
- count=3   source=INSERT    kind=attdef  block=HC_BTL_BLK     tag flags=font_px_target_ratio_outlier
```

This did not prove a visual defect by itself. It gave the next investigation a
specific, reviewable target: the three `HC_BTL_BLK` `ATTDEF` rows whose raw
`font_px` value was high relative to the report's `target_px`.

## ATTDEF Outlier Follow-up

The follow-up source audit found that `font_px` is not the visible text height.
CADGameFusion computes it as the Qt `QFont` pixel size needed to make the
string's tight glyph bbox reach the intended DXF world height. Sparse ATTDEF
glyphs can therefore have `font_px / target_px > 1` while their visible
`block_height_px / target_px` remains normal.

The diagnostic flag now uses `block_height_px / target_px` when available and
keeps `font_px / target_px` as an informational field. The same live G11 rows
now become evidence that the previous finding was a diagnostic false-positive,
not a renderer layout bug:

```text
HC_BTL_BLK ATTDEF rows:
font_px / target_px          ~1.62
block_height_px / target_px  ~1.07
layout flags                 none
```

## Next Use

Use the generated rows to pick one suspicious title-block path, for example a
specific `HC_BTL_BLK` `ATTRIB` / `ATTDEF` record or an outlier visible-height row.
Then inspect or fix that entity path directly in CADGameFusion, followed by a
normal A to C bump if rendering behavior changes.
