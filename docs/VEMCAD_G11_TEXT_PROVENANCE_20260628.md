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

VemCAD main `render-image` passed after the gitlink bump and pushed the rebuilt
`ghcr.io/zensgit/vemcad-render:main` image. The rebuilt image was then used to
rerender the existing G11/B11 fixture:

```bash
docker run --rm \
  -v /tmp/vacadbatchinputs:/in:ro \
  -v /tmp/vemcad-fidelity-out/g11_text_provenance_20260628T120605:/out \
  --entrypoint render_cli ghcr.io/zensgit/vemcad-render:main \
  --input /in/B11.dxf \
  --out /out/G11_ours.png \
  --bg white \
  --width 2339 --height 1653 \
  --report /out/G11_report.json \
  --class-mask-out /out/G11_semantic_mask.png
```

Observed report:

```text
schema_version            0.4
text_records              39
insert_records            16
nonempty_block_name       30
nonempty_text_kind        39
nonempty_attribute_tag    11
```

Top G11 text-provenance buckets:

| `source_type` | `text_kind` | `block_name` | has `attribute_tag` | count |
| --- | --- | --- | --- | ---: |
| `INSERT` | `text` | `HC_BTL_BLK` | no | 12 |
| `(empty)` | `attrib` | `(empty)` | yes | 8 |
| `INSERT` | `attdef` | `HC_BTL_BLK` | yes | 3 |
| `(empty)` | `mtext` | `(empty)` | no | 1 |
| `DIMENSION` | `mtext` | `*D19`...`*D26` | no | 8 |

This proves the live G11 report now distinguishes the visible title-block text
paths that were previously collapsed to generic `insert_text` / empty
`text_kind` records.

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
