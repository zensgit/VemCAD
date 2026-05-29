# VemCAD Router Contract

## 1. Purpose

This document defines the minimum product-layer HTTP contract for Router.

Goal:
- local desktop Router and remote deployed Router share the same request / response shape
- product clients depend on stable HTTP semantics instead of current converter implementation details

In scope:
- `GET /health`
- `POST /convert`
- `GET /status/{task_id}`
- `GET /manifest/{task_id}`
- history / list endpoints
- common error model

Out of scope:
- importer plugin path layout
- converter CLI path layout
- output directory naming
- repo-internal artifact storage details

## 2. Cross-Cutting Rules

### 2.1 Transport

- JSON responses use `application/json; charset=utf-8`.
- `POST /convert` uses `multipart/form-data`.
- Timestamps use RFC 3339 UTC, for example `2026-04-22T08:30:00Z`.
- `task_id` and `document_id` are opaque strings. Clients must not decode or construct them.
- URL fields such as `status_url`, `manifest_url`, `viewer_url`, and `artifact_urls.*` may be absolute or root-relative. Clients must treat them as opaque fetch targets.

### 2.2 Auth

- Deployments may require `Authorization: Bearer <token>` on every endpoint except `GET /health`.
- If auth is enabled and the token is missing or invalid, the server returns `401` with `error_code = "AUTH_REQUIRED"`.

### 2.3 Response Envelope

All JSON endpoints except the raw manifest body use the same top-level envelope:

Successful response:

```json
{
  "status": "ok"
}
```

Error response:

```json
{
  "status": "error",
  "error_code": "TASK_NOT_FOUND",
  "error": "task not found"
}
```

Rules:
- Clients should branch on `error_code`, not on human-readable `error`.
- Servers may add `message`, `details`, and `request_id`.
- Unknown fields are forward-compatible and must be ignored by clients.

### 2.4 Task State Model

`state` is one of:
- `queued`
- `running`
- `done`
- `error`

State rules:
- `queued` and `running` are non-terminal.
- `done` and `error` are terminal.
- Only terminal tasks may expose a final manifest.

## 3. Endpoints

### 3.1 `GET /health`

Purpose:
- liveness and readiness
- expose contract metadata and stable error code inventory

`200 OK`

```json
{
  "status": "ok",
  "service": "router",
  "ready": true,
  "time": "2026-04-22T08:30:00Z",
  "uptime_seconds": 913,
  "contract_version": "router-2026-04-22",
  "error_codes": [
    "AUTH_REQUIRED",
    "CONVERT_FAILED",
    "INVALID_BODY",
    "MANIFEST_MISSING",
    "MISSING_FILE",
    "PAYLOAD_TOO_LARGE",
    "QUEUE_FULL",
    "TASK_NOT_FOUND",
    "TASK_NOT_READY",
    "UNKNOWN_ENDPOINT"
  ]
}
```

Required fields:
- `status`
- `service`
- `ready`
- `time`
- `error_codes`

Optional fields:
- `uptime_seconds`
- `contract_version`
- `version`
- `commit`
- `build_time`
- `hostname`

### 3.2 `POST /convert`

Purpose:
- submit a conversion job
- optionally wait for completion if the deployment supports synchronous waiting

Content type:
- `multipart/form-data`

Required form fields:
- `file`: source CAD file payload

Stable optional form fields:
- `project_id`: product project identity; if omitted, the server may normalize to `unassigned`
- `document_label`: product document label; if omitted, the server may derive it from filename
- `owner`: owner or actor label
- `tags`: comma-separated tag list
- `revision_note`: free-form revision summary
- `emit`: comma-separated outputs from `json`, `gltf`, `meta`
- `wait`: `true|false`; when `true`, the server may hold the request open briefly
- `wait_timeout`: seconds to wait before falling back to `202`

Implementation-specific fields may exist, but product clients must not depend on them.

`202 Accepted`

```json
{
  "status": "ok",
  "task_id": "tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "state": "queued",
  "status_url": "/status/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2"
}
```

`200 OK` when the task finishes within the wait window:

```json
{
  "status": "ok",
  "task_id": "tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "state": "done",
  "document_id": "doc_01JSE2S7DMH2D1N5V6Q7P8R9S0",
  "status_url": "/status/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "manifest_url": "/manifest/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "viewer_url": "/tools/web_viewer/index.html?task_id=tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "artifact_urls": {
    "document_json": "/artifacts/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2/document.json",
    "mesh_gltf": "/artifacts/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2/mesh.gltf",
    "mesh_metadata": "/artifacts/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2/mesh_metadata.json"
  }
}
```

