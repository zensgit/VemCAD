# Render Reference Request Expected Size Required — Dev & Verification (2026-07-01)

## Boundary

This slice hardens AutoCAD reference request intake. It does not change render
output, compare scoring, private drawing handling, or AutoCAD equivalence
claims.

## Problem

Returned-reference intake blocks when a returned AutoCAD PNG's actual size
differs from `requested_expected_size`. But if a hand-written or stale
`reference_request.json` omitted that field, the size contract was absent and
the returned PNG size check could not fire.

That made the size gate optional for malformed request packages.

## Implementation

- `acad_reference_batch.py`
  - `_expected_size_issues(...)` now emits
    `error:missing_requested_expected_size` when neither
    `requested_expected_size` nor legacy `expected_size` is present.
  - `--validate-request` and `--from-request` therefore fail closed before
    fulfilment/compare if the request package does not declare the expected
    capture size.
- Tests
  - added a dedicated missing-size blocked test;
  - updated existing request fixtures to declare their intended expected size,
    so each test still exercises its original path.
- README
  - documents that the tool never derives the expected size from the returned
    PNG itself.

## Verification

Focused:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_batch.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
```

Result:

```text
43 passed in 23.99s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
219 passed in 38.27s
```

## Closeout

Request packages now must carry their own expected capture size. A malformed
request is routed to `fix-request-package` instead of letting a returned PNG
define its own size contract.
