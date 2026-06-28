#!/usr/bin/env python3
"""Validate AutoCAD reference manifests for X3 comparisons.

This tool is deliberately small and fail-closed. It does not render or compare;
it only decides whether supplied AutoCAD PNG references are trustworthy enough
to feed the matched-view X3 path.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


SCHEMA = "vemcad.autocad_reference_manifest/v1"
REPORT_SCHEMA = "vemcad.autocad_reference_manifest_validation/v1"

GATE_CAPTURE_METHODS = {
    "plot-export",
    "exportpng",
    "publish",
    "plot-raster",
}

DIAGNOSTIC_CAPTURE_METHODS = {
    "viewport-capture",
    "screenshot",
    "window-screenshot",
    "dwg-thumbnail",
}

MATCHED_VIEW_CONTRACTS = {
    "model-extents",
    "explicit-window",
}


@dataclass(frozen=True)
class ValidationIssue:
    case_id: str
    severity: str
    code: str
    message: str


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _expected_size(case: dict[str, Any]) -> tuple[int, int] | None:
    raw = case.get("expected_size")
    if raw is None:
        return None
    if isinstance(raw, dict):
        width = raw.get("width")
        height = raw.get("height")
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        width, height = raw
    else:
        raise ValueError("expected_size must be {width,height} or [width,height]")
    width_i = int(width)
    height_i = int(height)
    if width_i <= 0 or height_i <= 0:
        raise ValueError("expected_size values must be positive")
    return width_i, height_i


def _image_size(path: Path) -> tuple[int, int] | None:
    if not path.is_file():
        return None
    try:
        with Image.open(path) as image:
            return image.size
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"acad_png cannot be read as an image: {path}: {exc}") from exc


def _case_id(case: dict[str, Any], index: int) -> str:
    return _str(case.get("id") or case.get("drawing_id") or f"case{index:03d}")


def _resolve_path(manifest_dir: Path, value: Any) -> Path:
    path = Path(_str(value))
    if not path.is_absolute():
        path = manifest_dir / path
    return path


def validate_case(case: dict[str, Any], *, manifest_dir: Path, index: int) -> tuple[dict[str, Any], list[ValidationIssue]]:
    cid = _case_id(case, index)
    issues: list[ValidationIssue] = []

    def issue(severity: str, code: str, message: str) -> None:
        issues.append(ValidationIssue(cid, severity, code, message))

    drawing_id = _str(case.get("drawing_id"))
    source_dxf_raw = _str(case.get("source_dxf"))
    acad_png_raw = _str(case.get("acad_png"))
    capture_method = _str(case.get("capture_method")).lower()
    view_contract = _str(case.get("view_contract")).lower()

    if not drawing_id:
        issue("error", "missing_drawing_id", "drawing_id is required")
    if not source_dxf_raw:
        issue("error", "missing_source_dxf", "source_dxf is required")
    if not acad_png_raw:
        issue("error", "missing_acad_png", "acad_png is required")
    if not capture_method:
        issue("error", "missing_capture_method", "capture_method is required")
    if not view_contract:
        issue("error", "missing_view_contract", "view_contract is required")

    if capture_method in DIAGNOSTIC_CAPTURE_METHODS:
        issue(
            "error",
            "diagnostic_capture_method",
            f"capture_method={capture_method} is diagnostic-only and cannot gate X3 equivalence",
        )
    elif capture_method and capture_method not in GATE_CAPTURE_METHODS:
        issue("error", "unknown_capture_method", f"capture_method={capture_method} is not recognized")

    if view_contract and view_contract not in MATCHED_VIEW_CONTRACTS:
        issue("error", "unmatched_view_contract", f"view_contract={view_contract} is not a matched-view contract")

    source_dxf = _resolve_path(manifest_dir, source_dxf_raw) if source_dxf_raw else None
    acad_png = _resolve_path(manifest_dir, acad_png_raw) if acad_png_raw else None

    if source_dxf is not None and not source_dxf.is_file():
        issue("error", "source_dxf_missing", f"source_dxf not found: {source_dxf}")

    actual_size = None
    if acad_png is not None:
        try:
            actual_size = _image_size(acad_png)
        except ValueError as exc:
            issue("error", "invalid_acad_png", str(exc))
        else:
            if actual_size is None:
                issue("error", "acad_png_missing", f"acad_png not found: {acad_png}")

    expected_size = None
    try:
        expected_size = _expected_size(case)
    except (TypeError, ValueError) as exc:
        issue("error", "invalid_expected_size", str(exc))

    if actual_size is not None and expected_size is not None and actual_size != expected_size:
        issue(
            "error",
            "expected_size_mismatch",
            f"acad_png size {actual_size[0]}x{actual_size[1]} != expected {expected_size[0]}x{expected_size[1]}",
        )

    trust = "gate" if not any(i.severity == "error" for i in issues) else "blocked"
    normalized = {
        "id": cid,
        "drawing_id": drawing_id,
        "source_dxf": str(source_dxf) if source_dxf is not None else "",
        "acad_png": str(acad_png) if acad_png is not None else "",
        "capture_method": capture_method,
        "view_contract": view_contract,
        "expected_size": (
            {"width": expected_size[0], "height": expected_size[1]}
            if expected_size is not None else None
        ),
        "actual_size": (
            {"width": actual_size[0], "height": actual_size[1]}
            if actual_size is not None else None
        ),
        "trust": trust,
    }
    return normalized, issues


def validate_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    if data.get("schema") != SCHEMA:
        raise ValueError(f"manifest schema must be {SCHEMA}")
    cases_raw = data.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise ValueError("manifest cases must be a non-empty list")

    manifest_dir = path.parent
    cases: list[dict[str, Any]] = []
    issues: list[ValidationIssue] = []
    for index, case in enumerate(cases_raw, start=1):
        if not isinstance(case, dict):
            cid = f"case{index:03d}"
            issues.append(ValidationIssue(cid, "error", "case_not_object", "case must be an object"))
            continue
        normalized, case_issues = validate_case(case, manifest_dir=manifest_dir, index=index)
        cases.append(normalized)
        issues.extend(case_issues)

    error_count = sum(1 for issue in issues if issue.severity == "error")
    return {
        "schema": REPORT_SCHEMA,
        "manifest": str(path),
        "status": "pass" if error_count == 0 else "blocked",
        "case_count": len(cases),
        "error_count": error_count,
        "cases": cases,
        "issues": [asdict(issue) for issue in issues],
    }


def write_cases_for_batch(report: dict[str, Any], path: Path) -> None:
    cases = []
    for case in report["cases"]:
        if case["trust"] != "gate":
            continue
        cases.append({
            "id": case["id"],
            "acad": case["acad_png"],
            "ours": "",
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="acad_reference_manifest",
        description="Validate AutoCAD reference PNG manifests for matched-view X3 comparisons.")
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--batch-cases-out", type=Path, default=None,
                    help="write gate-trusted cases stub for autocad_batch_compare")
    args = ap.parse_args(argv)

    report = validate_manifest(args.manifest)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.batch_cases_out:
        write_cases_for_batch(report, args.batch_cases_out)

    print(f"AutoCAD reference manifest: {report['status']} ({report['error_count']} errors, {report['case_count']} cases)")
    for issue in report["issues"]:
        print(f"  {issue['severity']} {issue['case_id']} {issue['code']}: {issue['message']}")
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
