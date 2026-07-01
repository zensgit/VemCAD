# Render Manifest Expected Size Required — Dev & Verification (2026-07-01)

## Boundary

This slice hardens AutoCAD reference manifest intake and recapture request
generation. It does not change render output, X3 scoring, view-space thresholds,
private drawing handling, or AutoCAD equivalence claims.

## Problem

Returned-reference intake already requires `requested_expected_size`, but the
upstream AutoCAD manifest validator still allowed a case with no
`expected_size`. The recapture request generator also had a fallback that could
derive `requested_expected_size` from the current rejected AutoCAD PNG when the
compare row did not carry an explicit size.

That kept a narrow path where the size contract could be inferred from an image
instead of being an explicit declaration.

## Implementation

- `acad_reference_manifest.py`
  - emits `missing_expected_size` and blocks the manifest when a case omits
    `expected_size`.
- `acad_manifest_compare.py`
  - removes the current-AutoCAD-PNG size fallback when writing
    `reference_request.json`;
  - carries `requested_expected_size` only when the compare row has a validated
    `expected_size`.
- `README.md`
  - documents that each manifest case must declare `expected_size`, and that
    later request generation does not infer it from current or returned PNGs.
- Tests
  - cover manifest missing-size rejection;
  - cover recapture request generation with no fallback to the current PNG
    dimensions;
  - guard the README wording.

## Verification

Focused:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_manifest.py \
  tools/render_regression/tests/test_acad_manifest_compare.py::test_reference_request_does_not_fallback_to_current_png_size \
  tools/render_regression/tests/test_acad_manifest_compare.py::test_readme_documents_manifest_expected_size_as_required \
  tools/render_regression/tests/test_reference_input_runbook_docs.py -q
```

Result:

```text
12 passed in 0.44s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
223 passed in 38.20s
```

## Closeout

The size contract is now explicit from the first manifest gate through the
returned-reference request path. A stale or hand-written manifest/request cannot
silently let an AutoCAD PNG define its own expected dimensions.
