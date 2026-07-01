# Render Reference Runbook Size Contract — Dev & Verification (2026-07-01)

## Boundary

This slice corrects operator documentation for AutoCAD returned-reference
intake. It does not change render output, compare scoring, request validation
behavior, private drawing handling, or AutoCAD equivalence claims.

## Problem

The current code requires a recapture request to declare
`requested_expected_size`, then compares returned PNG dimensions against that
declared size. A malformed request that omits the size now fails closed with
`missing_requested_expected_size`.

The G11 AutoCAD reference input runbook still described the fulfillment path as
opening returned PNGs to record `expected_size`. That wording was stale after
the size-contract hardening and could mislead an operator into thinking a
returned PNG is allowed to define its own expected size.

## Implementation

- `VEMCAD_G11_AUTOCAD_REFERENCE_INPUT_RUNBOOK_20260628.md`
  - keeps initial manifest generation wording accurate: an accepted AutoCAD
    reference PNG may define manifest `expected_size`;
  - updates the recapture/fulfillment path to say the request-declared
    `requested_expected_size` is enforced;
  - states that returned PNGs are opened only to compare actual dimensions and
    never define their own expected size.
- `test_reference_input_runbook_docs.py`
  - guards the runbook against reintroducing the stale returned-PNG self-sizing
    wording.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_reference_input_runbook_docs.py -q
```

Result:

```text
1 passed in 0.00s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
220 passed in 36.34s
```

## Closeout

The operator-facing runbook now matches the shipped fail-closed size contract:
returned PNGs are evidence to inspect, not an authority that can set the size
contract after the fact.
