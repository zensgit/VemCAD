# VemCAD G11 Matched-Window Derivation Attempt (2026-06-28)

## Purpose

This note records the post-closeout follow-up to the one-week G11
render-fidelity goal:

> Can the existing AutoCAD reference PNG plus the VemCAD render report be used
> to derive a trustworthy explicit `render_cli --window` so that X3 becomes
> interpretable without recapturing AutoCAD?

Short answer: **not safely from the current inputs**.

No drawing, AutoCAD PNG, VemCAD PNG, overlay, or customer artifact is committed
with this note. All artifacts below are local `/tmp` evidence.

## Inputs

- AutoCAD reference:
  `/tmp/vemcadautocadplot/batch/png/G11-1.png`
- Source DXF:
  `/tmp/vacadbatchinputs/B11.dxf`
- Baseline VemCAD run:
  `/tmp/vemcad-fidelity-out/g11_week_real_20260628T133732Z`
- Renderer image:
  `ghcr.io/zensgit/vemcad-render:main`

Baseline view-space framing:

```json
{
  "ref_fill_x": 0.4361,
  "ref_fill_y": 0.922,
  "cand_fill_x": 0.3732,
  "cand_fill_y": 0.7919,
  "fill_divergence_x": 0.0628,
  "fill_divergence_y": 0.1301,
  "aspect_delta": 0.0035,
  "framing_mismatch": true
}
```

Baseline X3:

```json
{
  "ink_iou": 0.8021,
  "ssim": 0.4959,
  "color_dist": 134.1,
  "band": "fallback"
}
```

This remains **not interpretable as renderer fidelity** because the view-space
contract is mismatched.

## Attempt 1 — Use `render_cli` Report `content_bbox` As The Window

The baseline report showed header/extents clip narrower than content:

```json
{
  "clip": {
    "min_x": -125,
    "min_y": -25,
    "max_x": 925,
    "max_y": 1460
  },
  "content_bbox": {
    "min_x": -125,
    "min_y": -25,
    "max_x": 1036.38864021677,
    "max_y": 1460
  }
}
```

Command shape:

```bash
render_cli \
  --input /in/B11.dxf \
  --out /out/G11_ours.png \
  --bg white \
  --width 2339 \
  --height 1653 \
  --window -125,-25,1036.38864021677,1460 \
  --report /out/G11_report.json \
  --class-mask-out /out/G11_semantic_mask.png
```

Result:

```json
{
  "status": "viewspace_mismatch",
  "ink_iou": 0.8081,
  "ssim": 0.513,
  "color_dist": 128.1,
  "band": "fallback",
  "framing": {
    "ref_fill_x": 0.4361,
    "ref_fill_y": 0.922,
    "cand_fill_x": 0.3732,
    "cand_fill_y": 0.7919,
    "fill_divergence_x": 0.0628,
    "fill_divergence_y": 0.1301,
    "framing_mismatch": true
  }
}
```

Conclusion: the real `content_bbox` window removes the stale-header concern but
does **not** match the AutoCAD plot/view envelope.

## Attempt 2 — Shrink The Content Window Around Its Center

The fill ratios suggested that the AutoCAD plot was roughly 14% more zoomed-in
than the VemCAD render. A derived test window shrank the content bbox around its
center by `0.856`:

```text
--window -41.38001790439256,81.91999999999996,952.7686581211626,1353.08
```

Result:

```json
{
  "status": "viewspace_mismatch",
  "ink_iou": 0.2471,
  "ssim": 0.0385,
  "color_dist": 151.9,
  "aspect_delta": 0.0436,
  "band": "fallback",
  "framing": {
    "ref_fill_x": 0.4361,
    "ref_fill_y": 0.922,
    "cand_fill_x": 0.41,
    "cand_fill_y": 0.8306,
    "fill_divergence_x": 0.0261,
    "fill_divergence_y": 0.0913,
    "framing_mismatch": true
  }
}
```

Conclusion: viewport tuning moves the page-fill numbers, but it also corrupts
the geometric comparison. This is not a valid route to a matched-view claim.

## Diagnostic Only — Reference Envelope Reframing

For diagnosis only, `autocad_batch_compare.py --candidate-frame
reference-envelope` raster-transformed the VemCAD PNG into the AutoCAD ink
envelope. This is not a render mode and not a world-space contract.

Result:

```json
{
  "source_ink_iou": 0.8021,
  "ink_iou": 0.8277,
  "delta_ink_iou": 0.0256,
  "source_framing_mismatch": true,
  "framing_mismatch": false
}
```

Candidate-side semantic diagnostics after the diagnostic reframing:

| Class | Candidate precision | Reference coverage | Candidate pixels | Band |
| --- | ---: | ---: | ---: | --- |
| geometry | 0.9295 | 0.6097 | 23015 | review |
| text | 0.0000 | 0.0000 | 332 | fallback |
| dimension | 0.4830 | 0.1202 | 11438 | fallback |
| hatch | 1.0000 | 0.0232 | 642 | pass |
| insert_text | 0.6086 | 0.0843 | 5900 | fallback |
| other | 1.0000 | 0.0009 | 8 | pass |

Conclusion: reference-envelope removes the page-fill mismatch as an image
diagnostic, but the X3 score remains fallback and class residuals remain. Since
this is a raster transform, it must not be used as an AutoCAD-equivalence gate.

## Final Decision

The current AutoCAD PNG does not carry enough view/window provenance to derive a
trustworthy explicit world `--window`.

The next valid input is one of:

1. a fresh AutoCAD export at model EXTENTS with the same aspect/size as the
   VemCAD render, or
2. the actual AutoCAD plot/window world rectangle used to produce the PNG.

Until one of those exists:

- keep renderer work closed;
- do not tune line/text/scale from aggregate X3;
- do not accept reference-envelope or hand-shrunk windows as gate evidence;
- keep using the manifest harness to fail closed on `viewspace_mismatch`.
