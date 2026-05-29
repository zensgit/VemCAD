# VemCAD DXF ACAD_PROXY_ENTITY Rendering — Technical Evaluation

Date: 2026-05-15
Scope: the last known real fidelity gap vs AutoCAD 2026 in the DXF/DWG viewer
(`cadgamefusion editor_qt`) — serial-number balloons/leaders that do not render.
Decision requested: how to close it, and whether the ODA SDK is warranted.

## 1. Conclusion First

**Do NOT integrate the ODA SDK for this.** It is unnecessary and disproportionate.
The missing content is fully described by the standard *proxy entity graphics*
cache already embedded in the file. Recommended path: **Option B (ezdxf
pre-explode preprocessor)** for a fast, low-risk fix now; **Option A (in-house
C++ subset parser)** as the clean long-term native solution if a runtime Python
dependency is unacceptable. Both are bounded; neither needs ODA.

## 2. Evidence (test drawing: BTJ01231501522-00 短轴承座(盖)v2.dxf)

- DXF AC1032 (R2018). Modelspace contains exactly **4 `ACAD_PROXY_ENTITY`**,
  all on layer `YGJ细实线`.
- **All 4 carry a proxy-graphics cache** (464 / 464 / 464 / 324 bytes,
  DXF group codes 92 = byte count, 310 = binary data).
- Decoded (via ezdxf `ProxyGraphic.virtual_entities()`) they are the
  **serial-number balloons 1, 2, 3, 4** linking parts to the BOM:
  - e.g. serial "3": 2 concentric `CIRCLE` (arrow dot) at (387.0,1149.3)
    r=1.5/0.75; `POLYLINE` (387.0,1149.3)→(479.5,1378.0) leader;
    `POLYLINE` (479.5,1378.0)→(448.0,1378.0) landing; `TEXT "3"`
    at (458.0,1383.3) h=26.25.
- Coordinates are already in model space (within
  `$EXTMIN`(-125,-25) … `$EXTMAX`(1975,1460)) — render directly, no transform.
- **Opcode set across all 4 proxies is only `CIRCLE`, `POLYLINE`, `TEXT`** —
  a tiny subset of the proxy-graphics format.

## 3. Why It Currently Fails

`libdxfrw` carries `numProxyGraph` (code 92) / `proxyGraphics` (code 310) on the
`DRW_Entity` base, but `ACAD_PROXY_ENTITY` is **not in its parsed-entity enum**
(`deps/libdxfrw/src/drw_entities.h:32`, commented out). libdxfrw skips the
entity entirely, so `CadgfDrwAdapter` never receives a callback and the cached
bytes are discarded. This is a parser-coverage gap, not a format limitation.

## 4. Options

| Option | What | Effort | New runtime dep | Risk | Native/clean |
|---|---|---|---|---|---|
| ODA SDK | Commercial Teigha/ODA libraries | High | Large native libs + license | Licensing, binary size, build | Overkill |
| **A: in-house C++** | Patch libdxfrw to surface ACAD_PROXY_ENTITY + emit code 92/310; write a proxy-graphics opcode parser for the **CIRCLE/POLYLINE/TEXT subset** in the adapter | Medium | None | Bounded (3 opcodes) | Yes |
| **B: ezdxf preprocess** | On import, a Python/ezdxf step rewrites each `ACAD_PROXY_ENTITY` as its `virtual_entities()` (real LINE/CIRCLE/TEXT) into a temp DXF, then feed libdxfrw | Low | Python + ezdxf on import path | Low (decoder already proven on this file) | Adds Python at runtime |
| C: ODA File Converter | Free external converter to pre-explode | Low–Med | External binary | Bundling/path/platform | External process |

## 5. Cost / Benefit

- ODA SDK: licensing cost + tens of MB of native libraries + build/integration
  to render 4 simple primitives that are already in the file as plain
  circle/line/text. Rejected.
- Option A: ~one focused change set — (1) a minimal libdxfrw patch (recognize
  ACAD_PROXY_ENTITY, expose code 92/310 to `DRW_Interface`), (2) a C++ parser
  for the proxy-graphics opcodes actually used (polyline, circle, text, plus
  color/layer attribute opcodes). Self-contained, no new deps, matches the
  existing native plugin architecture. Effort concentrated in the binary
  opcode parser; format is documented (ODA spec, mirrored by ezdxf
  `proxygraphic.py`).
- Option B: smallest, fastest, lowest-risk — the ezdxf decoder is already
  proven correct on the target file in this evaluation. Cost is an
  import-path dependency on Python+ezdxf (already a dev/verification
  dependency, not yet a runtime one).

## 6. Recommendation

1. **Reject ODA SDK.**
2. **Now:** implement **Option B** to close the visible gap quickly and
   reversibly (preprocessor isolated to the import path; trivially removable).
3. **Long-term:** if the product must stay free of a runtime Python
   dependency, schedule **Option A** — bounded because only CIRCLE/POLYLINE/TEXT
   opcodes are required in practice; reuse ezdxf `proxygraphic.py` as the
   reference implementation.
4. Keep this isolated from the committed text/linetype/lineweight fidelity work
   (branch `fix/dxf-text-linetype-lineweight-fidelity`, commit `50feab2`).

## 7. Status of the Rest of the Drawing

Text (font face + size), linetype, lineweight, HATCH density, arrowheads, and
overall 7-view layout were verified against the AutoCAD 2026 reference and
match (~90%+). After proxy balloons are rendered there is no other known real
gap in this drawing.
