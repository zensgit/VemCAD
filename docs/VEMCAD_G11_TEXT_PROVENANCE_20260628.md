# VemCAD G11 Text Provenance Slice (2026-06-28)

## Purpose

This note records the follow-up to the G11 semantic-diagnosis line:

> Expose enough `render_cli --report` provenance to distinguish visible
> title-block text that arrives through block `TEXT`, `MTEXT`, `ATTRIB`, and
> `ATTDEF` paths.

This is a diagnostic/reporting slice. It does **not** change rendering behavior
and does **not** claim G11 is AutoCAD-equivalent.

## What Shipped Upstream

CADGameFusion PR #436 shipped the renderer-side capability:

- `render_cli --report` text-placement schema is now `vemcad.render_text_placement`
  version `0.4`.
- Each text-placement record now includes `block_name`.
- The libdxfrw direct import path writes `text_kind` for direct and block-expanded
  `TEXT` / `MTEXT`.
- The libdxfrw fork now preserves `ATTRIB` vs `ATTDEF` identity and group-2
  attribute tags at the callback boundary (zensgit/libdxfrw#1), allowing the
  CADGameFusion adapter to write `text_kind=attrib|attdef` and `attribute_tag`
  metadata without guessing.

VemCAD consumes that capability through this gitlink-only bump:

- `deps/cadgamefusion`: `590cbf2` -> `5871fce`

## Verification

CADGameFusion local Qt-free verification before PR:

```bash
cmake -S . -B /private/tmp/cadgf-g11-provenance-build \
  -DBUILD_EDITOR_QT=OFF \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo

cmake --build /private/tmp/cadgf-g11-provenance-build \
  --target \
    test_dxf_libdxfrw_block_text_provenance \
    test_dxf_libdxfrw_fit_text \
    test_dxf_libdxfrw_mtext_inline_color \
  -j2

ctest --test-dir /private/tmp/cadgf-g11-provenance-build \
  -R 'test_dxf_libdxfrw_(block_text_provenance|fit_text|mtext_inline_color)_run' \
  --output-on-failure
```

Result:

```text
3/3 tests passed
```

The new `test_dxf_libdxfrw_block_text_provenance` fixture proves a block INSERT
containing all four text sources produces visible text entities with:

| Source entity | Expected metadata after INSERT expansion |
| --- | --- |
| `TEXT` | `source_type=INSERT`, `block_name=TitleBlock`, `text_kind=text` |
| `MTEXT` | `source_type=INSERT`, `block_name=TitleBlock`, `text_kind=mtext` |
| `ATTRIB` | `source_type=INSERT`, `block_name=TitleBlock`, `text_kind=attrib`, `attribute_tag=ATTR_TAG` |
| `ATTDEF` | `source_type=INSERT`, `block_name=TitleBlock`, `text_kind=attdef`, `attribute_tag=ATTDEF_TAG` |

CADGameFusion PR #436 CI passed:

- validate-samples
- solve unit tests and `/solve-cadgf` smoke
- Build Core on Ubuntu / macOS / Windows
- Core Strict build on Ubuntu / macOS / Windows
- Exports, Validation & Comparison
- Qt Tests (Ubuntu)
- Local CI (Ubuntu)
- quick-check

## Boundary

This closes the **provenance-observability** hole for G11 title-block text. It
does not by itself improve the current G11 X3 score and must not be reported as
a visual-fidelity fix.

The current G11 comparison still has the view-space contract issue recorded in
`docs/VEMCAD_G11_VIEWSPACE_CONTRACT_20260628.md`:

- the AutoCAD reference and VemCAD candidate are not in the same page-fill /
  view-space relationship;
- the diagnostic X3 score remains useful for localization, not for an
  equivalence verdict.

## Next Use

The next G11 text/layout investigation can now read `text_placement.records[]`
and split visible title-block text by:

- `source_type`
- `block_name`
- `text_kind`
- `attribute_tag`
- text-style and resolved-font fields

Any future renderer correction should use this entity-level evidence first,
then rerun G11 under a matched view-space contract before claiming AutoCAD
equivalence.
