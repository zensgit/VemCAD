# Render Reference Handoff Strict Counts — Dev & Verification (2026-06-30)

## Boundary

This slice hardens the AutoCAD reference handoff after fresh PNGs are returned.
It does not render drawings, change X3 scoring, change the renderer, or claim
AutoCAD equivalence. The equivalence gate still requires fresh matched-view
AutoCAD PNGs or an explicit world window.

## Problem

The generated `reference_request.md` strict post-return route command encoded
single-case compare distribution guards:

- `--require-triage-bucket matched-pass=1`
- `--require-viewspace-status match=1`
- `--require-x3-band pass=1`

Those guards are correct for a one-case request, but they fail a valid
multi-case request after all returned PNGs pass. The operator handoff should
expect every requested case to become `matched-pass` / `match` / `pass`, not
exactly one case.

## Implementation

- `tools/render_regression/acad_manifest_compare.py`
  - computes the strict pass count from the generated request case count;
  - writes `matched-pass=<case_count>`, `match=<case_count>`, and
    `pass=<case_count>` into the generated post-return route command.
- `tools/render_regression/README.md`
  - documents that generated strict compare-distribution guards match the
    requested case count.
- `tools/render_regression/tests/test_acad_manifest_compare.py`
  - adds a two-case recapture request regression proving the generated strict
    route command uses `=2` and no longer preserves the old single-case `=1`
    assumption.

Structural route guards remain constant where they describe files/routes rather
than cases (`route-count=3`, `summary_tsv=1`, final exit-code count, etc.).

## Verification

Focused:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
```

Result:

```text
26 passed in 17.23s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
212 passed in 34.03s
```

## Closeout

The generated handoff now scales from one requested recapture case to many
without weakening fail-closed behavior. A `viewspace_mismatch` still remains an
input problem, and renderer work remains gated on valid matched-view evidence.
