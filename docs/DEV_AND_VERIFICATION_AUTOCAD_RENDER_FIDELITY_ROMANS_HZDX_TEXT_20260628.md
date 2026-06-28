# AutoCAD Render Fidelity - romans.shx + hzdx.shx Text Baseline

Date: 2026-06-28

Scope: follow-up text-fidelity slice after the HGCAD SHX tuning. This records
the ordinary `romans.shx` + `hzdx.shx` investigation, the rejected experiments,
and the low-risk baseline adjustment consumed by VemCAD.

## Problem

After the HGCAD-specific overdraw fix, G10/G11 still showed text and dimension
residuals in the AutoCAD PLOT comparison. The newly landed text provenance
showed that these rows were mostly regular SHX text:

- G10: `standard` style, `romans.shx` + `hzdx.shx`
- G11: generated style rows, `romans.shx` + `hzdx.shx`
- G04: dense table/text content with a large number of the same
  `romans.shx` + `hzdx.shx` rows

That made a broad global font or stroke change risky. G04 is the guardrail:
experiments that help the small G10/G11 samples can still damage dense table
drawings.

## Rejected Experiments

All experiments were compared against a same-host local baseline to avoid
macOS-vs-Linux font differences being mistaken for renderer regressions.

| experiment | result |
|---|---|
| Disable overdraw for all `romans.shx` + `hzdx.shx` | G10/G11 improved slightly, but G04 regressed by `-0.0445`. Rejected. |
| Resolve `romans.shx` + `hzdx.shx` to CJK sans | Most drawings improved slightly, but G04 regressed by `-0.0174`. Rejected. |
| Width factor `0.95x` | Negative across the batch, including G10/G11. Rejected. |
| Width factor `1.05x` | Helped G04/G05/G06 but hurt G10/G11. Rejected. |
| Screen-symmetric overdraw after horizontal scale | Did not improve target residuals. Rejected. |
| Baseline shift `+0.10 * targetPx` | Negative across the batch. Rejected. |

The useful direction was the opposite baseline shift: move the rendered
`romans.shx` + `hzdx.shx` text slightly upward in screen space.

## Fix Landed

CADGameFusion #434:

- CADGameFusion: `234ea728f34e54c3d4c01b9fae1e2f27e2c2c8d1`
- Change: for text provenanced as `romans.shx` + `hzdx.shx`, apply a small
  render-time baseline adjustment of `-0.05 * targetPx`.
- Keep font family, width factor, and overdraw behaviour unchanged.
- Bump `text_placement` report schema to `0.3`.
- Add report fields:
  - `render_baseline_adjust_px`
  - `render_baseline_adjust_world`

This is deliberately narrower than the rejected font-family or stroke-weight
experiments. It targets the observed baseline residual without changing the
dense G04 text style materially.

## Verification

### CADGameFusion

Local checks:

```bash
git diff --check
cmake --build /tmp/cadgf-romans-hzdx-baseline-qt-build --target render_cli -j2
ctest --test-dir /tmp/cadgf-romans-hzdx-baseline-qt-build \
  -R 'render_cli_(semantic_class_mask_smoke|dimension_class_provenance|semantic_class_provenance)' \
  --output-on-failure
```

All 3 targeted render_cli tests passed. The report smoke now asserts
`render_baseline_adjust_px` is present.

CADGameFusion #434 CI passed:

- validate-samples
- quick-check
- Local CI
- Qt Tests
- Ubuntu/macOS/Windows core builds
- solve-loop checks

### Local 12-case AutoCAD Diagnostic Batch

Compared against the same-host local baseline with:

```bash
python3 autocad_batch_compare.py \
  --cases /tmp/vemcad-fidelity-out/batch_romans_hzdx_baseline_adjust_local/cases.json \
  --out-dir /tmp/vemcad-fidelity-out/batch_romans_hzdx_baseline_adjust_local/compare_acad_display_reference_envelope \
  --candidate-style acad-display \
  --candidate-frame reference-envelope \
  --tile-grid 6x4
```

Result:

| id | baseline | adjusted | delta |
|---|---:|---:|---:|
| G01 | 0.8849 | 0.8843 | -0.0006 |
| G02 | 0.8966 | 0.8970 | +0.0004 |
| G03 | 0.9169 | 0.9180 | +0.0011 |
| G04 | 0.8837 | 0.8840 | +0.0003 |
| G05 | 0.8903 | 0.8912 | +0.0009 |
| G06 | 0.9274 | 0.9277 | +0.0003 |
| G07 | 0.8767 | 0.8768 | +0.0001 |
| G08 | 0.8307 | 0.8309 | +0.0002 |
| G09 | 0.8647 | 0.8669 | +0.0022 |
| G10 | 0.8163 | 0.8179 | +0.0016 |
| G11 | 0.8259 | 0.8277 | +0.0018 |
| G12 | 0.8295 | 0.8308 | +0.0013 |

Interpretation:

- G10/G11 both move in the intended direction.
- G04, the dense text/table guardrail, does not regress.
- G01 has a `-0.0006` drift, treated as noise-level registration variance.
- The fix is intentionally small; it is a fidelity nudge, not a claim of
  AutoCAD equivalence.

Artifacts:

- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_baseline_adjust_local`
- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_nooverdraw_local`
- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_sans_local`
- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_width095_local`
- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_width105_local`
- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_symmetric_overdraw_local`
- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_yplus010_local`
- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_yminus010_local`
- `/tmp/vemcad-fidelity-out/batch_romans_hzdx_yminus005_local`

## Boundary

This slice improves ordinary SHX text placement without changing the global
font or plot-style strategy. Remaining text-fidelity work should continue from
the `text_placement` report and should not reintroduce the rejected global
font-family or overdraw changes unless a broader corpus proves them safe.
