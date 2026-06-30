#!/usr/bin/env python3
"""Fulfill an AutoCAD reference request and run the matched-view comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acad_manifest_compare as compare  # noqa: E402
import acad_reference_batch as batch  # noqa: E402


SCHEMA = "vemcad.acad_reference_request_run/v1"
RUN_ARTIFACT_INDEX_SCHEMA = "vemcad.acad_reference_request_run_artifact_index/v1"


def _existing(path: Path) -> str:
    return str(path) if path.is_file() else ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _maybe_artifact(kind: str, path: str) -> dict[str, str] | None:
    if not path or not Path(path).is_file():
        return None
    return {"kind": kind, "path": path}


def _compare_status(compare_summary: Path) -> str:
    if not compare_summary.is_file():
        return ""
    try:
        payload = json.loads(compare_summary.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(payload.get("status") or "")


def _intake_status(intake_json: Path) -> dict[str, Any]:
    if not intake_json.is_file():
        return {
            "status": "",
            "error_count": None,
            "warning_count": None,
        }
    try:
        payload = json.loads(intake_json.read_text(encoding="utf-8"))
    except Exception:
        return {
            "status": "unreadable",
            "error_count": None,
            "warning_count": None,
        }
    return {
        "status": str(payload.get("status") or ""),
        "error_count": payload.get("error_count"),
        "warning_count": payload.get("warning_count"),
    }


def _recommended_next_action(summary: dict[str, Any]) -> dict[str, str]:
    validation_status = str(summary.get("reference_request_validation_status") or "")
    validation_errors = summary.get("reference_request_validation_error_count")
    intake_status = str(summary.get("reference_intake_status") or "")
    status = str(summary.get("status") or "")

    if validation_status in {"blocked", "unreadable"} or validation_errors:
        return {
            "code": "fix-request-package",
            "message": "Fix the request package before exporting or returning AutoCAD PNGs.",
            "artifact": str(summary.get("reference_request_validation_markdown") or ""),
        }
    if status == "input_blocked" and summary.get("missing_references_markdown"):
        return {
            "code": "provide-returned-autocad-pngs",
            "message": "Place the returned AutoCAD PNGs using the requested filenames, then rerun the wrapper.",
            "artifact": str(summary.get("missing_references_markdown") or ""),
        }
    if intake_status == "review":
        return {
            "code": "inspect-returned-reference-warnings",
            "message": "Inspect returned-reference intake warnings before trusting visual conclusions.",
            "artifact": str(summary.get("reference_intake_markdown") or ""),
        }
    if status == "viewspace_mismatch":
        return {
            "code": "recapture-autocad-or-provide-window",
            "message": "Recapture AutoCAD at matched model extents or provide the real world window; do not tune the renderer.",
            "artifact": str(summary.get("compare_summary_markdown") or ""),
        }
    if status == "pass":
        return {
            "code": "review-x3-pass",
            "message": "Review X3 and artifacts; open renderer work only for a concrete matched-view defect.",
            "artifact": str(summary.get("compare_summary_markdown") or ""),
        }
    if status == "compare_failed":
        return {
            "code": "inspect-compare-failure",
            "message": "Inspect compare outputs and per-case logs before changing renderer code.",
            "artifact": str(summary.get("compare_summary_markdown") or ""),
        }
    return {
        "code": "inspect-run-summary",
        "message": "Inspect the run summary and artifact index before choosing the next action.",
        "artifact": str(summary.get("run_artifact_index") or ""),
    }


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    next_action = summary["recommended_next_action"]
    lines = [
        "# AutoCAD Reference Request Run",
        "",
        f"- status: `{summary['status']}`",
        f"- batch_exit_code: `{summary['batch_exit_code']}`",
        f"- compare_exit_code: `{summary['compare_exit_code']}`",
        f"- reference_request_validation_status: `{summary['reference_request_validation_status']}`",
        f"- reference_request_validation_errors: `{summary['reference_request_validation_error_count']}`",
        f"- reference_intake_status: `{summary['reference_intake_status']}`",
        f"- reference_intake_warnings: `{summary['reference_intake_warning_count']}`",
        f"- recommended_next_action: `{next_action['code']}`",
        f"- recommended_next_action_message: {next_action['message']}",
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
    ]
    for label, key in (
        ("run artifact index", "run_artifact_index"),
        ("input artifact index", "input_artifact_index"),
        ("request validation", "reference_request_validation_markdown"),
        ("reference intake", "reference_intake_markdown"),
        ("missing references", "missing_references_markdown"),
        ("compare summary", "compare_summary_markdown"),
        ("compare artifact index", "compare_artifact_index"),
    ):
        value = summary.get(key) or ""
        if value:
            lines.append(f"- {label}: `{value}`")
    if next_action.get("artifact"):
        lines.append(f"- recommended next action artifact: `{next_action['artifact']}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_run_summary(
    out_dir: Path,
    *,
    input_dir: Path,
    compare_dir: Path,
    batch_rc: int,
    compare_rc: int | None,
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
        "reference_intake_json": _existing(input_dir / "reference_intake.json"),
        "reference_intake_markdown": _existing(input_dir / "reference_intake.md"),
        "reference_intake_status": intake["status"],
        "reference_intake_error_count": intake["error_count"],
        "reference_intake_warning_count": intake["warning_count"],
        "missing_references_json": _existing(input_dir / "missing_references.json"),
        "missing_references_markdown": _existing(input_dir / "missing_references.md"),
        "compare_summary_json": _existing(compare_summary_json),
        "compare_summary_markdown": _existing(compare_dir / "summary.md"),
        "compare_artifact_index": _existing(compare_dir / "artifact_index.json"),
        "boundary": {
            "renders_dxf": False,
            "requires_viewspace_match": True,
            "autocad_equivalence_claim": False,
        },
    }
    payload["recommended_next_action"] = _recommended_next_action(payload)
    _write_json(out_dir / "run_summary.json", payload)
    _write_markdown(out_dir / "run_summary.md", payload)
    artifacts = [
        {"kind": "run_summary_json", "path": str(out_dir / "run_summary.json")},
        {"kind": "run_summary_markdown", "path": str(out_dir / "run_summary.md")},
    ]
    for kind, key in (
        ("input_artifact_index", "input_artifact_index"),
        ("reference_request_validation_json", "reference_request_validation_json"),
        ("reference_request_validation_markdown", "reference_request_validation_markdown"),
        ("reference_intake_json", "reference_intake_json"),
        ("reference_intake_markdown", "reference_intake_markdown"),
        ("missing_references_json", "missing_references_json"),
        ("missing_references_markdown", "missing_references_markdown"),
        ("compare_summary_json", "compare_summary_json"),
        ("compare_summary_markdown", "compare_summary_markdown"),
        ("compare_artifact_index", "compare_artifact_index"),
    ):
        item = _maybe_artifact(kind, str(payload.get(key) or ""))
        if item is not None:
            artifacts.append(item)
    _write_json(out_dir / "artifact_index.json", {
        "schema": RUN_ARTIFACT_INDEX_SCHEMA,
        "status": payload["status"],
        "recommended_next_action": payload["recommended_next_action"],
        "count": len(artifacts),
        "artifacts": artifacts,
    })
    return payload


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
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    input_dir = args.out_dir / "input"
    compare_dir = args.out_dir / "compare"
    batch_args = [
        "--from-request", str(args.from_request),
        "--candidate-cases", str(args.candidate_cases),
        "--reference-dir", str(args.reference_dir),
        "--out-dir", str(input_dir),
    ]
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
        )
        print(f"AutoCAD reference request run: {summary['status']}")
        print(f"  recommended next action: {summary['recommended_next_action']['code']}")
        print(f"  run summary: {args.out_dir / 'run_summary.md'}")
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
    )
    print(f"AutoCAD reference request run: {summary['status']}")
    print(f"  recommended next action: {summary['recommended_next_action']['code']}")
    print(f"  run summary: {args.out_dir / 'run_summary.md'}")
    return compare_rc


if __name__ == "__main__":
    raise SystemExit(main())
