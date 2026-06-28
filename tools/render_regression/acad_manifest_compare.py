#!/usr/bin/env python3
"""Run matched-view X3 comparisons from an AutoCAD reference manifest.

This is the Day 2 harness for the G11 render-fidelity plan. It does not render
DXFs. It joins trusted AutoCAD references from acad_reference_manifest.py with
already-produced VemCAD PNG artifacts, then runs the existing compare_vs_acad.py
view-space gate for each case.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acad_reference_manifest as arm  # noqa: E402
import compare_vs_acad as cva  # noqa: E402


SCHEMA = "vemcad.acad_manifest_compare/v1"


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _resolve_path(base: Path, value: Any) -> Path:
    path = Path(_str(value))
    if not path.is_absolute():
        path = base / path
    return path


def _safe_case_name(case_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in case_id)
    return safe or "case"


def _load_candidate_cases(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("candidate cases JSON must be a list")
    base = path.parent
    candidates: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, str]] = []
    for index, raw in enumerate(data, start=1):
        case_id = _str(raw.get("id") if isinstance(raw, dict) else "") or f"case{index:03d}"
        if not isinstance(raw, dict):
            issues.append({
                "case_id": case_id,
                "severity": "error",
                "code": "candidate_not_object",
                "message": "candidate case must be an object",
            })
            continue
        ours_raw = _str(raw.get("ours") or raw.get("candidate") or raw.get("candidate_png"))
        if not ours_raw:
            issues.append({
                "case_id": case_id,
                "severity": "error",
                "code": "missing_candidate_png",
                "message": "candidate case must include ours/candidate_png",
            })
            continue
        ours = _resolve_path(base, ours_raw)
        if not ours.is_file():
            issues.append({
                "case_id": case_id,
                "severity": "error",
                "code": "candidate_png_missing",
                "message": f"candidate PNG not found: {ours}",
            })
        entry = {
            "id": case_id,
            "ours": str(ours),
            "source": dict(raw),
        }
        for key in ("render_report", "semantic_mask", "semantic_report"):
            value = _str(raw.get(key))
            if value:
                resolved = _resolve_path(base, value)
                if not resolved.is_file():
                    issues.append({
                        "case_id": case_id,
                        "severity": "error",
                        "code": f"{key}_missing",
                        "message": f"{key} not found: {resolved}",
                    })
                entry[key] = str(resolved)
        for key in ("render_image_digest", "render_image", "diagnostics"):
            if key in raw:
                entry[key] = raw[key]
        candidates[case_id] = entry
    return candidates, issues


def _manifest_issue_dict(issue: dict[str, Any]) -> dict[str, str]:
    return {
        "case_id": _str(issue.get("case_id")),
        "severity": _str(issue.get("severity") or "error"),
        "code": _str(issue.get("code")),
        "message": _str(issue.get("message")),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "id\tdrawing_id\tviewspace_status\tx3_band\tink_iou\tcolor_dist\t"
            "aspect_delta\tcompare_exit_code\tacad_png\tours\toverlay\tviewspace_report\n"
        )
        for row in rows:
            summary = row.get("x3_summary") or {}
            handle.write(
                f"{row['id']}\t{row.get('drawing_id', '')}\t{row.get('viewspace_status', '')}\t"
                f"{summary.get('band', '')}\t{summary.get('ink_iou', '')}\t"
                f"{summary.get('color_dist', '')}\t{summary.get('aspect_delta', '')}\t"
                f"{row.get('compare_exit_code', '')}\t{row.get('acad_png', '')}\t"
                f"{row.get('ours', '')}\t{row.get('overlay', '')}\t"
                f"{row.get('viewspace_report', '')}\n"
            )


def _compare_case(case: dict[str, Any], candidate: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    case_id = case["id"]
    safe = _safe_case_name(case_id)
    overlay = out_dir / "overlays" / f"{safe}_overlay.png"
    viewspace = out_dir / "viewspace" / f"{safe}_viewspace.json"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    viewspace.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        case["acad_png"],
        candidate["ours"],
        "--out", str(overlay),
        "--viewspace-report", str(viewspace),
        "--require-viewspace-match",
        "--capture-method", case["capture_method"],
    ]
    semantic_report_path = ""
    if candidate.get("semantic_mask") and candidate.get("semantic_report"):
        semantic_report = out_dir / "semantic" / f"{safe}_semantic_classes.json"
        argv.extend([
            "--semantic-mask", candidate["semantic_mask"],
            "--semantic-render-report", candidate["semantic_report"],
            "--semantic-class-report", str(semantic_report),
        ])
        semantic_report_path = str(semantic_report)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        rc = cva.main(argv)
    view_payload = json.loads(viewspace.read_text(encoding="utf-8"))
    return {
        "id": case_id,
        "drawing_id": case["drawing_id"],
        "source_dxf": case["source_dxf"],
        "acad_png": case["acad_png"],
        "ours": candidate["ours"],
        "render_report": candidate.get("render_report", ""),
        "semantic_mask": candidate.get("semantic_mask", ""),
        "semantic_report": candidate.get("semantic_report", ""),
        "semantic_class_report": semantic_report_path,
        "render_image_digest": candidate.get("render_image_digest", ""),
        "render_image": candidate.get("render_image", ""),
        "diagnostics": candidate.get("diagnostics", {}),
        "overlay": str(overlay) if overlay.is_file() else "",
        "viewspace_report": str(viewspace),
        "viewspace_status": view_payload["status"],
        "viewspace_reason": view_payload["reason"],
        "recommended_action": view_payload["recommended_action"],
        "x3_summary": view_payload["x3_summary"],
        "compare_exit_code": rc,
        "compare_stdout": stdout.getvalue(),
    }


def build_report(
    manifest_path: Path,
    *,
    candidate_cases: Path | None,
    out_dir: Path,
    dry_run: bool = False,
) -> tuple[int, dict[str, Any]]:
    validation = arm.validate_manifest(manifest_path)
    issues = [_manifest_issue_dict(issue) for issue in validation["issues"]]
    rows: list[dict[str, Any]] = []
    status = "ready" if dry_run else "pass"

    if validation["status"] != "pass":
        status = "blocked"
    elif dry_run:
        rows = validation["cases"]
    else:
        if candidate_cases is None:
            issues.append({
                "case_id": "",
                "severity": "error",
                "code": "missing_candidate_cases",
                "message": "--candidate-cases is required unless --dry-run is set",
            })
            status = "blocked"
        else:
            candidates, candidate_issues = _load_candidate_cases(candidate_cases)
            issues.extend(candidate_issues)
            if candidate_issues:
                status = "blocked"
            for case in validation["cases"]:
                if status == "blocked":
                    break
                candidate = candidates.get(case["id"])
                if candidate is None:
                    issues.append({
                        "case_id": case["id"],
                        "severity": "error",
                        "code": "candidate_case_missing",
                        "message": f"candidate case missing for manifest id={case['id']}",
                    })
                    status = "blocked"
                    break
                row = _compare_case(case, candidate, out_dir)
                rows.append(row)
                if row["viewspace_status"] != "match":
                    status = "viewspace_mismatch"
            if status == "pass" and any(row["compare_exit_code"] != 0 for row in rows):
                status = "compare_failed"

    report = {
        "schema": SCHEMA,
        "manifest": str(manifest_path),
        "candidate_cases": str(candidate_cases) if candidate_cases is not None else "",
        "status": status,
        "case_count": len(validation["cases"]),
        "compared_count": len(rows) if not dry_run else 0,
        "dry_run": dry_run,
        "issues": issues,
        "validation": validation,
        "rows": rows,
        "boundary": {
            "renders_dxf": False,
            "requires_viewspace_match": True,
            "autocad_equivalence_claim": False,
        },
    }
    rc = 0 if status in ("pass", "ready") else 2
    return rc, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acad_manifest_compare",
        description="Run matched-view X3 comparisons from an AutoCAD reference manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate-cases", type=Path, default=None,
                        help="JSON list mapping manifest ids to VemCAD PNG artifacts")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="validate the AutoCAD manifest only; do not require candidates or compare")
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rc, report = build_report(
        args.manifest,
        candidate_cases=args.candidate_cases,
        out_dir=args.out_dir,
        dry_run=args.dry_run,
    )
    _write_json(args.out_dir / "summary.json", report)
    if report["rows"] and not args.dry_run:
        _write_tsv(args.out_dir / "summary.tsv", report["rows"])

    print(
        f"AutoCAD manifest compare: {report['status']} "
        f"({report['compared_count']}/{report['case_count']} compared, {len(report['issues'])} issues)"
    )
    for issue in report["issues"]:
        print(f"  {issue['severity']} {issue['case_id']} {issue['code']}: {issue['message']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
