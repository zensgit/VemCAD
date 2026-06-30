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
BOUNDARY = {
    "read_only_routing": True,
    "renders_dxf": False,
    "compares_renders": False,
    "changes_x3_scoring": False,
    "changes_renderer": False,
    "autocad_equivalence_claim": False,
}

ACTION_DOMAINS = {
    "fix-request-package": "input",
    "provide-returned-autocad-pngs": "input",
    "inspect-input-block": "input",
    "inspect-compare-input-block": "input",
    "recapture-autocad-or-provide-window": "input",
    "inspect-returned-reference-warnings": "input-review",
    "inspect-renderer-candidate": "renderer-candidate",
    "inspect-compare-failure": "compare-debug",
    "review-x3-pass": "pass-review",
    "continue-to-request-run": "continue",
    "inspect-run-summary": "inspect",
    "inspect-artifact-index": "inspect",
    "inspect-compare-summary": "inspect",
}


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


def _action_domain(code: str) -> str:
    return ACTION_DOMAINS.get(code, "inspect")


def _action(code: str, message: str, *, artifact: str = "", domain: str = "") -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "artifact": artifact,
        "domain": domain or _action_domain(code),
    }


def _artifact_path(payload: dict[str, Any], kind: str) -> str:
    for item in payload.get("artifacts") or []:
        if isinstance(item, dict) and str(item.get("kind") or "") == kind:
            return str(item.get("path") or "")
    return ""


def _route_action(route: dict[str, Any]) -> dict[str, str]:
    action = route.get("recommended_next_action") or {}
    if isinstance(action, dict):
        code = str(action.get("code") or "")
        return {
            "code": code,
            "message": str(action.get("message") or ""),
            "artifact": str(action.get("artifact") or ""),
            "domain": str(action.get("domain") or _action_domain(code)),
        }
    return {"code": "", "message": "", "artifact": "", "domain": ""}


def _normalize_recommended_action(action: Any, fallback: dict[str, str]) -> dict[str, str]:
    if isinstance(action, dict):
        code = str(action.get("code") or "")
        if code:
            return _route_action({"recommended_next_action": action})
    return fallback


def _route_batch(payload: dict[str, Any]) -> dict[str, Any]:
    stage = str(payload.get("stage") or "")
    status = str(payload.get("status") or "")
    if status == "blocked" and stage == "request_validation":
        action = _action(
            "fix-request-package",
            "Fix request-package provenance or structure before exporting or returning AutoCAD PNGs.",
            artifact=_artifact_path(payload, "reference_request_validation_markdown"),
        )
    elif status == "blocked" and stage == "missing_references":
        action = _action(
            "provide-returned-autocad-pngs",
            "Place the returned AutoCAD PNGs using the requested filenames, then rerun the wrapper.",
            artifact=_artifact_path(payload, "missing_references_markdown"),
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
            artifact=_artifact_path(payload, "reference_intake_markdown"),
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
        "reference_request_validation_issue_code_counts": (
            payload.get("reference_request_validation_issue_code_counts") or {}
        ),
        "reference_intake_issue_code_counts": payload.get("reference_intake_issue_code_counts") or {},
        "recommended_next_action": action,
    }


