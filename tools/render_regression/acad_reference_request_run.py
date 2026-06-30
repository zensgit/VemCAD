#!/usr/bin/env python3
"""Fulfill an AutoCAD reference request and run the matched-view comparison."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acad_manifest_compare as compare  # noqa: E402
import acad_reference_batch as batch  # noqa: E402
import acad_artifact_route as artifact_route  # noqa: E402


SCHEMA = "vemcad.acad_reference_request_run/v1"
RUN_ARTIFACT_INDEX_SCHEMA = "vemcad.acad_reference_request_run_artifact_index/v1"


def _artifact_index_boundary(summary: dict[str, Any]) -> dict[str, bool]:
    return {
        "renders_dxf": False,
        "compares_renders": bool(summary.get("compare_artifact_index")),
        "changes_x3_scoring": False,
        "changes_renderer": False,
        "requires_viewspace_match": True,
        "autocad_equivalence_claim": False,
    }


def _existing(path: Path) -> str:
    return str(path) if path.is_file() else ""


def _md_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("|", "\\|")


def _md_table_cell(value: Any) -> str:
    text = _md_text(value)
    if not text:
        return "-"
    return text.replace("`", "\\`")


def _md_code_cell(value: Any) -> str:
    text = _md_text(value) or "-"
    longest_backticks = 0
    current = 0
    for char in text:
        if char == "`":
            current += 1
            longest_backticks = max(longest_backticks, current)
        else:
            current = 0
    delimiter = "`" * (longest_backticks + 1)
    return f"{delimiter}{text}{delimiter}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _clear_run_outputs(out_dir: Path) -> None:
    for name in (
        "run_summary.json",
        "run_summary.md",
        "case_actions.tsv",
        "route_summary.json",
        "route_summary.md",
        "artifact_index.json",
    ):
        path = out_dir / name
        if path.is_file():
            path.unlink()
    compare_dir = out_dir / "compare"
    if compare_dir.is_dir():
        shutil.rmtree(compare_dir)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _maybe_artifact(kind: str, path: str) -> dict[str, str] | None:
    if not path or not Path(path).is_file():
        return None
    return {"kind": kind, "path": path}


def _run_artifact_index_payload(
    summary: dict[str, Any],
    artifacts: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "schema": RUN_ARTIFACT_INDEX_SCHEMA,
        "boundary": _artifact_index_boundary(summary),
        "status": summary["status"],
        "final_exit_code": summary["final_exit_code"],
        "fail_on_input_review": summary["fail_on_input_review"],
        "recommended_next_action": summary["recommended_next_action"],
        "case_actions": summary["case_actions"],
        "case_action_counts": summary["case_action_counts"],
        "case_action_domain_counts": summary["case_action_domain_counts"],
        "reference_request_validation_status": summary["reference_request_validation_status"],
        "reference_request_validation_error_count": summary["reference_request_validation_error_count"],
        "reference_request_validation_warning_count": summary["reference_request_validation_warning_count"],
        "reference_request_validation_issue_code_counts": (
            summary["reference_request_validation_issue_code_counts"]
        ),
        "source_request_boundary": summary.get("source_request_boundary") or {},
        "reference_intake_status": summary["reference_intake_status"],
        "reference_intake_error_count": summary["reference_intake_error_count"],
        "reference_intake_warning_count": summary["reference_intake_warning_count"],
        "reference_intake_issue_code_counts": summary["reference_intake_issue_code_counts"],
        "count": len(artifacts),
        "artifacts": artifacts,
    }
    if summary.get("recommended_next_action_artifact_resolved"):
        payload["recommended_next_action_artifact_resolved"] = (
            summary["recommended_next_action_artifact_resolved"]
        )
        payload["recommended_next_action_artifact_exists"] = bool(
            summary.get("recommended_next_action_artifact_exists")
        )
    if summary.get("route_count") is not None:
        payload.update({
            "route_count": summary.get("route_count"),
            "route_kind_counts": summary.get("route_kind_counts") or {},
            "route_status_counts": summary.get("route_status_counts") or {},
            "route_final_exit_code_counts": summary.get("route_final_exit_code_counts") or {},
            "route_recommended_action_counts": summary.get("route_recommended_action_counts") or {},
            "route_recommended_action_domain_counts": (
                summary.get("route_recommended_action_domain_counts") or {}
            ),
            "route_compare_case_count": summary.get("route_compare_case_count"),
            "route_compared_count": summary.get("route_compared_count"),
            "route_triage_bucket_counts": summary.get("route_triage_bucket_counts") or {},
            "route_viewspace_status_counts": summary.get("route_viewspace_status_counts") or {},
            "route_x3_band_counts": summary.get("route_x3_band_counts") or {},
            "route_compare_issue_code_counts": summary.get("route_compare_issue_code_counts") or {},
        })
    return payload


def _write_run_artifact_index(
    out_dir: Path,
    summary: dict[str, Any],
    artifacts: list[dict[str, str]],
) -> None:
    _write_json(out_dir / "artifact_index.json", _run_artifact_index_payload(summary, artifacts))


def _copy_action_artifact_resolution(summary: dict[str, Any], route_payload: dict[str, Any]) -> None:
    resolved = str(route_payload.get("action_artifact_resolved") or "")
    if not resolved:
        summary.pop("recommended_next_action_artifact_resolved", None)
        summary.pop("recommended_next_action_artifact_exists", None)
        return
    summary["recommended_next_action_artifact_resolved"] = resolved
    summary["recommended_next_action_artifact_exists"] = bool(
        route_payload.get("action_artifact_exists")
    )


def _compare_status(compare_summary: Path) -> str:
    if not compare_summary.is_file():
        return ""
    try:
        payload = json.loads(compare_summary.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(payload.get("status") or "")


def _issue_code_counts(payload: dict[str, Any]) -> dict[str, int]:
    issues = payload.get("issues")
    if not isinstance(issues, list):
        issues = []
        for row in payload.get("cases") or []:
            if isinstance(row, dict):
                issues.extend(row.get("issues") or [])
    counts: dict[str, int] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        code = str(issue.get("code") or "")
        if code:
            counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _intake_status(intake_json: Path) -> dict[str, Any]:
    if not intake_json.is_file():
        return {
            "status": "",
            "error_count": None,
            "warning_count": None,
            "issue_code_counts": {},
            "source_request_boundary": {},
        }
    try:
        payload = json.loads(intake_json.read_text(encoding="utf-8"))
    except Exception:
        return {
            "status": "unreadable",
            "error_count": None,
            "warning_count": None,
            "issue_code_counts": {},
            "source_request_boundary": {},
        }
    source_request_boundary = payload.get("source_request_boundary")
    return {
        "status": str(payload.get("status") or ""),
        "error_count": payload.get("error_count"),
        "warning_count": payload.get("warning_count"),
        "issue_code_counts": _issue_code_counts(payload),
        "source_request_boundary": (
            dict(source_request_boundary) if isinstance(source_request_boundary, dict) else {}
        ),
    }


def _action_domain(code: str) -> str:
    return artifact_route.ACTION_DOMAINS.get(code, "inspect")


def _action(code: str, message: str, *, artifact: str = "") -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "artifact": artifact,
        "domain": _action_domain(code),
    }


def _compare_reference_request_markdown(summary: dict[str, Any]) -> str:
    compare_dir = str(summary.get("compare_dir") or "")
    if not compare_dir:
        return ""
    path = Path(compare_dir) / "reference_request.md"
    return str(path) if path.is_file() else ""


def _recommended_next_action(summary: dict[str, Any]) -> dict[str, str]:
    validation_status = str(summary.get("reference_request_validation_status") or "")
    validation_errors = summary.get("reference_request_validation_error_count")
    intake_status = str(summary.get("reference_intake_status") or "")
    status = str(summary.get("status") or "")

    if validation_status in {"blocked", "unreadable"} or validation_errors:
        return _action(
            "fix-request-package",
            "Fix the request package before exporting or returning AutoCAD PNGs.",
            artifact=str(summary.get("reference_request_validation_markdown") or ""),
        )
    if status == "input_blocked" and summary.get("missing_references_markdown"):
        return _action(
            "provide-returned-autocad-pngs",
            "Place the returned AutoCAD PNGs using the requested filenames, then rerun the wrapper.",
            artifact=str(summary.get("missing_references_markdown") or ""),
        )
    if intake_status == "blocked":
        return _action(
            "fix-returned-reference-input",
            "Fix returned AutoCAD PNG input before matched-view comparison.",
            artifact=str(summary.get("reference_intake_markdown") or ""),
        )
    if intake_status == "review":
        return _action(
            "inspect-returned-reference-warnings",
            "Inspect returned-reference intake warnings before trusting visual conclusions.",
            artifact=str(summary.get("reference_intake_markdown") or ""),
        )
    if status == "viewspace_mismatch":
        return _action(
            "recapture-autocad-or-provide-window",
            "Recapture AutoCAD at matched model extents or provide the real world window; do not tune the renderer.",
            artifact=_compare_reference_request_markdown(summary) or str(summary.get("compare_summary_markdown") or ""),
        )
    if status == "pass":
        return _action(
            "review-x3-pass",
            "Review X3 and artifacts; open renderer work only for a concrete matched-view defect.",
            artifact=str(summary.get("compare_summary_markdown") or ""),
        )
    if status == "compare_failed":
        return _action(
            "inspect-compare-failure",
            "Inspect compare outputs and per-case logs before changing renderer code.",
            artifact=str(summary.get("compare_summary_markdown") or ""),
        )
    return _action(
        "inspect-run-summary",
        "Inspect the run summary and artifact index before choosing the next action.",
        artifact=str(summary.get("run_artifact_index") or ""),
    )


def _case_action_counts(case_actions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for action in case_actions:
        code = str(action.get("code") or "")
        if code:
            counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _case_action_domain_counts(case_actions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for action in case_actions:
        domain = str(action.get("domain") or _action_domain(str(action.get("code") or "")))
        if domain:
            counts[domain] = counts.get(domain, 0) + 1
    return dict(sorted(counts.items()))


def _format_case_action_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _tsv(value: Any) -> str:
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _artifact_resolution(artifact: str) -> dict[str, Any]:
    if not artifact:
        return {}
    resolved = Path(artifact).resolve()
    return {
        "artifact_resolved": str(resolved),
        "artifact_exists": resolved.is_file(),
    }


def _write_case_actions_tsv(path: Path, case_actions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "id\tdrawing_id\tcode\tdomain\tsource\ttriage_bucket\t"
            "viewspace_status\tx3_band\tissue_count\trecommended_output_name\t"
            "artifact\tartifact_resolved\tartifact_exists\n"
        )
        for action in case_actions:
            handle.write(
                f"{_tsv(action.get('id'))}\t"
                f"{_tsv(action.get('drawing_id'))}\t"
                f"{_tsv(action.get('code'))}\t"
                f"{_tsv(action.get('domain'))}\t"
                f"{_tsv(action.get('source'))}\t"
                f"{_tsv(action.get('triage_bucket'))}\t"
                f"{_tsv(action.get('viewspace_status'))}\t"
                f"{_tsv(action.get('x3_band'))}\t"
                f"{_tsv(action.get('issue_count'))}\t"
                f"{_tsv(action.get('recommended_output_name'))}\t"
                f"{_tsv(action.get('artifact'))}\t"
                f"{_tsv(action.get('artifact_resolved'))}\t"
                f"{_tsv(action.get('artifact_exists'))}\n"
            )


def _final_exit_code(
    summary: dict[str, Any],
    base_exit_code: int,
    *,
    fail_on_input_review: bool,
) -> int:
    if (
        fail_on_input_review
        and base_exit_code == 0
        and summary.get("recommended_next_action", {}).get("domain") == "input-review"
    ):
        return 2
    return base_exit_code


def _put_case_action(
    actions: dict[str, dict[str, Any]],
    case_id: str,
    *,
    drawing_id: str = "",
    code: str,
    message: str,
    source: str,
    artifact: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    if not case_id or case_id in actions:
        return
    payload: dict[str, Any] = {
        "id": case_id,
        "drawing_id": drawing_id,
        "code": code,
        "domain": _action_domain(code),
        "message": message,
        "source": source,
        "artifact": artifact,
    }
    payload.update(_artifact_resolution(artifact))
    if extra:
        payload.update(extra)
    actions[case_id] = payload


def _compare_case_action(row: dict[str, Any]) -> tuple[str, str]:
    bucket = str(row.get("triage_bucket") or "")
    if bucket == "renderer-candidate":
        return (
            "inspect-renderer-candidate",
            "Matched-view X3 failed; inspect artifacts and isolate a concrete renderer defect before changing renderer code.",
        )
    if bucket == "recapture-required":
        return (
            "recapture-autocad-or-provide-window",
            "Recapture AutoCAD at matched model extents or provide the real world window; do not tune the renderer.",
        )
    if bucket == "matched-pass":
        return (
            "review-x3-pass",
            "Matched-view X3 passed; no renderer work unless manual review finds a concrete defect.",
        )
    return (
        "inspect-compare-case",
        "Inspect this case's compare artifacts before choosing the next action.",
    )


def _case_actions(summary: dict[str, Any]) -> list[dict[str, Any]]:
    actions: dict[str, dict[str, Any]] = {}

    validation = _read_json(Path(str(summary.get("reference_request_validation_json") or "")))
    validation_artifact = str(summary.get("reference_request_validation_markdown") or "")
    for row in validation.get("cases") or []:
        issues = [item for item in row.get("issues") or [] if item.get("severity") in {"error", "warning"}]
        if issues:
            _put_case_action(
                actions,
                str(row.get("id") or ""),
                drawing_id=str(row.get("drawing_id") or ""),
                code="fix-request-package",
                message="Fix request-package provenance or structure before exporting or returning AutoCAD PNGs.",
                source="request_validation",
                artifact=validation_artifact,
                extra={"issue_count": len(issues)},
            )

    missing = _read_json(Path(str(summary.get("missing_references_json") or "")))
    missing_artifact = str(summary.get("missing_references_markdown") or "")
    for row in missing.get("missing") or []:
        _put_case_action(
            actions,
            str(row.get("id") or ""),
            drawing_id=str(row.get("drawing_id") or ""),
            code="provide-returned-autocad-pngs",
            message="Place the returned AutoCAD PNG using the requested filename, then rerun the wrapper.",
            source="missing_references",
            artifact=missing_artifact,
            extra={"recommended_output_name": str(row.get("recommended_output_name") or "")},
        )

    intake = _read_json(Path(str(summary.get("reference_intake_json") or "")))
    intake_artifact = str(summary.get("reference_intake_markdown") or "")
    for row in intake.get("cases") or []:
        issues = [item for item in row.get("issues") or [] if item.get("severity") in {"error", "warning"}]
        if issues:
            has_error = any(item.get("severity") == "error" for item in issues)
            code = "fix-returned-reference-input" if has_error else "inspect-returned-reference-warnings"
            message = (
                "Fix returned AutoCAD PNG input before matched-view comparison."
                if has_error
                else "Inspect returned-reference intake warnings before trusting visual conclusions."
            )
            _put_case_action(
                actions,
                str(row.get("id") or ""),
                drawing_id=str(row.get("drawing_id") or ""),
                code=code,
                message=message,
                source="reference_intake",
                artifact=intake_artifact,
                extra={"issue_count": len(issues)},
            )

    compare_summary = _read_json(Path(str(summary.get("compare_summary_json") or "")))
    compare_artifact = str(summary.get("compare_summary_markdown") or "")
    compare_request_artifact = _compare_reference_request_markdown(summary)
    for row in compare_summary.get("rows") or []:
        case_id = str(row.get("id") or "")
        code, message = _compare_case_action(row)
        artifact = (
            compare_request_artifact
            if code == "recapture-autocad-or-provide-window" and compare_request_artifact
            else compare_artifact
        )
        x3 = row.get("x3_summary") or {}
        _put_case_action(
            actions,
            case_id,
            drawing_id=str(row.get("drawing_id") or ""),
            code=code,
            message=message,
            source="compare",
            artifact=artifact,
            extra={
                "triage_rank": row.get("triage_rank"),
                "triage_bucket": str(row.get("triage_bucket") or ""),
                "viewspace_status": str(row.get("viewspace_status") or ""),
                "x3_band": str(x3.get("band") or ""),
            },
        )

    return sorted(
        actions.values(),
        key=lambda item: (
            item.get("triage_rank") if isinstance(item.get("triage_rank"), int) else 9999,
            str(item.get("id") or ""),
        ),
    )


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    next_action = summary["recommended_next_action"]
    lines = [
        "# AutoCAD Reference Request Run",
        "",
        f"- status: `{summary['status']}`",
        f"- batch_exit_code: `{summary['batch_exit_code']}`",
        f"- compare_exit_code: `{summary['compare_exit_code']}`",
        f"- final_exit_code: `{summary['final_exit_code']}`",
        f"- fail_on_input_review: `{summary['fail_on_input_review']}`",
        f"- reference_request_validation_status: `{summary['reference_request_validation_status']}`",
        f"- reference_request_validation_errors: `{summary['reference_request_validation_error_count']}`",
        f"- reference_request_validation_warnings: `{summary['reference_request_validation_warning_count']}`",
        "- reference_request_validation_issue_codes: "
        f"`{_format_case_action_counts(summary['reference_request_validation_issue_code_counts'])}`",
        f"- source_request_boundary: `{_format_case_action_counts(summary.get('source_request_boundary') or {})}`",
        f"- reference_intake_status: `{summary['reference_intake_status']}`",
        f"- reference_intake_errors: `{summary['reference_intake_error_count']}`",
        f"- reference_intake_warnings: `{summary['reference_intake_warning_count']}`",
        f"- reference_intake_issue_codes: `{_format_case_action_counts(summary['reference_intake_issue_code_counts'])}`",
        f"- recommended_next_action: `{next_action['code']}`",
        f"- recommended_next_action_domain: `{next_action['domain']}`",
        f"- recommended_next_action_message: {next_action['message']}",
        f"- case_action_counts: `{_format_case_action_counts(summary['case_action_counts'])}`",
        f"- case_action_domain_counts: `{_format_case_action_counts(summary['case_action_domain_counts'])}`",
    ]
    if summary.get("route_count") is not None:
        lines.extend([
            f"- route_count: `{summary['route_count']}`",
            f"- route_kind_counts: `{_format_case_action_counts(summary.get('route_kind_counts') or {})}`",
            f"- route_status_counts: `{_format_case_action_counts(summary.get('route_status_counts') or {})}`",
            "- route_final_exit_code_counts: "
            f"`{_format_case_action_counts(summary.get('route_final_exit_code_counts') or {})}`",
            "- route_recommended_action_counts: "
            f"`{_format_case_action_counts(summary.get('route_recommended_action_counts') or {})}`",
            "- route_recommended_action_domain_counts: "
            f"`{_format_case_action_counts(summary.get('route_recommended_action_domain_counts') or {})}`",
        ])
        if summary.get("route_compare_case_count") is not None:
            lines.append(f"- route_compare_case_count: `{summary['route_compare_case_count']}`")
        if summary.get("route_compared_count") is not None:
            lines.append(f"- route_compared_count: `{summary['route_compared_count']}`")
        if summary.get("route_triage_bucket_counts"):
            lines.append(
                "- route_triage_bucket_counts: "
                f"`{_format_case_action_counts(summary.get('route_triage_bucket_counts') or {})}`"
            )
        if summary.get("route_viewspace_status_counts"):
            lines.append(
                "- route_viewspace_status_counts: "
                f"`{_format_case_action_counts(summary.get('route_viewspace_status_counts') or {})}`"
            )
        if summary.get("route_x3_band_counts"):
            lines.append(
                "- route_x3_band_counts: "
                f"`{_format_case_action_counts(summary.get('route_x3_band_counts') or {})}`"
            )
        if summary.get("route_compare_issue_code_counts"):
            lines.append(
                "- route_compare_issue_code_counts: "
                f"`{_format_case_action_counts(summary.get('route_compare_issue_code_counts') or {})}`"
            )
    lines.extend([
        "",
        "## Boundary",
        "",
        f"- autocad_equivalence_claim: `{summary['boundary']['autocad_equivalence_claim']}`",
        f"- requires_viewspace_match: `{summary['boundary']['requires_viewspace_match']}`",
        "",
        "This wrapper only runs the existing input-prep and matched-view comparison tools. It does not render DXFs and does not replace X3.",
        "",
        "## Artifacts",
        "",
        f"- input_dir: `{summary['input_dir']}`",
        f"- compare_dir: `{summary['compare_dir']}`",
    ])
    for label, key in (
        ("run artifact index", "run_artifact_index"),
        ("input artifact index", "input_artifact_index"),
        ("request validation", "reference_request_validation_markdown"),
        ("reference intake", "reference_intake_markdown"),
        ("missing references", "missing_references_markdown"),
        ("missing references tsv", "missing_references_tsv"),
        ("compare summary", "compare_summary_markdown"),
        ("compare reference request", "compare_reference_request_markdown"),
        ("compare reference request json", "compare_reference_request_json"),
        ("compare artifact index", "compare_artifact_index"),
        ("case actions tsv", "case_actions_tsv"),
        ("route summary json", "route_summary_json"),
        ("route summary markdown", "route_summary_markdown"),
    ):
        value = summary.get(key) or ""
        if value:
            lines.append(f"- {label}: {_md_code_cell(value)}")
    if next_action.get("artifact"):
        lines.append(f"- recommended next action artifact: {_md_code_cell(next_action['artifact'])}")
    if summary.get("recommended_next_action_artifact_resolved"):
        lines.append(
            "- recommended next action artifact resolved: "
            f"{_md_code_cell(summary['recommended_next_action_artifact_resolved'])}"
        )
        lines.append(
            "- recommended next action artifact exists: "
            f"{_md_code_cell(bool(summary.get('recommended_next_action_artifact_exists')))}"
        )
    case_actions = summary.get("case_actions") or []
    if case_actions:
        lines.extend([
            "",
            "## Case Actions",
            "",
            "| Case | Drawing | Action | Domain | Source | Triage | Artifact |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for action in case_actions:
            triage = action.get("triage_bucket") or action.get("issue_count") or "-"
            artifact = action.get("artifact_resolved") or action.get("artifact") or ""
            lines.append(
                f"| {_md_code_cell(action.get('id', ''))} | {_md_table_cell(action.get('drawing_id', ''))} | "
                f"{_md_code_cell(action.get('code', ''))} | {_md_code_cell(action.get('domain', ''))} | "
                f"{_md_code_cell(action.get('source', ''))} | "
                f"{_md_code_cell(triage)} | {_md_code_cell(artifact)} |"
            )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_run_summary(
    out_dir: Path,
    *,
    input_dir: Path,
    compare_dir: Path,
    batch_rc: int,
    compare_rc: int | None,
    fail_on_input_review: bool = False,
) -> dict[str, Any]:
    compare_summary_json = compare_dir / "summary.json"
    compare_status = _compare_status(compare_summary_json)
    request_validation = _intake_status(input_dir / "reference_request_validation.json")
    intake = _intake_status(input_dir / "reference_intake.json")
    if batch_rc != 0:
        status = "input_blocked"
    else:
        status = compare_status or ("pass" if compare_rc == 0 else "compare_failed")
    payload = {
        "schema": SCHEMA,
        "status": status,
        "batch_exit_code": batch_rc,
        "compare_exit_code": compare_rc,
        "input_dir": str(input_dir),
        "compare_dir": str(compare_dir),
        "run_artifact_index": str(out_dir / "artifact_index.json"),
        "input_artifact_index": _existing(input_dir / "artifact_index.json"),
        "reference_request_validation_json": _existing(input_dir / "reference_request_validation.json"),
        "reference_request_validation_markdown": _existing(input_dir / "reference_request_validation.md"),
        "reference_request_validation_status": request_validation["status"],
        "reference_request_validation_error_count": request_validation["error_count"],
        "reference_request_validation_warning_count": request_validation["warning_count"],
        "reference_request_validation_issue_code_counts": request_validation["issue_code_counts"],
        "source_request_boundary": request_validation["source_request_boundary"],
        "reference_intake_json": _existing(input_dir / "reference_intake.json"),
        "reference_intake_markdown": _existing(input_dir / "reference_intake.md"),
        "reference_intake_status": intake["status"],
        "reference_intake_error_count": intake["error_count"],
        "reference_intake_warning_count": intake["warning_count"],
        "reference_intake_issue_code_counts": intake["issue_code_counts"],
        "missing_references_json": _existing(input_dir / "missing_references.json"),
        "missing_references_markdown": _existing(input_dir / "missing_references.md"),
        "missing_references_tsv": _existing(input_dir / "missing_references.tsv"),
        "compare_summary_json": _existing(compare_summary_json),
        "compare_summary_markdown": _existing(compare_dir / "summary.md"),
        "compare_reference_request_json": _existing(compare_dir / "reference_request.json"),
        "compare_reference_request_markdown": _existing(compare_dir / "reference_request.md"),
        "compare_artifact_index": _existing(compare_dir / "artifact_index.json"),
        "route_summary_json": str(out_dir / "route_summary.json"),
        "route_summary_markdown": str(out_dir / "route_summary.md"),
        "case_actions_tsv": str(out_dir / "case_actions.tsv"),
        "boundary": {
            "renders_dxf": False,
            "requires_viewspace_match": True,
            "autocad_equivalence_claim": False,
        },
    }
    payload["recommended_next_action"] = _recommended_next_action(payload)
    base_exit_code = batch_rc if batch_rc != 0 else int(compare_rc if compare_rc is not None else 1)
    payload["fail_on_input_review"] = bool(fail_on_input_review)
    payload["final_exit_code"] = _final_exit_code(
        payload,
        base_exit_code,
        fail_on_input_review=fail_on_input_review,
    )
    payload["case_actions"] = _case_actions(payload)
    payload["case_action_counts"] = _case_action_counts(payload["case_actions"])
    payload["case_action_domain_counts"] = _case_action_domain_counts(payload["case_actions"])
    _write_case_actions_tsv(Path(payload["case_actions_tsv"]), payload["case_actions"])
    _write_json(out_dir / "run_summary.json", payload)
    _write_markdown(out_dir / "run_summary.md", payload)
    artifacts = [
        {"kind": "run_summary_json", "path": str(out_dir / "run_summary.json")},
        {"kind": "run_summary_markdown", "path": str(out_dir / "run_summary.md")},
        {"kind": "case_actions_tsv", "path": str(out_dir / "case_actions.tsv")},
        {"kind": "route_summary_json", "path": str(out_dir / "route_summary.json")},
        {"kind": "route_summary_markdown", "path": str(out_dir / "route_summary.md")},
    ]
    for kind, key in (
        ("input_artifact_index", "input_artifact_index"),
        ("reference_request_validation_json", "reference_request_validation_json"),
        ("reference_request_validation_markdown", "reference_request_validation_markdown"),
        ("reference_intake_json", "reference_intake_json"),
        ("reference_intake_markdown", "reference_intake_markdown"),
        ("missing_references_json", "missing_references_json"),
        ("missing_references_markdown", "missing_references_markdown"),
        ("missing_references_tsv", "missing_references_tsv"),
        ("compare_summary_json", "compare_summary_json"),
        ("compare_summary_markdown", "compare_summary_markdown"),
        ("compare_reference_request_json", "compare_reference_request_json"),
        ("compare_reference_request_markdown", "compare_reference_request_markdown"),
        ("compare_artifact_index", "compare_artifact_index"),
    ):
        item = _maybe_artifact(kind, str(payload.get(key) or ""))
        if item is not None:
            artifacts.append(item)
    _write_run_artifact_index(out_dir, payload, artifacts)
    route_inputs = [Path(path) for path in (
        payload.get("input_artifact_index"),
        str(out_dir / "artifact_index.json"),
        payload.get("compare_artifact_index"),
    ) if path]
    route_payload = artifact_route.route_artifact_indexes(route_inputs)
    artifact_route.write_route_report_files(
        route_payload,
        out_json=Path(payload["route_summary_json"]),
        out_md=Path(payload["route_summary_markdown"]),
    )
    payload.update({
        "route_count": route_payload.get("count"),
        "route_kind_counts": route_payload.get("kind_counts") or {},
        "route_status_counts": route_payload.get("status_counts") or {},
        "route_final_exit_code_counts": route_payload.get("final_exit_code_counts") or {},
        "route_recommended_action_counts": route_payload.get("recommended_action_counts") or {},
        "route_recommended_action_domain_counts": (
            route_payload.get("recommended_action_domain_counts") or {}
        ),
        "route_compare_case_count": route_payload.get("compare_case_count"),
        "route_compared_count": route_payload.get("compared_count"),
        "route_triage_bucket_counts": route_payload.get("triage_bucket_counts") or {},
        "route_viewspace_status_counts": route_payload.get("viewspace_status_counts") or {},
        "route_x3_band_counts": route_payload.get("x3_band_counts") or {},
        "route_compare_issue_code_counts": route_payload.get("compare_issue_code_counts") or {},
    })
    _write_run_artifact_index(out_dir, payload, artifacts)
    route_payload = artifact_route.route_artifact_indexes(route_inputs)
    _copy_action_artifact_resolution(payload, route_payload)
    artifact_route.write_route_report_files(
        route_payload,
        out_json=Path(payload["route_summary_json"]),
        out_md=Path(payload["route_summary_markdown"]),
    )
    _write_run_artifact_index(out_dir, payload, artifacts)
    _write_json(out_dir / "run_summary.json", payload)
    _write_markdown(out_dir / "run_summary.md", payload)
    return payload


def _print_run_summary(summary: dict[str, Any], out_dir: Path) -> None:
    print(f"AutoCAD reference request run: {summary['status']}")
    print(f"  final exit code: {summary['final_exit_code']}")
    print(f"  fail on input review: {bool(summary.get('fail_on_input_review'))}")
    print(f"  recommended next action: {summary['recommended_next_action']['code']}")
    print(f"  recommended next action domain: {summary['recommended_next_action']['domain']}")
    if summary["recommended_next_action"].get("artifact"):
        print(f"  recommended next action artifact: {summary['recommended_next_action']['artifact']}")
    if summary.get("recommended_next_action_artifact_resolved"):
        print(
            "  recommended next action artifact resolved: "
            f"{summary['recommended_next_action_artifact_resolved']}"
        )
        print(
            "  recommended next action artifact exists: "
            f"{bool(summary.get('recommended_next_action_artifact_exists'))}"
        )
    print(f"  case action counts: {_format_case_action_counts(summary['case_action_counts'])}")
    print(f"  case action domain counts: {_format_case_action_counts(summary['case_action_domain_counts'])}")
    print(
        "  reference request validation issue codes: "
        f"{_format_case_action_counts(summary['reference_request_validation_issue_code_counts'])}"
    )
    print(
        "  reference intake issue codes: "
        f"{_format_case_action_counts(summary['reference_intake_issue_code_counts'])}"
    )
    if summary.get("route_compare_case_count") is not None:
        print(f"  route compare cases: {summary['route_compare_case_count']}")
    if summary.get("route_compared_count") is not None:
        print(f"  route compared cases: {summary['route_compared_count']}")
    if summary.get("route_triage_bucket_counts"):
        print(
            "  route triage buckets: "
            f"{_format_case_action_counts(summary['route_triage_bucket_counts'])}"
        )
    if summary.get("route_viewspace_status_counts"):
        print(
            "  route viewspace statuses: "
            f"{_format_case_action_counts(summary['route_viewspace_status_counts'])}"
        )
    if summary.get("route_final_exit_code_counts"):
        print(
            "  route final exit codes: "
            f"{_format_case_action_counts(summary['route_final_exit_code_counts'])}"
        )
    if summary.get("route_x3_band_counts"):
        print(
            "  route x3 bands: "
            f"{_format_case_action_counts(summary['route_x3_band_counts'])}"
        )
    if summary.get("route_compare_issue_code_counts"):
        print(
            "  route compare issue codes: "
            f"{_format_case_action_counts(summary['route_compare_issue_code_counts'])}"
        )
    if summary.get("route_summary_markdown"):
        print(f"  route summary  : {summary['route_summary_markdown']}")
    print(f"  run summary: {out_dir / 'run_summary.md'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acad_reference_request_run",
        description="Fulfill a reference_request.json and run the matched-view X3 comparison.")
    parser.add_argument("--from-request", type=Path, required=True,
                        help="reference_request.json produced by acad_manifest_compare.py")
    parser.add_argument("--candidate-cases", type=Path, required=True,
                        help="original candidate_cases.json")
    parser.add_argument("--reference-dir", type=Path, required=True,
                        help="directory containing returned AutoCAD PNGs")
    parser.add_argument("--case-id", action="append", default=None,
                        help="fulfill and compare only this case id; may repeat")
    parser.add_argument("--require-request-boundary", action="append", default=[],
                        help="require reference_request.json boundary key=value before fulfilment; may repeat")
    parser.add_argument("--fail-on-input-review", action="store_true",
                        help=(
                            "return exit code 2 when the run's recommended action is in the "
                            "input-review domain, even if the matched-view compare itself exits 0"
                        ))
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    _clear_run_outputs(args.out_dir)
    input_dir = args.out_dir / "input"
    compare_dir = args.out_dir / "compare"
    batch_args = [
        "--from-request", str(args.from_request),
        "--candidate-cases", str(args.candidate_cases),
        "--reference-dir", str(args.reference_dir),
        "--out-dir", str(input_dir),
    ]
    for item in args.require_request_boundary:
        batch_args.extend(["--require-request-boundary", item])
    for case_id in args.case_id or []:
        batch_args.extend(["--case-id", case_id])
    batch_rc = batch.main(batch_args)
    if batch_rc != 0:
        summary = _write_run_summary(
            args.out_dir,
            input_dir=input_dir,
            compare_dir=compare_dir,
            batch_rc=batch_rc,
            compare_rc=None,
            fail_on_input_review=args.fail_on_input_review,
        )
        _print_run_summary(summary, args.out_dir)
        return batch_rc

    compare_rc = compare.main([
        "--manifest", str(input_dir / "acad_manifest.json"),
        "--candidate-cases", str(input_dir / "candidate_cases.json"),
        "--out-dir", str(compare_dir),
    ])
    summary = _write_run_summary(
        args.out_dir,
        input_dir=input_dir,
        compare_dir=compare_dir,
        batch_rc=batch_rc,
        compare_rc=compare_rc,
        fail_on_input_review=args.fail_on_input_review,
    )
    _print_run_summary(summary, args.out_dir)
    return int(summary["final_exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
