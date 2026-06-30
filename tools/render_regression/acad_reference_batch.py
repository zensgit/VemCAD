#!/usr/bin/env python3
"""Create manifest/candidate JSON files for a batch of AutoCAD reference cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acad_reference_manifest as arm  # noqa: E402

INTAKE_SCHEMA = "vemcad.acad_reference_intake/v1"
BATCH_ARTIFACT_INDEX_SCHEMA = "vemcad.acad_reference_batch_artifact_index/v1"


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _file_provenance(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def _near_white(rgb: tuple[int, int, int]) -> bool:
    return min(rgb) >= 245 and (max(rgb) - min(rgb)) <= 10


def _corner_white_ratio(image: Image.Image, *, sample_px: int = 12) -> float:
    rgb = image.convert("RGB")
    width, height = rgb.size
    sample_w = min(sample_px, width)
    sample_h = min(sample_px, height)
    if sample_w <= 0 or sample_h <= 0:
        return 0.0
    boxes = [
        (0, 0, sample_w, sample_h),
        (width - sample_w, 0, width, sample_h),
        (0, height - sample_h, sample_w, height),
        (width - sample_w, height - sample_h, width, height),
    ]
    total = 0
    near_white = 0
    for box in boxes:
        for pixel in rgb.crop(box).getdata():
            total += 1
            if _near_white(pixel):
                near_white += 1
    return near_white / total if total else 0.0


def _has_alpha(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA"):
        return True
    return "transparency" in image.info


def _inspect_reference_png(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    with Image.open(path) as image:
        width, height = image.size
        long_edge = max(width, height)
        ratio = _corner_white_ratio(image)
        alpha = _has_alpha(image)
        inspection = {
            "path": str(path),
            "width": width,
            "height": height,
            "long_edge": long_edge,
            "aspect_ratio": round(width / height, 6) if height else None,
            "mode": image.mode,
            "has_alpha": alpha,
            "corner_white_ratio": round(ratio, 4),
        }
        inspection.update(_file_provenance(path))
        if long_edge < 1600:
            issues.append({
                "severity": "warning",
                "code": "long_edge_below_requested",
                "message": f"long edge {long_edge}px is below the requested >=1600px capture contract",
            })
        if alpha:
            issues.append({
                "severity": "warning",
                "code": "alpha_channel_present",
                "message": "PNG has an alpha/transparency channel; export on a solid white background when possible",
            })
        if ratio < 0.95:
            issues.append({
                "severity": "warning",
                "code": "corner_background_not_white",
                "message": f"corner white ratio {ratio:.3f} is below 0.95; check for dark background, toolbar/chrome, or crop",
            })
    return inspection, issues


def _ink_profile(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        min_x = width
        min_y = height
        max_x = -1
        max_y = -1
        for y in range(height):
            for x, pixel in enumerate(rgb.crop((0, y, width, y + 1)).getdata()):
                if not _near_white(pixel):
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        if max_x < min_x or max_y < min_y:
            return {
                "status": "blank",
                "image_width": width,
                "image_height": height,
            }
        bbox_w = max_x - min_x + 1
        bbox_h = max_y - min_y + 1
        return {
            "status": "available",
            "image_width": width,
            "image_height": height,
            "bbox": [min_x, min_y, max_x, max_y],
            "bbox_width": bbox_w,
            "bbox_height": bbox_h,
            "bbox_aspect": round(bbox_w / bbox_h, 6) if bbox_h else None,
            "fill_x": round(bbox_w / width, 6) if width else None,
            "fill_y": round(bbox_h / height, 6) if height else None,
        }


def _identity_advisory(returned_png: Path, candidate_png: Path | None) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if candidate_png is None:
        return {"status": "unavailable", "reason": "candidate_missing"}, []
    try:
        returned = _ink_profile(returned_png)
        candidate = _ink_profile(candidate_png)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, []
    advisory: dict[str, Any] = {
        "status": "available",
        "diagnostic_only": True,
        "candidate_png": str(candidate_png),
        "returned_ink": returned,
        "candidate_ink": candidate,
    }
    issues: list[dict[str, str]] = []
    returned_aspect = returned.get("bbox_aspect")
    candidate_aspect = candidate.get("bbox_aspect")
    if isinstance(returned_aspect, (int, float)) and isinstance(candidate_aspect, (int, float)):
        aspect_delta = abs(float(returned_aspect) - float(candidate_aspect)) / max(
            float(returned_aspect),
            float(candidate_aspect),
        )
        advisory["ink_bbox_aspect_delta"] = round(aspect_delta, 6)
        if aspect_delta > 0.25:
            issues.append({
                "severity": "warning",
                "code": "ink_bbox_aspect_divergence",
                "message": (
                    f"returned/candidate ink bbox aspect differs by {aspect_delta:.3f}; "
                    "check for wrong drawing or capture-window mismatch"
                ),
            })
    return advisory, issues


def _resolve(base: Path, value: Any) -> str:
    raw = _str(value)
    if not raw:
        return ""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base / path
    return str(path.resolve())


def _required(item: dict[str, Any], key: str, index: int) -> str:
    value = _str(item.get(key))
    if not value:
        raise ValueError(f"case {index}: missing required field {key}")
    return value


def _diagnostics(item: dict[str, Any]) -> dict[str, str]:
    raw = item.get("diagnostics") or {}
    if not isinstance(raw, dict):
        raise ValueError("diagnostics must be an object when present")
    return {str(key): str(value) for key, value in sorted(raw.items())}


def _manifest_case(item: dict[str, Any], base: Path, index: int) -> dict[str, Any]:
    case_id = _required(item, "id", index)
    acad_png = Path(_resolve(base, _required(item, "acad_png", index)))
    expected_size = item.get("expected_size")
    if isinstance(expected_size, dict):
        width = int(expected_size["width"])
        height = int(expected_size["height"])
    elif isinstance(expected_size, (list, tuple)) and len(expected_size) == 2:
        width = int(expected_size[0])
        height = int(expected_size[1])
    else:
        width, height = _image_size(acad_png)
    return {
        "id": case_id,
        "drawing_id": _required(item, "drawing_id", index),
        "source_dxf": _resolve(base, _required(item, "source_dxf", index)),
        "acad_png": str(acad_png),
        "capture_method": _str(item.get("capture_method") or "plot-export"),
        "view_contract": _str(item.get("view_contract") or "model-extents"),
        "expected_size": {
            "width": width,
            "height": height,
        },
    }


def _candidate_case(item: dict[str, Any], base: Path, index: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": _required(item, "id", index),
        "ours": _resolve(base, _required(item, "ours", index)),
    }
    for key in ("render_report", "semantic_mask", "semantic_report"):
        value = _str(item.get(key))
        if value:
            payload[key] = _resolve(base, value)
    for key in ("render_image", "render_image_digest"):
        value = _str(item.get(key))
        if value:
            payload[key] = value
    diagnostics = _diagnostics(item)
    if diagnostics:
        payload["diagnostics"] = diagnostics
    return payload


def _load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("cases JSON must be a non-empty list")
    cases: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"case {index}: must be an object")
        cases.append(item)
    return cases


def _build_files(cases: list[dict[str, Any]], base: Path, out_dir: Path) -> tuple[Path, Path, dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": arm.SCHEMA,
        "cases": [
            _manifest_case(item, base, index)
            for index, item in enumerate(cases, start=1)
        ],
    }
    candidates = [
        _candidate_case(item, base, index)
        for index, item in enumerate(cases, start=1)
    ]
    manifest_path = out_dir / "acad_manifest.json"
    candidates_path = out_dir / "candidate_cases.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    candidates_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = arm.validate_manifest(manifest_path)
    return manifest_path, candidates_path, validation


def build_files(cases_json: Path, out_dir: Path) -> tuple[Path, Path, dict[str, Any]]:
    return _build_files(_load_cases(cases_json), cases_json.parent, out_dir)


def _load_candidate_map(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("candidate cases JSON must be a list")
    candidates: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"candidate case {index}: must be an object")
        case_id = _str(item.get("id"))
        if not case_id:
            raise ValueError(f"candidate case {index}: missing id")
        candidates[case_id] = item
    return candidates


def _load_request_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("reference request JSON must be an object")
    if data.get("schema") != "vemcad.acad_reference_request/v1":
        raise ValueError("reference request schema must be vemcad.acad_reference_request/v1")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("reference request must contain a non-empty cases list")
    for index, item in enumerate(cases, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"request case {index}: must be an object")
    return cases


def _filter_request_cases(cases: list[dict[str, Any]], case_ids: set[str] | None) -> list[dict[str, Any]]:
    if not case_ids:
        return cases
    selected = [case for case in cases if _str(case.get("id")) in case_ids]
    found = {_str(case.get("id")) for case in selected}
    missing = sorted(case_ids - found)
    if missing:
        raise ValueError(f"requested case id(s) not found in reference request: {', '.join(missing)}")
    return selected


def _fulfilled_cases(
    request_json: Path,
    *,
    candidate_cases: Path,
    reference_dir: Path,
    case_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    request_cases = _filter_request_cases(_load_request_cases(request_json), case_ids)
    candidates = _load_candidate_map(candidate_cases)
    fulfilled: list[dict[str, Any]] = []
    for index, request in enumerate(request_cases, start=1):
        case_id = _required(request, "id", index)
        candidate = candidates.get(case_id)
        if candidate is None:
            raise ValueError(f"request case {case_id}: missing candidate case")
        output_name = _required(request, "recommended_output_name", index)
        source_dxf = Path(_resolve(request_json.parent, _required(request, "source_dxf", index)))
        candidate_png = Path(_resolve(candidate_cases.parent, _required(candidate, "ours", index)))
        expected_source_sha = _str(request.get("source_dxf_sha256"))
        if expected_source_sha:
            actual_source = _file_provenance(source_dxf)
            if actual_source["sha256"] != expected_source_sha:
                raise ValueError(
                    f"request case {case_id}: source_dxf sha256 mismatch "
                    f"({actual_source['sha256']} != {expected_source_sha})"
                )
        expected_candidate_sha = _str(request.get("candidate_png_sha256"))
        if expected_candidate_sha:
            actual_candidate = _file_provenance(candidate_png)
            if actual_candidate["sha256"] != expected_candidate_sha:
                raise ValueError(
                    f"request case {case_id}: candidate PNG sha256 mismatch "
                    f"({actual_candidate['sha256']} != {expected_candidate_sha})"
                )
        item: dict[str, Any] = {
            "id": case_id,
            "drawing_id": _required(request, "drawing_id", index),
            "source_dxf": str(source_dxf),
            "acad_png": str((reference_dir / output_name).resolve()),
            "ours": str(candidate_png),
            "capture_method": _str(request.get("requested_capture_method") or "plot-export"),
            "view_contract": _str(request.get("requested_view_contract") or "model-extents"),
        }
        expected_size = request.get("requested_expected_size") or request.get("expected_size")
        if expected_size is not None:
            item["expected_size"] = expected_size
        for key in ("render_report", "semantic_mask", "semantic_report"):
            if key in candidate:
                item[key] = _resolve(candidate_cases.parent, candidate[key])
        for key in ("render_image", "render_image_digest", "diagnostics"):
            if key in candidate:
                item[key] = candidate[key]
        fulfilled.append(item)
    return fulfilled


def _write_missing_references_report(
    out_dir: Path,
    request_json: Path,
    *,
    reference_dir: Path,
    case_ids: set[str] | None = None,
) -> int:
    request_cases = _filter_request_cases(_load_request_cases(request_json), case_ids)
    missing: list[dict[str, str]] = []
    for index, request in enumerate(request_cases, start=1):
        case_id = _required(request, "id", index)
        output_name = _required(request, "recommended_output_name", index)
        expected_path = (reference_dir / output_name).resolve()
        if not expected_path.is_file():
            missing.append({
                "id": case_id,
                "drawing_id": _str(request.get("drawing_id")),
                "recommended_output_name": output_name,
                "expected_path": str(expected_path),
            })
    if not missing:
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "vemcad.acad_reference_missing/v1",
        "request": str(request_json.resolve()),
        "reference_dir": str(reference_dir.resolve()),
        "missing_count": len(missing),
        "missing": missing,
    }
    json_path = out_dir / "missing_references.json"
    md_path = out_dir / "missing_references.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Missing AutoCAD Reference PNGs",
        "",
        f"- request: `{request_json.resolve()}`",
        f"- reference_dir: `{reference_dir.resolve()}`",
        f"- missing_count: `{len(missing)}`",
        "",
        "| Case | Drawing | Expected PNG | Expected path |",
        "| --- | --- | --- | --- |",
    ]
    for item in missing:
        lines.append(
            f"| `{item['id']}` | {_str(item.get('drawing_id'))} | "
            f"`{item['recommended_output_name']}` | `{item['expected_path']}` |"
        )
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return len(missing)


def _existing_batch_artifacts(out_dir: Path) -> list[dict[str, str]]:
    known = (
        ("acad_manifest.json", "acad_manifest"),
        ("candidate_cases.json", "candidate_cases"),
        ("reference_intake.json", "reference_intake_json"),
        ("reference_intake.md", "reference_intake_markdown"),
        ("missing_references.json", "missing_references_json"),
        ("missing_references.md", "missing_references_markdown"),
    )
    artifacts: list[dict[str, str]] = []
    for name, kind in known:
        path = out_dir / name
        if path.is_file():
            artifacts.append({"kind": kind, "path": str(path)})
    return artifacts


def _clear_batch_outputs(out_dir: Path) -> None:
    for name, _kind in (
        ("acad_manifest.json", "acad_manifest"),
        ("candidate_cases.json", "candidate_cases"),
        ("reference_intake.json", "reference_intake_json"),
        ("reference_intake.md", "reference_intake_markdown"),
        ("missing_references.json", "missing_references_json"),
        ("missing_references.md", "missing_references_markdown"),
        ("artifact_index.json", "artifact_index"),
    ):
        path = out_dir / name
        if path.is_file():
            path.unlink()


def _write_batch_artifact_index(out_dir: Path) -> Path | None:
    artifacts = _existing_batch_artifacts(out_dir)
    if not artifacts:
        return None
    path = out_dir / "artifact_index.json"
    payload = {
        "schema": BATCH_ARTIFACT_INDEX_SCHEMA,
        "count": len(artifacts),
        "artifacts": artifacts,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_reference_intake_report(
    out_dir: Path,
    request_json: Path,
    *,
    candidate_cases: Path,
    reference_dir: Path,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    request_cases = _filter_request_cases(_load_request_cases(request_json), case_ids)
    candidates = _load_candidate_map(candidate_cases)
    rows: list[dict[str, Any]] = []
    error_count = 0
    warning_count = 0
    for index, request in enumerate(request_cases, start=1):
        case_id = _required(request, "id", index)
        output_name = _required(request, "recommended_output_name", index)
        expected_path = (reference_dir / output_name).resolve()
        row_issues: list[dict[str, str]] = []
        inspection: dict[str, Any] = {"path": str(expected_path)}
        try:
            inspection, row_issues = _inspect_reference_png(expected_path)
        except Exception as exc:
            row_issues = [{
                "severity": "error",
                "code": "reference_png_unreadable",
                "message": str(exc),
            }]
        candidate = candidates.get(case_id)
        candidate_png = None
        if candidate is not None:
            candidate_raw = _str(candidate.get("ours"))
            if candidate_raw:
                candidate_png = Path(_resolve(candidate_cases.parent, candidate_raw))
        advisory, advisory_issues = _identity_advisory(expected_path, candidate_png)
        inspection["identity_advisory"] = advisory
        row_issues.extend(advisory_issues)
        for issue in row_issues:
            if issue["severity"] == "error":
                error_count += 1
            elif issue["severity"] == "warning":
                warning_count += 1
        rows.append({
            "id": case_id,
            "drawing_id": _str(request.get("drawing_id")),
            "recommended_output_name": output_name,
            "inspection": inspection,
            "issues": row_issues,
        })
    status = "blocked" if error_count else ("review" if warning_count else "pass")
    payload = {
        "schema": INTAKE_SCHEMA,
        "request": str(request_json.resolve()),
        "reference_dir": str(reference_dir.resolve()),
        "status": status,
        "case_count": len(rows),
        "error_count": error_count,
        "warning_count": warning_count,
        "checks": {
            "long_edge_min_px": 1600,
            "corner_white_ratio_min": 0.95,
            "alpha_channel": "warning",
        },
        "cases": rows,
        "boundary": {
            "autocad_equivalence_claim": False,
            "replaces_x3_compare": False,
            "purpose": "preflight returned AutoCAD PNGs before matched-view comparison",
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "reference_intake.json"
    md_path = out_dir / "reference_intake.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# AutoCAD Reference Intake Preflight",
        "",
        f"- status: `{status}`",
        f"- request: `{request_json.resolve()}`",
        f"- reference_dir: `{reference_dir.resolve()}`",
        f"- cases: `{len(rows)}`",
        f"- errors: `{error_count}`",
        f"- warnings: `{warning_count}`",
        "",
        "This is a capture-quality preflight only. It does not compare against VemCAD and does not claim AutoCAD equivalence.",
        "",
        "| Case | Drawing | PNG | Size | Long edge | Corner white | Issues |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        inspection = row["inspection"]
        issues = row["issues"]
        issue_text = ", ".join(f"{item['severity']}:{item['code']}" for item in issues) or "-"
        size = (
            f"{inspection.get('width')}x{inspection.get('height')}"
            if inspection.get("width") and inspection.get("height") else "-"
        )
        lines.append(
            f"| `{row['id']}` | {_str(row.get('drawing_id'))} | "
            f"`{row['recommended_output_name']}` | {size} | "
            f"{inspection.get('long_edge', '-')} | {inspection.get('corner_white_ratio', '-')} | "
            f"{issue_text} |"
        )
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return payload


def build_files_from_request(
    request_json: Path,
    *,
    candidate_cases: Path,
    reference_dir: Path,
    out_dir: Path,
    case_ids: set[str] | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    missing_count = _write_missing_references_report(
        out_dir,
        request_json,
        reference_dir=reference_dir,
        case_ids=case_ids,
    )
    if missing_count:
        raise ValueError(f"missing {missing_count} returned AutoCAD PNG(s); see {out_dir / 'missing_references.md'}")
    intake = _write_reference_intake_report(
        out_dir,
        request_json,
        candidate_cases=candidate_cases,
        reference_dir=reference_dir,
        case_ids=case_ids,
    )
    if intake["status"] == "blocked":
        raise ValueError(f"returned AutoCAD PNG intake blocked; see {out_dir / 'reference_intake.md'}")
    return _build_files(
        _fulfilled_cases(
            request_json,
            candidate_cases=candidate_cases,
            reference_dir=reference_dir,
            case_ids=case_ids,
        ),
        Path.cwd(),
        out_dir,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acad_reference_batch",
        description="Create validated AutoCAD manifest + candidate case files from a cases JSON list.")
    parser.add_argument("--cases", type=Path, default=None,
                        help="JSON list of AutoCAD reference cases")
    parser.add_argument("--from-request", type=Path, default=None,
                        help="reference_request.json produced by acad_manifest_compare.py")
    parser.add_argument("--candidate-cases", type=Path, default=None,
                        help="original candidate_cases.json, required with --from-request")
    parser.add_argument("--reference-dir", type=Path, default=None,
                        help="directory containing returned AutoCAD PNGs, required with --from-request")
    parser.add_argument("--case-id", action="append", default=None,
                        help="with --from-request, fulfill only this case id; may repeat")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    _clear_batch_outputs(args.out_dir)

    try:
        if args.from_request is not None:
            if args.candidate_cases is None or args.reference_dir is None:
                raise ValueError("--candidate-cases and --reference-dir are required with --from-request")
            manifest_path, candidates_path, validation = build_files_from_request(
                args.from_request,
                candidate_cases=args.candidate_cases,
                reference_dir=args.reference_dir,
                out_dir=args.out_dir,
                case_ids=set(args.case_id or []) or None,
            )
        else:
            if args.cases is None:
                raise ValueError("--cases is required unless --from-request is set")
            manifest_path, candidates_path, validation = build_files(args.cases, args.out_dir)
    except Exception as exc:
        index_path = _write_batch_artifact_index(args.out_dir)
        print(f"AutoCAD reference batch: blocked ({exc})", file=sys.stderr)
        if index_path is not None:
            print(f"  artifact index : {index_path}", file=sys.stderr)
        return 2

    index_path = _write_batch_artifact_index(args.out_dir)
    print(f"AutoCAD reference batch: {validation['status']} ({validation['case_count']} cases)")
    print(f"  manifest       : {manifest_path}")
    print(f"  candidate cases: {candidates_path}")
    if index_path is not None:
        print(f"  artifact index : {index_path}")
    if validation["issues"]:
        for issue in validation["issues"]:
            print(f"  {issue['severity']} {issue['case_id']} {issue['code']}: {issue['message']}")
    return 0 if validation["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