def _route_run(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "request_run",
        "status": str(payload.get("status") or ""),
        "case_action_counts": payload.get("case_action_counts") or {},
        "case_action_domain_counts": payload.get("case_action_domain_counts") or {},
        "reference_request_validation_issue_code_counts": (
            payload.get("reference_request_validation_issue_code_counts") or {}
        ),
        "reference_intake_issue_code_counts": payload.get("reference_intake_issue_code_counts") or {},
        "case_actions": payload.get("case_actions") or [],
        "recommended_next_action": _normalize_recommended_action(
            payload.get("recommended_next_action"),
            _action(
                "inspect-run-summary",
                "Inspect the run summary before choosing the next action.",
            ),
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


def _artifact_index_boundary(payload: dict[str, Any]) -> dict[str, Any]:
    boundary = payload.get("boundary")
    return dict(boundary) if isinstance(boundary, dict) else {}


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
    return _annotate_action_artifact({
        "schema": SCHEMA,
        "artifact_index": str(path),
        "artifact_index_schema": schema,
        "artifact_index_boundary": _artifact_index_boundary(payload),
        "boundary": dict(BOUNDARY),
        **route,
    })


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = value or "<missing>"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _sum_count_maps(routes: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for route in routes:
        values = route.get(key)
        if not isinstance(values, dict):
            continue
        for code, count in values.items():
            code_text = str(code)
            if not code_text:
                continue
            try:
                count_int = int(count)
            except Exception:
                continue
            counts[code_text] = counts.get(code_text, 0) + count_int
    return dict(sorted(counts.items()))


def _route_batch_summary(routes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind_counts": _count_values([str(route.get("kind") or "") for route in routes]),
        "status_counts": _count_values([str(route.get("status") or "") for route in routes]),
        "recommended_action_counts": _count_values([
            str((route.get("recommended_next_action") or {}).get("code") or "") for route in routes
        ]),
        "recommended_action_domain_counts": _count_values([
            _route_action(route)["domain"] for route in routes
        ]),
        "reference_request_validation_issue_code_counts": _sum_count_maps(
            routes,
            "reference_request_validation_issue_code_counts",
        ),
        "reference_intake_issue_code_counts": _sum_count_maps(
            routes,
            "reference_intake_issue_code_counts",
        ),
    }


_ACTION_PRIORITY = {
    "fix-request-package": 0,
    "provide-returned-autocad-pngs": 1,
    "inspect-returned-reference-warnings": 2,
    "inspect-renderer-candidate": 3,
    "recapture-autocad-or-provide-window": 4,
    "inspect-compare-input-block": 5,
    "inspect-input-block": 5,
    "inspect-compare-failure": 5,
    "inspect-run-summary": 6,
    "inspect-artifact-index": 6,
    "inspect-compare-summary": 6,
    "review-x3-pass": 7,
    "continue-to-request-run": 8,
}


def _recommended_batch_action(routes: list[dict[str, Any]]) -> dict[str, str]:
    if not routes:
        return _action(
            "inspect-artifact-index",
            "Inspect artifact indexes before choosing the next action.",
        )
    ranked: list[tuple[int, int, dict[str, str]]] = []
    for index, route in enumerate(routes):
        action = _route_action(route)
        code = action["code"] or "inspect-artifact-index"
        priority = _ACTION_PRIORITY.get(code, 6)
        ranked.append((priority, index, action))
    priority, index, action = min(ranked, key=lambda item: (item[0], item[1]))
    artifact = action.get("artifact") or str(routes[index].get("artifact_index") or "")
    message = action.get("message") or "Inspect route artifacts before choosing the next action."
    payload = {
        "code": action.get("code") or "inspect-artifact-index",
        "message": message,
        "artifact": artifact,
        "domain": action.get("domain") or _action_domain(action.get("code") or "inspect-artifact-index"),
    }
    source_artifact_index = str(routes[index].get("artifact_index") or "")
    if source_artifact_index:
        payload["source_artifact_index"] = source_artifact_index
        payload["source_route_index"] = str(index + 1)
    return payload


def _recommended_action_artifact(payload: dict[str, Any]) -> str:
    return str((payload.get("recommended_next_action") or {}).get("artifact") or "")


def _recommended_action_source_index(payload: dict[str, Any]) -> str:
    action = payload.get("recommended_next_action") or {}
    source = str(action.get("source_artifact_index") or "")
    if source:
        return source
    if payload.get("schema") != BATCH_SCHEMA:
        return str(payload.get("artifact_index") or "")
    return ""


def _resolve_action_artifact(payload: dict[str, Any]) -> Path | None:
    artifact = _recommended_action_artifact(payload)
    if not artifact:
        return None
    artifact_path = Path(artifact)
    if artifact_path.is_absolute():
        return artifact_path
    source_index = _recommended_action_source_index(payload)
    if source_index:
        if artifact == source_index:
            return Path(artifact).resolve()
        return (Path(source_index).parent / artifact).resolve()
    return artifact_path.resolve()


def _annotate_action_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    artifact = _recommended_action_artifact(payload)
    resolved = _resolve_action_artifact(payload)
    if artifact and resolved is not None:
        payload["action_artifact_resolved"] = str(resolved)
        payload["action_artifact_exists"] = resolved.is_file()
    for route in payload.get("routes") or []:
        if isinstance(route, dict):
            _annotate_action_artifact(route)
    return payload


def route_artifact_indexes(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one artifact index is required")
    routes = [route_artifact_index(path) for path in paths]
    return _annotate_action_artifact({
        "schema": BATCH_SCHEMA,
        "boundary": dict(BOUNDARY),
        "count": len(routes),
        **_route_batch_summary(routes),
        "recommended_next_action": _recommended_batch_action(routes),
        "routes": routes,
    })


def _format_counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _write_text(route: dict[str, Any]) -> str:
    action = route.get("recommended_next_action") or {}
    source_boundary = route.get("artifact_index_boundary") or {}
    lines = [
        f"kind: {route.get('kind', '')}",
        f"status: {route.get('status', '')}",
        f"recommended_next_action: {action.get('code', '')}",
        f"recommended_action_domain: {action.get('domain', '')}",
        f"message: {action.get('message', '')}",
    ]
    if action.get("artifact"):
        lines.append(f"action_artifact: {action.get('artifact', '')}")
    if route.get("action_artifact_resolved"):
        lines.append(f"action_artifact_resolved: {route.get('action_artifact_resolved', '')}")
        lines.append(f"action_artifact_exists: {str(bool(route.get('action_artifact_exists'))).lower()}")
    if source_boundary:
        lines.append(
            "source_artifact_boundary: "
            + ",".join(
                f"{key}={str(bool(value)).lower() if isinstance(value, bool) else value}"
                for key, value in sorted(source_boundary.items())
            )
        )
    if route.get("case_action_counts"):
        lines.append(f"case_action_counts: {_format_counts(route['case_action_counts'])}")
    if route.get("case_action_domain_counts"):
        lines.append(f"case_action_domain_counts: {_format_counts(route['case_action_domain_counts'])}")
    if route.get("reference_request_validation_issue_code_counts"):
        lines.append(
            "reference_request_validation_issue_code_counts: "
            + _format_counts(route["reference_request_validation_issue_code_counts"])
        )
    if route.get("reference_intake_issue_code_counts"):
        lines.append(
            "reference_intake_issue_code_counts: "
            + _format_counts(route["reference_intake_issue_code_counts"])
        )
    if route.get("triage_bucket_counts"):
        lines.append(f"triage_bucket_counts: {_format_counts(route['triage_bucket_counts'])}")
    return "\n".join(lines)


def _write_batch_text(payload: dict[str, Any]) -> str:
    action = payload.get("recommended_next_action") or {}
    boundary = payload.get("boundary") or {}
    summary = [
        f"route_count: {payload.get('count', 0)}",
        "kind_counts: " + _format_counts(payload.get("kind_counts") or {}),
        "status_counts: " + _format_counts(payload.get("status_counts") or {}),
        "recommended_action_counts: " + _format_counts(payload.get("recommended_action_counts") or {}),
        "recommended_action_domain_counts: "
        + _format_counts(payload.get("recommended_action_domain_counts") or {}),
        f"recommended_next_action: {action.get('code', '')}",
        f"recommended_action_domain: {action.get('domain', '')}",
        f"message: {action.get('message', '')}",
        f"action_artifact: {action.get('artifact', '')}",
    ]
    if payload.get("reference_request_validation_issue_code_counts"):
        summary.append(
            "reference_request_validation_issue_code_counts: "
            + _format_counts(payload["reference_request_validation_issue_code_counts"])
        )
    if payload.get("reference_intake_issue_code_counts"):
        summary.append(
            "reference_intake_issue_code_counts: "
            + _format_counts(payload["reference_intake_issue_code_counts"])
        )
    if payload.get("action_artifact_resolved"):
        summary.extend([
            f"action_artifact_resolved: {payload.get('action_artifact_resolved', '')}",
            f"action_artifact_exists: {str(bool(payload.get('action_artifact_exists'))).lower()}",
        ])
    summary.append(
        f"autocad_equivalence_claim: {str(bool(boundary.get('autocad_equivalence_claim'))).lower()}"
    )
    chunks = ["\n".join(summary)]
    for index, route in enumerate(payload.get("routes") or [], start=1):
        chunks.append("\n".join([
            f"route: {index}",
            f"artifact_index: {route.get('artifact_index', '')}",
            _write_text(route),
        ]))
    return "\n\n".join(chunks)


def _write_markdown_route(route: dict[str, Any], *, heading: str) -> str:
    action = _route_action(route)
    boundary = route.get("boundary") or {}
    source_boundary = route.get("artifact_index_boundary") or {}
    lines = [
        f"## {heading}",
        "",
        f"- artifact_index: `{route.get('artifact_index', '')}`",
        f"- kind: `{route.get('kind', '')}`",
        f"- status: `{route.get('status', '')}`",
        f"- recommended_next_action: `{action['code']}`",
        f"- recommended_action_domain: `{action['domain']}`",
        f"- message: {action['message']}",
    ]
    if boundary:
        lines.extend([
            f"- read_only_routing: `{bool(boundary.get('read_only_routing'))}`",
            f"- autocad_equivalence_claim: `{bool(boundary.get('autocad_equivalence_claim'))}`",
        ])
    if source_boundary:
        lines.extend([
            f"- source_compares_renders: `{bool(source_boundary.get('compares_renders'))}`",
            f"- source_autocad_equivalence_claim: `{bool(source_boundary.get('autocad_equivalence_claim'))}`",
        ])
    if action["artifact"]:
        lines.append(f"- action_artifact: `{action['artifact']}`")
    if route.get("action_artifact_resolved"):
        lines.append(f"- action_artifact_resolved: `{route['action_artifact_resolved']}`")
        lines.append(f"- action_artifact_exists: `{bool(route.get('action_artifact_exists'))}`")
    if route.get("case_action_counts"):
        lines.append(f"- case_action_counts: `{_format_counts(route['case_action_counts'])}`")
    if route.get("case_action_domain_counts"):
        lines.append(f"- case_action_domain_counts: `{_format_counts(route['case_action_domain_counts'])}`")
    if route.get("reference_request_validation_issue_code_counts"):
        lines.append(
            "- reference_request_validation_issue_code_counts: "
            f"`{_format_counts(route['reference_request_validation_issue_code_counts'])}`"
        )
    if route.get("reference_intake_issue_code_counts"):
        lines.append(
            "- reference_intake_issue_code_counts: "
            f"`{_format_counts(route['reference_intake_issue_code_counts'])}`"
        )
    if route.get("triage_bucket_counts"):
        lines.append(f"- triage_bucket_counts: `{_format_counts(route['triage_bucket_counts'])}`")
    return "\n".join(lines)


def _write_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# AutoCAD Artifact Route Report",
        "",
        "This report is read-only routing guidance. It does not compare renders,",
        "change X3 scoring, tune the renderer, or claim AutoCAD equivalence.",
        "",
    ]
    if payload.get("schema") == BATCH_SCHEMA:
        action = _route_action(payload)
        boundary = payload.get("boundary") or {}
        lines.extend([
            "## Summary",
            "",
            f"- route_count: `{payload.get('count', 0)}`",
            f"- kind_counts: `{_format_counts(payload.get('kind_counts') or {})}`",
            f"- status_counts: `{_format_counts(payload.get('status_counts') or {})}`",
            "- recommended_action_counts: "
            f"`{_format_counts(payload.get('recommended_action_counts') or {})}`",
            "- recommended_action_domain_counts: "
            f"`{_format_counts(payload.get('recommended_action_domain_counts') or {})}`",
            f"- recommended_next_action: `{action['code']}`",
            f"- recommended_action_domain: `{action['domain']}`",
            f"- message: {action['message']}",
            f"- read_only_routing: `{bool(boundary.get('read_only_routing'))}`",
            f"- autocad_equivalence_claim: `{bool(boundary.get('autocad_equivalence_claim'))}`",
            "",
        ])
        if payload.get("reference_request_validation_issue_code_counts"):
            lines.extend([
                "- reference_request_validation_issue_code_counts: "
                f"`{_format_counts(payload['reference_request_validation_issue_code_counts'])}`",
            ])
        if payload.get("reference_intake_issue_code_counts"):
            lines.extend([
                "- reference_intake_issue_code_counts: "
                f"`{_format_counts(payload['reference_intake_issue_code_counts'])}`",
            ])
        if (
            payload.get("reference_request_validation_issue_code_counts")
            or payload.get("reference_intake_issue_code_counts")
        ):
            lines.append("")
        if action["artifact"]:
            lines.extend([
                "## Recommended Action Artifact",
                "",
                f"- action_artifact: `{action['artifact']}`",
                f"- action_artifact_resolved: `{payload.get('action_artifact_resolved', '')}`",
                f"- action_artifact_exists: `{bool(payload.get('action_artifact_exists'))}`",
                "",
            ])
        for index, route in enumerate(payload.get("routes") or [], start=1):
            lines.append(_write_markdown_route(route, heading=f"Route {index}"))
            lines.append("")
    else:
        lines.append(_write_markdown_route(payload, heading="Route"))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_output_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def route_markdown(payload: dict[str, Any]) -> str:
    return _write_markdown(payload)


def write_route_report_files(
    payload: dict[str, Any],
    *,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> None:
    if out_json:
        _write_output_file(out_json, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if out_md:
        _write_output_file(out_md, route_markdown(payload))


def _recommended_action_code(payload: dict[str, Any]) -> str:
    return str((payload.get("recommended_next_action") or {}).get("code") or "")


def _artifact_matches(actual: str, expected: str) -> bool:
    actual_norm = actual.replace("\\", "/")
    expected_norm = expected.replace("\\", "/").lstrip("/")
    if not expected_norm:
        return not actual_norm
    return actual_norm == expected_norm or actual_norm.endswith(f"/{expected_norm}")


def _recommended_action_domain(payload: dict[str, Any]) -> str:
    return _route_action(payload)["domain"]


def _action_domain_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = payload.get("recommended_action_domain_counts")
    if isinstance(counts, dict):
        return {str(key): int(value) for key, value in counts.items() if str(key)}
    counts = payload.get("case_action_domain_counts")
    if isinstance(counts, dict):
        return {str(key): int(value) for key, value in counts.items() if str(key)}
    domain = _recommended_action_domain(payload)
    return {domain: 1} if domain else {}


def _status_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = payload.get("status_counts")
    if isinstance(counts, dict):
        return {str(key): int(value) for key, value in counts.items() if str(key)}
    status = str(payload.get("status") or "")
    return {status: 1} if status else {}


def _kind_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = payload.get("kind_counts")
    if isinstance(counts, dict):
        return {str(key): int(value) for key, value in counts.items() if str(key)}
    kind = str(payload.get("kind") or "")
    return {kind: 1} if kind else {}


def _route_count(payload: dict[str, Any]) -> int:
    if payload.get("schema") == BATCH_SCHEMA:
        try:
            return int(payload.get("count") or 0)
        except Exception:
            return 0
    return 1


def _issue_code_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in (
        "reference_request_validation_issue_code_counts",
        "reference_intake_issue_code_counts",
    ):
        values = payload.get(key)
        if not isinstance(values, dict):
            continue
        for code, count in values.items():
            code_text = str(code)
            if not code_text:
                continue
            try:
                count_int = int(count)
            except Exception:
                continue
            counts[code_text] = counts.get(code_text, 0) + count_int
    return dict(sorted(counts.items()))


def _parse_boundary_expectation(raw: str) -> tuple[str, Any]:
    if "=" not in raw:
        raise ValueError(f"boundary expectation must be key=value: {raw}")
    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        raise ValueError(f"boundary expectation key is empty: {raw}")
    lowered = value.lower()
    if lowered == "true":
        return key, True
    if lowered == "false":
        return key, False
    return key, value


def _source_boundary_routes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema") == BATCH_SCHEMA:
        return [route for route in payload.get("routes") or [] if isinstance(route, dict)]
    return [payload]


def _check_source_boundary_requirements(
    payload: dict[str, Any],
    expectations: list[tuple[str, Any]],
) -> list[str]:
    failures: list[str] = []
    for route in _source_boundary_routes(payload):
        boundary = route.get("artifact_index_boundary")
        artifact = str(route.get("artifact_index") or "<unknown>")
        if not isinstance(boundary, dict):
            boundary = {}
        for key, expected in expectations:
            if key not in boundary:
                failures.append(f"{artifact}: missing source boundary {key}")
                continue
            actual = boundary.get(key)
            if actual != expected:
                failures.append(f"{artifact}: source boundary {key}={actual!r} != {expected!r}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acad_artifact_route",
        description="Read an AutoCAD reference artifact index and print the next safe action.")
    parser.add_argument("artifact_index", type=Path, nargs="+",
                        help="artifact_index.json, or directories containing artifact_index.json")
    parser.add_argument("--recursive", action="store_true",
                        help="discover artifact_index.json files recursively under directory inputs")
    parser.add_argument("--text", action="store_true", help="print a human-readable summary instead of JSON")
    parser.add_argument("--out-json", type=Path, help="also write the route payload JSON to this file")
    parser.add_argument("--out-md", type=Path, help="also write a Markdown route report to this file")
    parser.add_argument("--require-action", default="",
                        help="exit 2 unless the top-level recommended_next_action.code matches this value")
    parser.add_argument("--require-action-domain", default="",
                        help="exit 2 unless the top-level recommended_next_action.domain matches this value")
    parser.add_argument("--forbid-action-domain", action="append", default=[],
                        help=(
                            "exit 2 if any routed action domain count includes this domain; "
                            "may repeat"
                        ))
    parser.add_argument("--require-status", action="append", default=[],
                        help="exit 2 unless the routed status counts include this status; may repeat")
    parser.add_argument("--forbid-status", action="append", default=[],
                        help="exit 2 if the routed status counts include this status; may repeat")
    parser.add_argument("--require-kind", action="append", default=[],
                        help="exit 2 unless the routed kind counts include this kind; may repeat")
    parser.add_argument("--forbid-kind", action="append", default=[],
                        help="exit 2 if the routed kind counts include this kind; may repeat")
    parser.add_argument("--require-route-count", type=int,
                        help="exit 2 unless the routed artifact-index count exactly matches this value")
    parser.add_argument("--require-action-artifact", default="",
                        help=(
                            "exit 2 unless the top-level recommended_next_action.artifact "
                            "matches or ends with this path"
                        ))
    parser.add_argument("--require-action-artifact-exists", action="store_true",
                        help=(
                            "exit 2 unless the top-level recommended_next_action.artifact "
                            "resolves to an existing file"
                        ))
    parser.add_argument("--require-source-boundary", action="append", default=[],
                        help="exit 2 unless every routed source artifact boundary has key=value; may repeat")
    parser.add_argument("--require-issue-code", action="append", default=[],
                        help=(
                            "exit 2 unless the routed request/intake issue-code counts "
                            "include this code; may repeat"
                        ))
    parser.add_argument("--forbid-issue-code", action="append", default=[],
                        help=(
                            "exit 2 if the routed request/intake issue-code counts "
                            "include this code; may repeat"
                        ))
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
    try:
        source_boundary_expectations = [
            _parse_boundary_expectation(item) for item in args.require_source_boundary
        ]
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
    write_route_report_files(payload, out_json=args.out_json, out_md=args.out_md)
    if args.require_action:
        actual = _recommended_action_code(payload)
        if actual != args.require_action:
            artifact = _recommended_action_artifact(payload)
            print(
                f"acad_artifact_route: required action {args.require_action!r} "
                f"but got {actual!r}",
                file=sys.stderr,
            )
            if artifact:
                print(f"acad_artifact_route: action artifact: {artifact}", file=sys.stderr)
            return 2
    if args.require_action_domain:
        actual = _recommended_action_domain(payload)
        if actual != args.require_action_domain:
            action = _recommended_action_code(payload)
            artifact = _recommended_action_artifact(payload)
            print(
                f"acad_artifact_route: required action domain {args.require_action_domain!r} "
                f"but got {actual!r} for action {action!r}",
                file=sys.stderr,
            )
            if artifact:
                print(f"acad_artifact_route: action artifact: {artifact}", file=sys.stderr)
            return 2
    if args.forbid_action_domain:
        counts = _action_domain_counts(payload)
        forbidden = [domain for domain in args.forbid_action_domain if counts.get(domain, 0)]
        if forbidden:
            print(
                "acad_artifact_route: forbidden action domain present: "
                + ", ".join(f"{domain}={counts.get(domain, 0)}" for domain in forbidden),
                file=sys.stderr,
            )
            print(
                "acad_artifact_route: action domain counts: "
                + _format_counts(counts),
                file=sys.stderr,
            )
            return 2
    if args.require_status or args.forbid_status:
        counts = _status_counts(payload)
        missing = [status for status in args.require_status if not counts.get(status, 0)]
        if missing:
            print(
                "acad_artifact_route: required status missing: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            print(
                "acad_artifact_route: status counts: "
                + _format_counts(counts),
                file=sys.stderr,
            )
            return 2
        forbidden_statuses = [status for status in args.forbid_status if counts.get(status, 0)]
        if forbidden_statuses:
            print(
                "acad_artifact_route: forbidden status present: "
                + ", ".join(f"{status}={counts.get(status, 0)}" for status in forbidden_statuses),
                file=sys.stderr,
            )
            print(
                "acad_artifact_route: status counts: "
                + _format_counts(counts),
                file=sys.stderr,
            )
            return 2
    if args.require_kind or args.forbid_kind:
        counts = _kind_counts(payload)
        missing = [kind for kind in args.require_kind if not counts.get(kind, 0)]
        if missing:
            print(
                "acad_artifact_route: required kind missing: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            print(
                "acad_artifact_route: kind counts: "
                + _format_counts(counts),
                file=sys.stderr,
            )
            return 2
        forbidden_kinds = [kind for kind in args.forbid_kind if counts.get(kind, 0)]
        if forbidden_kinds:
            print(
                "acad_artifact_route: forbidden kind present: "
                + ", ".join(f"{kind}={counts.get(kind, 0)}" for kind in forbidden_kinds),
                file=sys.stderr,
            )
            print(
                "acad_artifact_route: kind counts: "
                + _format_counts(counts),
                file=sys.stderr,
            )
            return 2
    if args.require_route_count is not None:
        actual = _route_count(payload)
        if actual != args.require_route_count:
            print(
                f"acad_artifact_route: required route count {args.require_route_count} "
                f"but got {actual}",
                file=sys.stderr,
            )
            print(
                "acad_artifact_route: kind counts: "
                + _format_counts(_kind_counts(payload)),
                file=sys.stderr,
            )
            return 2
    if args.require_issue_code or args.forbid_issue_code:
        counts = _issue_code_counts(payload)
        missing = [code for code in args.require_issue_code if not counts.get(code, 0)]
        if missing:
            print(
                "acad_artifact_route: required issue code missing: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            print(
                "acad_artifact_route: issue code counts: "
                + _format_counts(counts),
                file=sys.stderr,
            )
            return 2
        forbidden_codes = [code for code in args.forbid_issue_code if counts.get(code, 0)]
        if forbidden_codes:
            print(
                "acad_artifact_route: forbidden issue code present: "
                + ", ".join(f"{code}={counts.get(code, 0)}" for code in forbidden_codes),
                file=sys.stderr,
            )
            print(
                "acad_artifact_route: issue code counts: "
                + _format_counts(counts),
                file=sys.stderr,
            )
            return 2
    if args.require_action_artifact:
        actual = _recommended_action_artifact(payload)
        if not _artifact_matches(actual, args.require_action_artifact):
            action = _recommended_action_code(payload)
            print(
                f"acad_artifact_route: required action artifact {args.require_action_artifact!r} "
                f"but got {actual!r} for action {action!r}",
                file=sys.stderr,
            )
            return 2
    if args.require_action_artifact_exists:
        actual = _recommended_action_artifact(payload)
        resolved = _resolve_action_artifact(payload)
        if not actual or resolved is None:
            action = _recommended_action_code(payload)
            print(
                f"acad_artifact_route: required action artifact to exist "
                f"but action {action!r} has no artifact",
                file=sys.stderr,
            )
            return 2
        if not resolved.is_file():
            action = _recommended_action_code(payload)
            print(
                f"acad_artifact_route: required action artifact to exist "
                f"but {resolved} is not a file for action {action!r}",
                file=sys.stderr,
            )
            return 2
    if source_boundary_expectations:
        failures = _check_source_boundary_requirements(payload, source_boundary_expectations)
        if failures:
            print("acad_artifact_route: source boundary requirement failed", file=sys.stderr)
            for failure in failures:
                print(f"acad_artifact_route: {failure}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
