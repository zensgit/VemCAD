# VemCAD Render Service Contract (A7)

Status: v0.1 (2026-06-12) — describes the merged Phase-1 service
(`services/render/`, VemCAD #63/#64/#66/#67). Style follows
`VEMCAD_ROUTER_CONTRACT.md`.
Related: `VEMCAD_CAD_PACKAGE_CONTRACT.md` (the `cad_package` the validator
checks), `VEMCAD_RENDER_SERVICE_PHASE1_DEVELOPMENT_20260610.md` (plan A2a/A3/A4/A5).

## 1. Purpose

Defines the HTTP contract of the render service so consumers (PLM thumbnails /
previews, the regression harness, future Yuantus integration) depend on stable
semantics, not implementation details.

In scope: `GET /healthz`, `POST /render`, `POST /package`,
`GET /package/{id}/report`; the error model; cache semantics; the validator's
capability ceiling; the render report schema; recorded deviations.

Out of scope: render_cli flags/layout, the cache directory layout, the package
store layout, the A6 image internals.

## 2. Cross-cutting rules

- JSON responses are `application/json; charset=utf-8`. `POST /render` and
  `POST /package` use `multipart/form-data`.
- **Security posture (Phase 1)**: internal-network bind only, **no auth**,
  back-pressure via `429`. Authentication is deferred to the Yuantus
  integration phase. The image is non-production (CI artifact + dev compose);
  nothing points production traffic at it.
- All payloads (DXF, fonts, PNG, JSON) are untrusted and are parsed only inside
  the render sandbox (timeout, RLIMIT, private tempdir, minimal env; Linux:
  `--network none`; macOS dev: `sandbox-exec` deny-network, recorded).
- Error envelope — **every** error, including framework request-validation,
  uses one shape:

```json
{ "status": "error", "error_code": "BAD_PARAMS", "error": "human message" }
```

| error_code | HTTP | Endpoint(s) | Meaning |
|---|---|---|---|
| `BAD_PARAMS` | 422 | /render, /package | invalid params, or any framework request-validation failure (the handler is app-wide — e.g. a missing `manifest` part on /package) |
| `EMPTY_INPUT` | 422 | /render | empty upload, or neither file nor package_id |
| `UNSUPPORTED_INPUT` | 415 | /render | `.dwg` upload (v0 accepts DXF only) |
| `PAYLOAD_TOO_LARGE` | 413 | /render, /package | over the upload/package cap |
| `RENDER_FAILED` | 422 | /render | render_cli error / timeout / blank output |
| `BUSY` | 429 | /render | worker pool saturated, retry later |
| `BAD_MANIFEST` | 422 | /package | manifest is not valid JSON |
| `PACKAGE_REJECTED` | 422 | /package | unparseable / unknown-major / identity-broken manifest (the only outright rejection) |
| `IDENTITY_CONFLICT` | 409 | /package | package_id already bound to a different identity |
| `PACKAGE_NOT_FOUND` | 404 | /package/{id}/report, /render | no such package_id |
| `PAYLOAD_NOT_FOUND` | 404 | /render | package has no renderable payload for the role |
| `ROLE_NOT_RENDERABLE` | 404 | /render | role ∉ {twin-dxf, twin-dxf-flattened} |
| `INTERNAL` | 500 | any | unhandled error (caught, enveloped) |

## 3. `GET /healthz`

Returns `200` when ready, **`503` when degraded** (probes/LBs key on the
status code). Body:

```json
{
  "status": "ok",
  "render_cli": {"path": "...", "sha256": "...", "available": true,
                 "smoke": {"ok": true, "bytes": 4958}},
  "fonts": {"dir": null, "count": 0, "fingerprint": "no-fonts"},
  "workers": {"max": 2, "active": 0}
}
```

`render_cli.smoke` is the startup render of a built-in synthetic drawing (with
a TEXT entity, so a broken offscreen/font runtime collapses the size); a
suspiciously small output sets `ok=false` → `status:degraded` → `503`.

## 4. `POST /render`

Two input modes, mutually exclusive:
- **direct**: multipart field `file` = a **DXF** (`.dwg` → `415`).
- **package-ref**: query `package_id` + `role` (∈ `twin-dxf` /
  `twin-dxf-flattened`; other roles `404 ROLE_NOT_RENDERABLE`); renders that
  stored payload, skipping any payload the validator quarantined.

Query params (both modes):

| param | default | constraint |
|---|---|---|
| `format` | `png` | `png` \| `svg` |
| `width`, `height` | 2400, 1697 | each 16..8192, and `width*height ≤ 64 MP` |
| `bg` | `dark` | `dark` \| `white` \| `#RRGGBB` |
| `view` | `extents` | `extents` only in v0 |

Direct-upload cap: **48 MiB** (`RENDER_MAX_UPLOAD_BYTES`), independent of the
contract §2.4 package ceilings. Over → `413`.

Success → `200` with the image bytes (`image/png` or `image/svg+xml`) and:
- `X-Render-Cache: hit | miss`
- `X-Render-Key: <cache key>`

**Thumbnails** are `/render` with small `width`/`height` — there is **no
separate `/thumbnail` endpoint** in v0; a thin `GET /thumbnail` alias may be
added during Yuantus integration.

### 4.1 Cache key (normative)

A render is content-addressed by a **four-tuple**, JSON-canonicalised
(sorted keys, no whitespace) then sha256:

```
( content_sha256,                      # sha256 of the input DXF bytes
  params,                              # {format,width,height,bg,view}
  render_cli_version,                  # sha256 of the render_cli binary
  font_store_fingerprint )             # sha256 over the font dir (name+hash), or "no-fonts"
```

The renderer-version and font components exist from day one so a render_cli
upgrade or a font-set change can never serve stale pixels. A cache hit serves
the prior artifact on the same `/render` endpoint (fast path) — there is no
separate cache route. (Plan wording "render_cli 版本即子模块 SHA": the runtime
canonical is the **binary sha256**, which also covers worktree-dev binaries.)

### 4.2 Render report sidecar

Each cached artifact has a `<key>.report.json` (`vemcad.render_service_report`):
service params, `content_sha256`, `render_cli_sha256`, `font_dir`,
`font_fingerprint`, `duration_s`, `network_isolated`, `render_cli_stdout`, and
the embedded **`render_cli_report`** (B1's `vemcad.render_report`: view
scale/pan/clip + `y_axis`/viewport, entity/text counts, two-layer font
records). On a cache hit the sidecar is not regenerated.

## 5. `POST /package` + `GET /package/{id}/report`

`POST /package`: multipart `manifest` (the `cad_package.json`) + zero or more
`payload` parts. Validates per `VEMCAD_CAD_PACKAGE_CONTRACT.md` §9 and stores.
Package total cap **1 GiB** (over → `413`). Returns `200` with the validation
report + `status:"ok"` + `upsert:{identity,superseded_by_existing}`, **except**
an unparseable/unknown-major/identity-broken manifest → `422 PACKAGE_REJECTED`
(the only outright rejection — package *quality* never blocks ingestion).

`GET /package/{id}/report` returns the stored validation report (`404` if absent).

### 5.1 Validation report schema (`vemcad.package_validation_report`)

```json
{
  "schema": "vemcad.package_validation_report", "schema_version": "0.1",
  "package_id": "...", "claimed_level": "standard",
  "validated_level": "standard",
  "warnings": [{"code": "...", "message": "...", "...": "..."}],
  "quarantined": [{"role": "...", "sha256": "...", "file_name": "...", "reason": "..."}],
  "incomplete_preview": false,
  "notes_echo": [],
  "error": null
}
```

### 5.2 Validator capability ceiling (A4, Phase 1)

- **2D only, up to `standard`.** `rich` is **never granted** (warns
  `rich-not-granted-v0`); a `3d-*` discipline is stored with an
  `3d-not-supported-v0` note and validated at `source-only`.
- Levels: `source-only` (floor) → `minimal` (well-formed metadata) →
  `standard` (+ `twin-dxf` + ≥1 §7-conforming `ref-render`). Per-payload
  quarantine (sha256/size/format-sniff and the §2.4 ceilings: ≤256 entries,
  ≤512 MiB/payload, ≤64 MP raster, missing `size_bytes`). ref-render §7 gate:
  view ∈ extents/layout, long edge ≥1600, `#RRGGBB` background (white required
  on offscreen-render/plot-raster), valid capture_method + captured_at_event.
- Identity (`cad_package` §2.2): key = (tenant, source.sha256, plugin_name,
  host_app, schema_major); **fixed default tenant** in v0; upsert never moves
  the `latest` pointer to a lower `plugin_version`; cross-identity reuse of a
  `package_id` → `409`.

## 6. Recorded deviations

This is the authoritative superset; `services/render/README.md` records #1–#2,
the rest are added here (keep the two in sync on change).

1. **Completeness / pending-TTL simplification** — `cad_package` §2.1 envisages
   "payloads incomplete → pending state + TTL". v0 quarantines a missing
   payload immediately and finalizes; same-identity re-submission upserts. No
   pending/TTL state machine.
2. **Package total 1 GiB is a `413` rejection** (transport guard), not a
   per-entry quarantine; per-entry §2.4 caps (256 / 512 MiB / 64 MP) ARE
   quarantine.
3. **`--font-dir` / `--report`** are wired (A5/B1 merged); a pre-B1 render_cli
   silently omits them.
4. **incomplete-preview** flags `resolved:false` external refs AND the
   freeze-addendum case (`resolved:true` `dwg-xref` with no uploaded
   `xref-dxf`).
5. Relation to `services/router`: that precedent is contract-docs-only with the
   impl in the submodule; this service keeps its impl in VemCAD `services/render/`.

## 7. Versioning

v0.x additive; consumers ignore unknown JSON fields. A breaking change to an
endpoint/field/error-code bumps to v1 with a migration note here.
