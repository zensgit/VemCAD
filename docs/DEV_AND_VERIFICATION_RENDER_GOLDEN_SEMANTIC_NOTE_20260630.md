# Render Golden Semantic Note Refresh — Dev & Verification (2026-06-30)

## Boundary

This slice refreshes stale golden/regression wording after the semantic class
buffer landed. It does not change rendering, X3 scoring, golden pass/fail
thresholds, or any AutoCAD equivalence claim.

## Problem

`tools/render_regression/golden/golden.json` and nearby regression docs still
said D2 had "NO text/geometry split" because it needed a renderer-supplied text
mask. That was true before the semantic provenance line, but it is stale now:
`render_cli` emits candidate-side semantic class diagnostics. The remaining
honest gap is different: AutoCAD/reference semantics are still unknown, so there
is no reference-vs-candidate semantic pass/fail gate.

## Implementation

- `golden/golden.json`
  - replaces the stale "needs renderer mask" rationale with the current state:
    candidate-side semantic diagnostics exist, but the gate still uses combined
    `ink_iou` until a reference/AutoCAD semantic mask or gate policy exists;
  - keeps text-dominant fixtures `gate=false`.
- `tools/render_regression/README.md`
  - updates the D2 known-gap explanation with the same current-state wording.
- `tools/render_regression/compare.py`
  - updates the module docstring so future readers do not reopen already-shipped
    renderer-mask work.
- `tools/render_regression/redteam_exp2.py`
  - updates diagnostic print text to describe the current combined-ink gate.
- `tools/render_regression/tests/test_regress.py`
  - adds a regression that rejects the old stale phrases in the real golden
    manifest and asserts the new candidate-side/reference-side distinction.

## Verification

Focused:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_regress.py \
  tools/render_regression/tests/test_compare.py -q
```

Result:

```text
27 passed in 1.34s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
212 passed in 32.07s
```

## Closeout

The golden manifest now reflects the shipped semantic diagnostics without
overclaiming them as an AutoCAD/reference semantic gate. Text-heavy drawings
remain non-gating until that separate policy/evidence exists.
