#!/usr/bin/env python3
"""Route AutoCAD reference artifact indexes to the next safe operator action."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "vemcad.acad_artifact_route/v1"
BATCH_SCHEMA = "vemcad.acad_artifact_route_batch/v1"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"could not read artifact index {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"artifact index {path} must be a JSON object")
    return payload


def _resolve_artifact_index(path: Path) -> Path:
    if path.is_dir():
        path = path / "artifact_index.json"
    if not path.is_file():
        raise ValueError(f"artifact index not found: {path}")
    return path


def _discover_artifact_indexes(paths: list[Path]) -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path.is_dir():
            candidates = sorted(path.rglob("artifact_index.json"))
        else:
            candidates = [_resolve_artifact_index(path)]
        if not candidates:
            raise ValueError(f"no artifact indexes found recursively under: {path}")
        for candidate in candidates:
            key = candidate.resolve()
            if key in seen:
                continue
            seen.add(key)
            discovered.append(candidate)
    if not discovered:
        raise ValueError("at least one artifact index is required")
    return discovered


def _action(code: str, message: str, *, artifact: str = "") -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "artifact": artifact,
    }


def _route_batch(payload: dict[str, Any]) -> dict[str, Any]:
    stage = str(payload.get("stage") or "")
    status = str(payload.get("status") or "")
    if status == "blocked" and stage == "request_validation":
        action = _action(
            "fix-request-package",
            "Fix request-package provenance or structure before exporting or returning AutoCAD PNGs.",
        )
    elif status == "blocked" and stage == "missing_references":
        action = _action(
            "provide-returned-autocad-pngs",
            "Place the returned AutoCAD PNGs using the requested filenames, then rerun the wrapper.",
        )
    elif status == "blocked":
        action = _action(
            "inspect-input-block",
            "Inspect batch artifacts before continuing to matched-view comparison.",
        )
    elif status == "review":
        action = _action(
            "inspect-returned-reference-warnings",
            "Inspect returned-reference intake warnings before trusting visual conclusions.",
        )
    elif status == "pass":
        action = _action(
            "continue-to-request-run",
            "Continue to the request runner or matched-view comparison.",
        )
    else:
        action = _action(
            "inspect-artifact-index",
            "Inspect the batch artifact index before choosing the next action.",
        )
    return {
        "kind": "batch",
        "status": status,
        "stage": stage,
        "case_count": payload.get("case_count"),
        "recommended_next_action": action,
    }


def _route_run(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "request_run",
        "status": str(payload.get("status") or ""),
        "case_action_counts": payload.get("case_action_counts") or {},
        "case_actions": payload.get("case_actions") or [],
        "recommended_next_action": payload.get("recommended_next_action") or _action(
            "inspect-run-summary",
            "Inspect the run summary before choosing the next action.",
        ),
    }


def _route_compare(payload: dict[str, Any]) -> dict[str, Any]:
    triage = payload.get("triage_bucket_counts") or {}
    status = str(payload.get("status") or "")
    if triage.get("renderer-candidate"):
        action = _action(
            "inspect-renderer-candidate",
            "Matched-view X3 has renderer candidates; inspect overlays and isolate concrete renderer defects.",
        )
    elif triage.get("recapture-required"):
        action = _action(
            "recapture-autocad-or-provide-window",
            "Recapture AutoCAD at matched model extents or provide the real world window; do not tune the renderer.",
        )
    elif status == "pass":
        action = _action(
            "review-x3-pass",
            "Matched-view X3 passed; no renderer work unless manual review finds a concrete defect.",
        )
    elif status == "blocked":
        action = _action(
            "inspect-compare-input-block",
            "Inspect compare input issues before changing renderer code.",
        )
    else:
        action = _action(
            "inspect-compare-summary",
            "Inspect compare summary and artifacts before choosing the next action.",
        )
    return {
        "kind": "compare",
        "status": status,
        "case_count": payload.get("case_count"),
        "compared_count": payload.get("compared_count"),
        "triage_bucket_counts": triage,
        "viewspace_status_counts": payload.get("viewspace_status_counts") or {},
        "x3_band_counts": payload.get("x3_band_counts") or {},
        "recommended_next_action": action,
    }


def route_artifact_index(path: Path) -> dict[str, Any]:
    path = _resolve_artifact_index(path)
    payload = _read_json(path)
    schema = str(payload.get("schema") or "")
    if schema == "vemcad.acad_reference_batch_artifact_index/v1":
        route = _route_batch(payload)
    elif schema == "vemcad.acad_reference_request_run_artifact_index/v1":
        route = _route_run(payload)
    elif schema == "vemcad.acad_manifest_compare_artifact_index/v1":
        route = _route_compare(payload)
    else:
        raise ValueError(f"unsupported artifact index schema: {schema or '<missing>'}")
    return {
        "schema": SCHEMA,
        "artifact_index": str(path),
        "artifact_index_schema": schema,
        **route,
    }


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = value or "<missing>"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _route_batch_summary(routes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind_counts": _count_values([str(route.get("kind") or "") for route in routes]),
        "status_counts": _count_values([str(route.get("status") or "") for route in routes]),
        "recommended_action_counts": _count_values([
            str((route.get("recommended_next_action") or {}).get("code") or "") for route in routes
        ]),
    }


def route_artifact_indexes(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one artifact index is required")
    routes = [route_artifact_index(path) for path in paths]
    return {
        "schema": BATCH_SCHEMA,
        "count": len(routes),
        **_route_batch_summary(routes),
        "routes": routes,
    }


def _format_counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _write_text(route: dict[str, Any]) -> str:
    action = route.get("recommended_next_action") or {}
    lines = [
        f"kind: {route.get('kind', '')}",
        f"status: {route.get('status', '')}",
        f"recommended_next_action: {action.get('code', '')}",
        f"message: {action.get('message', '')}",
    ]
    if route.get("case_action_counts"):
        lines.append(f"case_action_counts: {_format_counts(route['case_action_counts'])}")
    if route.get("triage_bucket_counts"):
        lines.append(f"triage_bucket_counts: {_format_counts(route['triage_bucket_counts'])}")
    return "\n".join(lines)


def _write_batch_text(payload: dict[str, Any]) -> str:
    chunks = [
        "\n".join([
            f"route_count: {payload.get('count', 0)}",
            "kind_counts: " + _format_counts(payload.get("kind_counts") or {}),
            "status_counts: " + _format_counts(payload.get("status_counts") or {}),
            "recommended_action_counts: " + _format_counts(payload.get("recommended_action_counts") or {}),
        ])
    ]
    for index, route in enumerate(payload.get("routes") or [], start=1):
        chunks.append("\n".join([
            f"route: {index}",
            f"artifact_index: {route.get('artifact_index', '')}",
            _write_text(route),
        ]))
    return "\n\n".join(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acad_artifact_route",
        description="Read an AutoCAD reference artifact index and print the next safe action.")
    parser.add_argument("artifact_index", type=Path, nargs="+",
                        help="artifact_index.json, or directories containing artifact_index.json")
    parser.add_argument("--recursive", action="store_true",
                        help="discover artifact_index.json files recursively under directory inputs")
    parser.add_argument("--text", action="store_true", help="print a human-readable summary instead of JSON")
    args = parser.parse_args(argv)

    try:
        paths = _discover_artifact_indexes(args.artifact_index) if args.recursive else args.artifact_index
        if len(paths) == 1:
            payload = route_artifact_index(paths[0])
        else:
            payload = route_artifact_indexes(paths)
    except Exception as exc:
        print(f"acad_artifact_route: {exc}", file=sys.stderr)
        return 2
    if args.text:
        if payload.get("schema") == BATCH_SCHEMA:
            print(_write_batch_text(payload))
        else:
            print(_write_text(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