Contract notes:
- `status_url` is always required.
- `manifest_url`, `document_id`, and `artifact_urls` are required once `state = "done"`.
- `viewer_url` is optional.
- During migration, servers may also inline `manifest` in the `done` response. Clients should prefer `manifest_url` when present.
- If the task reaches terminal failure inside the wait window, the server may return `5xx` with the common error envelope.

### 3.3 `GET /status/{task_id}`

Purpose:
- poll task progress
- read terminal result metadata without fetching the manifest body

`200 OK`, non-terminal:

```json
{
  "status": "ok",
  "task_id": "tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "state": "running",
  "created_at": "2026-04-22T08:30:00Z",
  "started_at": "2026-04-22T08:30:01Z",
  "finished_at": null,
  "status_url": "/status/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2"
}
```

`200 OK`, terminal success:

```json
{
  "status": "ok",
  "task_id": "tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "state": "done",
  "created_at": "2026-04-22T08:30:00Z",
  "started_at": "2026-04-22T08:30:01Z",
  "finished_at": "2026-04-22T08:30:04Z",
  "document_id": "doc_01JSE2S7DMH2D1N5V6Q7P8R9S0",
  "status_url": "/status/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "manifest_url": "/manifest/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "viewer_url": "/tools/web_viewer/index.html?task_id=tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "artifact_urls": {
    "document_json": "/artifacts/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2/document.json",
    "mesh_gltf": "/artifacts/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2/mesh.gltf",
    "mesh_metadata": "/artifacts/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2/mesh_metadata.json"
  }
}
```

`200 OK`, terminal failure:

```json
{
  "status": "ok",
  "task_id": "tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "state": "error",
  "created_at": "2026-04-22T08:30:00Z",
  "started_at": "2026-04-22T08:30:01Z",
  "finished_at": "2026-04-22T08:30:02Z",
  "status_url": "/status/tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "error_code": "CONVERT_FAILED",
  "error": "conversion failed"
}
```

Required fields:
- `status`
- `task_id`
- `state`
- `status_url`

Optional progress fields:
- `created_at`
- `started_at`
- `finished_at`

Terminal success fields:
- `document_id`
- `manifest_url`
- `artifact_urls`
- `viewer_url`

Terminal failure fields:
- `error_code`
- `error`

### 3.4 `GET /manifest/{task_id}`

Purpose:
- return the canonical artifact manifest for a completed conversion task

Success response is the raw manifest JSON body, not an outer envelope.
The `status` field inside the manifest is manifest metadata, not the common response envelope.

`200 OK`

```json
{
  "schema_version": "1",
  "status": "ok",
  "generated_at": "2026-04-22T08:30:04Z",
  "project_id": "demo-project",
  "document_label": "sample.dxf",
  "document_id": "doc_01JSE2S7DMH2D1N5V6Q7P8R9S0",
  "artifacts": {
    "document_json": "document.json",
    "mesh_gltf": "mesh.gltf",
    "mesh_bin": "mesh.bin",
    "mesh_metadata": "mesh_metadata.json"
  },
  "outputs": [
    "json",
    "gltf",
    "meta"
  ],
  "warnings": []
}
```

Manifest rules:
- `schema_version`, `status`, `generated_at`, `document_id`, and `artifacts` are required.
- `project_id` and `document_label` should be present after normalization.
- `artifacts` maps logical artifact keys to manifest-local filenames or relative paths.
- Servers may add converter metadata such as hashes, sizes, source metadata, schema version, and tool versions.
- Clients must ignore manifest fields they do not understand.

Error cases:
- `404 TASK_NOT_FOUND`: unknown task id
- `409 TASK_NOT_READY`: task exists but is not yet `done`
- `500 MANIFEST_MISSING`: task ended but no readable manifest exists

### 3.5 History / List Endpoints

These endpoints provide product-readable history and list views over normalized Router records.

Common response envelope:

```json
{
  "status": "ok",
  "count": 1,
  "items": []
}
```

#### `GET /history`

Purpose:
- append-only event feed across convert and annotation activity

Query parameters:
- `limit`
- `project_id`
- `state`
- `event`
- `from`
- `to`
- `owner`
- `tags`
- `revision`

`items[]` entry shape:

```json
{
  "task_id": "tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "event": "convert",
  "state": "done",
  "project_id": "demo-project",
  "document_label": "sample.dxf",
  "created_at": "2026-04-22T08:30:00Z",
  "started_at": "2026-04-22T08:30:01Z",
  "finished_at": "2026-04-22T08:30:04Z",
  "owner": "alice",
  "tags": [
    "release-candidate",
    "import"
  ],
  "revision_note": "initial import",
  "viewer_url": "/tools/web_viewer/index.html?task_id=tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "error": null,
  "error_code": null,
  "annotations": []
}
```

