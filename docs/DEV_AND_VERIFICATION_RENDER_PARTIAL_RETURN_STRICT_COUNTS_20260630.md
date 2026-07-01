# Render Reference Partial-Return Strict Counts — Dev & Verification (2026-06-30)

## Boundary

This slice hardens the operator handoff text for partial AutoCAD reference
returns. It does not render drawings, change X3 scoring, change the renderer,
or claim AutoCAD equivalence. Fresh matched-view AutoCAD PNGs or an explicit
world window remain required for any equivalence claim.

## Problem

The generated `reference_request.md` post-return route command now scales its
positive compare-distribution guards to the full generated request case count:

- `matched-pass=<case_count>`
- `match=<case_count>`
- `pass=<case_count>`

That is correct for a full return. The same handoff also supports partial
returns via repeated `--case-id <ID>`, but the text did not say that operators
must adjust those three positive distribution counts to the number of selected
returned cases. Without that note, a valid partial return can look like a strict
route failure.

## Implementation

- `tools/render_regression/acad_manifest_compare.py`
  - generated `reference_request.md` now states that partial-return strict
    positive compare-distribution counts must be changed to the selected
    returned case count.
- `tools/render_regression/README.md`
  - documents the same full-return vs partial-return distinction.
- `tools/render_regression/tests/test_acad_manifest_compare.py`
  - asserts both the generated handoff and README keep the partial-return count
    adjustment text.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
```

Result:

```text
13 passed in 1.57s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
212 passed in 33.42s
```

## Closeout

Full-return generated commands remain strict and exact. Partial returns remain
supported, but the handoff now tells operators how to keep the strict compare
distribution guards aligned with the selected subset instead of the full request
case count.
