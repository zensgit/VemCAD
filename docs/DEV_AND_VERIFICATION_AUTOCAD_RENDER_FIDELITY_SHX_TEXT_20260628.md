# AutoCAD Render Fidelity - SHX Text Overdraw Tuning

Date: 2026-06-28

Scope: training-batch render fidelity for SHX-backed text after the hatch and
text-placement diagnostic slices. This records the provenance work, the rejected
broad text-rendering experiment, and the accepted HGCAD-only tuning consumed by
VemCAD.

## Problem

The remaining G10/G11 deltas were dominated by text and dimension-looking text.
Earlier render reports exposed text placement but did not say which DXF style or
SHX font stack produced each text entity, so a global font-rendering change
would have been guesswork.

## Diagnostics Landed

1. CADGameFusion #430 / VemCAD #152
   - Hatch pattern diagnostics.
   - Result: useful for ruling out hatch-pattern residuals in the current text
     outliers.

2. CADGameFusion #431 / VemCAD #153
   - Text placement diagnostics.
   - Result: located the text-heavy residuals but still lacked DXF style and
     font provenance.

3. CADGameFusion #432 / VemCAD #154
   - CADGameFusion: `325fba8dddec0656aa83f5249151a29f49361ca7`
   - VemCAD: `4f315fc24e46b0559f93a8f346de9aad6db1b8e2`
   - Change: preserve DXF text style provenance through direct text, MTEXT, and
     block-expanded text.
   - Report fields added to `text_placement` schema `0.2`:
     `text_style`, `text_style_known`, `text_font_file`, `text_bigfont_file`,
     `text_style_width_factor`, `text_style_char_ratio`, and
     `text_effective_width_factor`.

## Provenance Findings

Reports rendered from the training samples showed that the important text
outliers are not one uniform SHX case:

| sample | total text | dominant provenance |
|---|---:|---|
| G10 | 34 | 33 `standards`-style rows using `romans.shx` + `hzdx.shx`; 1 `HC_GBDIM` |
| G11 | 39 | 23 generated style rows using `romans.shx` + `hzdx.shx`; 15 `HGCAD` rows using `HGCAD.SHX` + `HGCADHZ.SHX`; 1 `HC_GBDIM` |
| G04 | 1001 | 787 `romans.shx` + `hzdx.shx`; 213 `HGCAD.SHX` + `HGCADHZ.SHX`; 1 `HC_GBDIM` |

This made a broad "all SHX text" change too risky: it would touch drawings with
large amounts of regular `romans.shx`/`hzdx.shx` text that were not the target
of the visible HGCAD residual.

## Rejected Experiment: Broad SHX Overdraw Removal

A first local experiment disabled the heavier song-like CJK fallback overdraw
for all SHX-backed text. It improved G10/G11 but regressed other drawings on
the same host baseline, especially G04.

Same-host baseline versus broad experiment:

| id | delta |
|---|---:|
| G01 | +0.0014 |
| G02 | -0.0080 |
| G03 | -0.0025 |
| G04 | -0.0572 |
| G05 | -0.0123 |
| G06 | -0.0123 |
| G07 | +0.0034 |
| G08 | +0.0003 |
| G09 | +0.0026 |
| G10 | +0.0073 |
| G11 | +0.0257 |
| G12 | +0.0015 |

Conclusion: broad SHX tuning is not acceptable. The G04 regression is larger
than the G10/G11 gain.

## Accepted Fix: HGCAD-only Overdraw Tuning

CADGameFusion #433:

- CADGameFusion: `535a1aca61a50e682c575119aaca378a30751767`
- Change: when text provenance confirms `HGCAD.SHX` or `HGCADHZ.SHX`, skip the
  heavier song-like CJK fallback overdraw. Other CJK/song text paths remain
  unchanged.
- Rationale: the HGCAD SHX pair is closer to AutoCAD single-stroke engineering
  SHX than to regular filled song/fangsong outlines. The fix is provenance-gated
  so it does not globally alter regular SHX text.

Same-host baseline versus HGCAD-only experiment:

| id | baseline | HGCAD-only | delta |
|---|---:|---:|---:|
| G01 | 0.8123 | 0.8123 | +0.0000 |
| G02 | 0.8965 | 0.8965 | +0.0000 |
| G03 | 0.9184 | 0.9184 | +0.0000 |
| G04 | 0.8724 | 0.8786 | +0.0062 |
| G05 | 0.8969 | 0.8969 | +0.0000 |
| G06 | 0.9322 | 0.9335 | +0.0013 |
| G07 | 0.8720 | 0.8829 | +0.0109 |
| G08 | 0.8296 | 0.8296 | +0.0000 |
| G09 | 0.8716 | 0.8716 | +0.0000 |
| G10 | 0.8129 | 0.8129 | +0.0000 |
| G11 | 0.8141 | 0.8377 | +0.0236 |
| G12 | 0.8393 | 0.8393 | +0.0000 |

Conclusion: HGCAD-only tuning improves the main G11 text residual without the
G04 regression caused by the broad SHX experiment.

## Verification

### CADGameFusion

Local targeted checks passed before opening CADGameFusion #433:

```bash
git diff --check
cmake --build /tmp/cadgf-shx-overdraw-tuning-qt-build --target render_cli -j2
ctest --test-dir /tmp/cadgf-shx-overdraw-tuning-qt-build \
  -R 'render_cli_(semantic_class_mask_smoke|dimension_class_provenance|semantic_class_provenance)' \
  --output-on-failure
```

CADGameFusion #433 CI passed:

- validate-samples
- quick-check
- Local CI
- Qt Tests
- Ubuntu/macOS/Windows core builds
- solve-loop checks

### VemCAD

VemCAD consumes the fix with a gitlink bump from
`325fba8dddec0656aa83f5249151a29f49361ca7` to
`535a1aca61a50e682c575119aaca378a30751767`.

Guardrail:

```bash
git -C deps/cadgamefusion merge-base --is-ancestor \
  535a1aca61a50e682c575119aaca378a30751767 origin/main
```

The training drawings were not committed to git. Local render comparison
artifacts were written under:

- `/tmp/vemcad-fidelity-out/batch_text_style_provenance_325fba8_local`
- `/tmp/vemcad-fidelity-out/batch_hgcad_overdraw_tuning_325fba8_local`

## Methodology Correction

Do not compare a local macOS `render_cli` experiment directly against an older
Linux render-image baseline. Platform font availability can dominate the
result and create false regressions. The accepted and rejected experiments above
compare same-host local builds:

- baseline: `/tmp/cadgf-text-style-provenance-qt-build`
- experiment: `/tmp/cadgf-shx-overdraw-tuning-qt-build`

Release-image validation can still be used after the VemCAD bump, but it should
be interpreted as a deployment check, not as the primary same-host A/B evidence.

## Remaining Boundaries

This slice fixes only the HGCAD-specific overdraw residual. It does not claim to
solve every text-fidelity issue:

- regular `romans.shx` + `hzdx.shx` text remains unchanged;
- exact SHX glyph parity is still renderer-dependent;
- G10/G11 residuals can still include dimension layout, plot-style, and
view-space effects.

The next text-fidelity slice should start from the `text_placement` provenance
report rather than from a global lineweight or global font knob.