Required history fields:
- `task_id`
- `event`
- `state`
- `project_id`
- `document_label`
- `created_at`
- `tags`
- `annotations`

`event` is currently:
- `convert`
- `annotation`

#### `GET /projects`

Purpose:
- project-level rollup list

Query parameters:
- `limit`
- `owner`
- `tags`
- `revision`
- `event`

`items[]` entry shape:

```json
{
  "project_id": "demo-project",
  "latest_task_id": "tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "latest_state": "done",
  "last_activity": "2026-04-22T08:30:00Z",
  "document_count": 1,
  "owner": "alice",
  "tags": [
    "release-candidate"
  ],
  "revision_note": "initial import",
  "annotation_count": 0,
  "latest_annotation": null
}
```

#### `GET /projects/{project_id}/documents`

Purpose:
- document list within one project

Query parameters:
- `limit`
- `owner`
- `tags`
- `revision`
- `event`

`items[]` entry shape:

```json
{
  "document_id": "doc_01JSE2S7DMH2D1N5V6Q7P8R9S0",
  "document_label": "sample.dxf",
  "project_id": "demo-project",
  "latest_task_id": "tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "latest_state": "done",
  "last_activity": "2026-04-22T08:30:00Z",
  "latest_viewer_url": "/tools/web_viewer/index.html?task_id=tsk_01JSE2S4H6T4S7QYQ4Q9A7N8B2",
  "owner": "alice",
  "tags": [
    "release-candidate"
  ],
  "revision_note": "initial import",
  "annotation_count": 0,
  "latest_annotation": null,
  "version_count": 1
}
```

#### `GET /documents/{document_id}/versions`

Purpose:
- chronological version history for one normalized document identity

Query parameters:
- `limit`
- `state`
- `event`
- `from`
- `to`
- `owner`
- `tags`
- `revision`

Response item shape:
- same structure as `GET /history`

## 4. Error Model

### 4.1 Stable Error Envelope

```json
{
  "status": "error",
  "error_code": "QUEUE_FULL",
  "error": "queue full",
  "request_id": "req_01JSE2V6A5QQ4Q7X9Q3M6NN6XB"
}
```

Required fields:
- `status = "error"`
- `error_code`
- `error`

Optional fields:
- `message`
- `details`
- `request_id`

### 4.2 Minimum Error Code Set

Product clients must handle at least:

| error_code | Typical HTTP status | Meaning |
| --- | --- | --- |
| `AUTH_REQUIRED` | `401` | Missing or invalid bearer token. |
| `INVALID_BODY` | `400` | Request body or form fields could not be parsed. |
| `MISSING_FILE` | `400` | `POST /convert` did not include a file part. |
| `PAYLOAD_TOO_LARGE` | `413` | Upload exceeds router limit. |
| `QUEUE_FULL` | `429` | Router accepted the request shape but cannot enqueue more work. |
| `TASK_NOT_FOUND` | `404` | Unknown `task_id`. |
| `TASK_NOT_READY` | `409` | Task exists but requested terminal artifact is not ready yet. |
| `INVALID_DOCUMENT_ID` | `400` | Malformed or unsupported document id. |
| `MISSING_PROJECT_ID` | `400` | Project-scoped list endpoint omitted its path identity. |
| `CONVERT_FAILED` | `500` | Conversion ended in a terminal failure. |
| `MANIFEST_MISSING` | `500` | Conversion completed but no readable manifest exists. |
| `UNKNOWN_ENDPOINT` | `404` | Unsupported route or method. |

Servers may emit more specific error codes. Clients must treat unknown codes as non-retryable unless the HTTP status and product flow say otherwise.

### 4.3 Retry Guidance

- Safe to retry:
  - `QUEUE_FULL`
  - transient `5xx` without client-side validation failure
- Do not retry unchanged input:
  - `INVALID_BODY`
  - `MISSING_FILE`
  - `INVALID_DOCUMENT_ID`
  - `AUTH_REQUIRED`

## 5. Compatibility Notes

- This document is the product-facing contract source of truth for `services/router`.
- The current reference implementation under `deps/cadgamefusion/tools/plm_router_service.py` may expose extra fields or temporarily inline `manifest` in `POST /convert` and `GET /status/{task_id}` results.
- Clients should consume only the fields defined here and ignore the rest.
