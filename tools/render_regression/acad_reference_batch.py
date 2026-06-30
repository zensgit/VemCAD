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
import acad_artifact_route as artifact_route  # noqa: E402

INTAKE_SCHEMA = "vemcad.acad_reference_intake/v1"
BATCH_ARTIFACT_INDEX_SCHEMA = "vemcad.acad_reference_batch_artifact_index/v1"
REQUEST_VALIDATION_SCHEMA = "vemcad.acad_reference_request_validation/v1"
BATCH_ARTIFACT_BOUNDARY = {
    "renders_dxf": False,
    "compares_renders": False,
    "changes_x3_scoring": False,
    "changes_renderer": False,
    "requires_viewspace_match": False,
    "autocad_equivalence_claim": False,
}


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _tsv(value: Any) -> str:
    return _str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _md_table_cell(value: Any) -> str:
    text = _str(value)
    if not text:
        return "-"
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("|", "\\|").replace("`", "\\`")


def _md_code_cell(value: Any) -> str:
    text = _str(value)
    if not text:
        text = "-"
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("|", "\\|")
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


def _expected_size_text(expected_size: Any) -> str:
    if isinstance(expected_size, dict):
        width = expected_size.get("width")
        height = expected_size.get("height")
    elif isinstance(expected_size, (list, tuple)) and len(expected_size) == 2:
        width, height = expected_size
    else:
        return ""
    width_text = _str(width)
    height_text = _str(height)
    return f"{width_text}x{height_text}" if width_text and height_text else ""


def _expected_size_dimensions(expected_size: Any) -> tuple[int, int] | None:
    if isinstance(expected_size, dict):
        width = expected_size.get("width")
        height = expected_size.get("height")
    elif isinstance(expected_size, (list, tuple)) and len(expected_size) == 2:
        width, height = expected_size
    else:
        return None
    try:
        width_int = int(width)
        height_int = int(height)
    except Exception:
        return None
    if width_int <= 0 or height_int <= 0:
        return None
    return width_int, height_int


def _provenance_text(provenance: Any) -> str:
    if not isinstance(provenance, dict):
        return ""
    parts: list[str] = []
    sha = _str(provenance.get("sha256"))
    size = provenance.get("size_bytes")
    if sha:
        parts.append(f"sha256={sha}")
    if size is not None:
        parts.append(f"size={size}")
    return " ".join(parts)


def _issue_code_labels(issues: Any) -> str:
    if not isinstance(issues, list):
        return ""
    labels: list[str] = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        code = _str(item.get("code"))
        if not code:
            continue
        severity = _str(item.get("severity"))
        labels.append(f"{severity}:{code}" if severity else code)
    return ",".join(labels)


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


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
        code = _str(issue.get("code"))
        if code:
            counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _format_counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _format_boundary(boundary: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(boundary.items())) or "none"


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
    if returned.get("status") == "blank":
        issues.append({
            "severity": "warning",
            "code": "returned_reference_blank",
            "message": (
                "returned AutoCAD reference PNG has no detected ink; check for a blank export, "
                "wrong file, or unmatched capture window before trusting X3"
            ),
        })
    if candidate.get("status") == "blank":
        issues.append({
            "severity": "warning",
            "code": "candidate_render_blank",
            "message": (
                "candidate VemCAD render PNG has no detected ink; check the render artifact "
                "before trusting X3"
            ),
        })
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


def _identity_advisory_text(advisory: dict[str, Any]) -> str:
    status = _str(advisory.get("status"))
    if not status:
        return "-"
    parts = [f"status={status}"]
    returned = advisory.get("returned_ink")
    if isinstance(returned, dict) and returned.get("status"):
        parts.append(f"returned={returned.get('status')}")
    candidate = advisory.get("candidate_ink")
    if isinstance(candidate, dict) and candidate.get("status"):
        parts.append(f"candidate={candidate.get('status')}")
    if advisory.get("ink_bbox_aspect_delta") is not None:
        parts.append(f"aspect_delta={advisory.get('ink_bbox_aspect_delta')}")
    if advisory.get("diagnostic_only") is True:
        parts.append("diagnostic-only")
    if advisory.get("reason"):
        parts.append(f"reason={advisory.get('reason')}")
    if advisory.get("error"):
        parts.append(f"error={advisory.get('error')}")
    return " ".join(_str(part) for part in parts if _str(part))


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


def _load_candidate_map_with_issues(
    path: Path,
    case_ids: set[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("candidate cases JSON must be a list")
    candidates: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, str]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            issues.append({
                "severity": "error",
                "case_id": f"candidate{index:03d}",
                "code": "candidate_not_object",
                "message": "candidate case must be an object",
            })
            continue
        case_id = _str(item.get("id"))
        if case_ids is not None and case_id not in case_ids:
            continue
        if not case_id:
            issues.append({
                "severity": "error",
                "case_id": f"candidate{index:03d}",
                "code": "candidate_missing_id",
                "message": "candidate case is missing id",
            })
            continue
        if case_id in candidates:
            issues.append({
                "severity": "error",
                "case_id": case_id,
                "code": "duplicate_candidate_id",
                "message": f"candidate id {case_id} appears more than once",
            })
            continue
        candidates[case_id] = item
    return candidates, issues


def _load_request_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("reference request JSON must be an object")
    if data.get("schema") != "vemcad.acad_reference_request/v1":
        raise ValueError("reference request schema must be vemcad.acad_reference_request/v1")
    return data


def _load_request_cases(path: Path) -> list[dict[str, Any]]:
    return _request_cases(_load_request_payload(path))


def _request_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("reference request must contain a non-empty cases list")
    for index, item in enumerate(cases, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"request case {index}: must be an object")
    return cases


def _request_boundary(data: dict[str, Any]) -> dict[str, Any]:
    boundary = data.get("boundary")
    return dict(boundary) if isinstance(boundary, dict) else {}


def _request_boundary_requirement_issues(
    boundary: dict[str, Any],
    expectations: list[tuple[str, Any]],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for key, expected in expectations:
        if key not in boundary:
            issues.append({
                "severity": "error",
                "case_id": "<request>",
                "code": "missing_request_boundary",
                "message": f"source request boundary is missing {key}",
            })
            continue
        actual = boundary.get(key)
        if actual != expected:
            issues.append({
                "severity": "error",
                "case_id": "<request>",
                "code": "request_boundary_mismatch",
                "message": f"source request boundary {key}={actual!r} != {expected!r}",
            })
    return issues


def _filter_request_cases(cases: list[dict[str, Any]], case_ids: set[str] | None) -> list[dict[str, Any]]:
    if not case_ids:
        return cases
    selected = [case for case in cases if _str(case.get("id")) in case_ids]
    found = {_str(case.get("id")) for case in selected}
    missing = sorted(case_ids - found)
    if missing:
        raise ValueError(f"requested case id(s) not found in reference request: {', '.join(missing)}")
    return selected


def _safe_output_name_issues(case_id: str, output_name: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    path = Path(output_name)
    if (
        "\\" in output_name
        or path.is_absolute()
        or path.name != output_name
        or output_name in (".", "..")
        or ".." in path.parts
    ):
        issues.append({
            "severity": "error",
            "case_id": case_id,
            "code": "unsafe_recommended_output_name",
            "message": f"recommended_output_name must be a plain filename: {output_name}",
        })
    return issues


def _expected_size_issues(case_id: str, expected_size: Any) -> list[dict[str, str]]:
    if expected_size is None:
        return []
    width = None
    height = None
    if isinstance(expected_size, dict):
        width = expected_size.get("width")
        height = expected_size.get("height")
    elif isinstance(expected_size, (list, tuple)) and len(expected_size) == 2:
        width, height = expected_size
    try:
        width_i = int(width)
        height_i = int(height)
    except Exception:
        width_i = 0
        height_i = 0
    if width_i <= 0 or height_i <= 0:
        return [{
            "severity": "error",
            "case_id": case_id,
            "code": "invalid_requested_expected_size",
            "message": "requested_expected_size/expected_size must contain positive width and height",
        }]
    return []


def _capture_contract_issues(case_id: str, capture_method: Any, view_contract: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    method = _str(capture_method or "plot-export").lower()
    view = _str(view_contract or "model-extents").lower()
    if method in arm.DIAGNOSTIC_CAPTURE_METHODS:
        issues.append({
            "severity": "error",
            "case_id": case_id,
            "code": "diagnostic_requested_capture_method",
            "message": f"requested_capture_method={method} is diagnostic-only and cannot gate X3 equivalence",
        })
    elif method and method not in arm.GATE_CAPTURE_METHODS:
        issues.append({
            "severity": "error",
            "case_id": case_id,
            "code": "unknown_requested_capture_method",
            "message": f"requested_capture_method={method} is not recognized",
        })
    if view and view not in arm.MATCHED_VIEW_CONTRACTS:
        issues.append({
            "severity": "error",
            "case_id": case_id,
            "code": "unmatched_requested_view_contract",
            "message": f"requested_view_contract={view} is not a matched-view contract",
        })
    return issues


def _size_mismatch_issue(case_id: str, label: str, declared: Any, actual: int) -> list[dict[str, str]]:
    if declared is None:
        return []
    try:
        declared_int = int(declared)
    except Exception:
        return [{
            "severity": "error",
            "case_id": case_id,
            "code": f"{label}_size_invalid",
            "message": f"{label} size declaration must be an integer",
        }]
    if declared_int != actual:
        return [{
            "severity": "error",
            "case_id": case_id,
            "code": f"{label}_size_mismatch",
            "message": f"{label} size mismatch ({actual} != {declared_int})",
        }]
    return []


def _sha_mismatch_issue(case_id: str, label: str, declared: Any, actual: str) -> list[dict[str, str]]:
    expected = _str(declared)
    if not expected:
        return []
    if expected != actual:
        return [{
            "severity": "error",
            "case_id": case_id,
            "code": f"{label}_sha256_mismatch",
            "message": f"{label} sha256 mismatch ({actual} != {expected})",
        }]
    return []


def _write_reference_request_validation_report(
    out_dir: Path,
    request_json: Path,
    *,
    candidate_cases: Path,
    case_ids: set[str] | None = None,
    request_boundary_expectations: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    request_payload = _load_request_payload(request_json)
    request_boundary = _request_boundary(request_payload)
    request_cases = _filter_request_cases(_request_cases(request_payload), case_ids)
    selected_case_ids = {_str(item.get("id")) for item in request_cases if _str(item.get("id"))}
    candidates, global_issues = _load_candidate_map_with_issues(
        candidate_cases,
        selected_case_ids if case_ids else None,
    )
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = [dict(item) for item in global_issues]
    issues.extend(_request_boundary_requirement_issues(
        request_boundary,
        request_boundary_expectations or [],
    ))
    seen_request_ids: set[str] = set()
    seen_output_names: dict[str, str] = {}

    for index, request in enumerate(request_cases, start=1):
        case_id = _str(request.get("id")) or f"case{index:03d}"
        row_issues: list[dict[str, str]] = []
        if not _str(request.get("id")):
            row_issues.append({
                "severity": "error",
                "case_id": case_id,
                "code": "request_missing_id",
                "message": "request case is missing id",
            })
        elif case_id in seen_request_ids:
            row_issues.append({
                "severity": "error",
                "case_id": case_id,
                "code": "duplicate_request_id",
                "message": f"request id {case_id} appears more than once",
            })
        seen_request_ids.add(case_id)

        output_name = _str(request.get("recommended_output_name"))
        if not output_name:
            row_issues.append({
                "severity": "error",
                "case_id": case_id,
                "code": "missing_recommended_output_name",
                "message": "request case is missing recommended_output_name",
            })
        else:
            row_issues.extend(_safe_output_name_issues(case_id, output_name))
            previous = seen_output_names.get(output_name)
            if previous is not None:
                row_issues.append({
                    "severity": "error",
                    "case_id": case_id,
                    "code": "duplicate_recommended_output_name",
                    "message": f"recommended output {output_name} is also used by {previous}",
                })
            seen_output_names[output_name] = case_id

        source_path = None
        source_provenance = None
        source_raw = _str(request.get("source_dxf"))
        if not source_raw:
            row_issues.append({
                "severity": "error",
                "case_id": case_id,
                "code": "missing_source_dxf",
                "message": "request case is missing source_dxf",
            })
        else:
            source_path = Path(_resolve(request_json.parent, source_raw))
            if not source_path.is_file():
                row_issues.append({
                    "severity": "error",
                    "case_id": case_id,
                    "code": "source_dxf_missing",
                    "message": f"source DXF not found: {source_path}",
                })
            else:
                source_provenance = _file_provenance(source_path)
                row_issues.extend(_sha_mismatch_issue(
                    case_id,
                    "source_dxf",
                    request.get("source_dxf_sha256"),
                    source_provenance["sha256"],
                ))
                row_issues.extend(_size_mismatch_issue(
                    case_id,
                    "source_dxf",
                    request.get("source_dxf_size_bytes"),
                    source_provenance["size_bytes"],
                ))

        candidate = candidates.get(case_id)
        candidate_path = None
        candidate_provenance = None
        if candidate is None:
            row_issues.append({
                "severity": "error",
                "case_id": case_id,
                "code": "candidate_missing",
                "message": f"candidate case {case_id} is missing",
            })
        else:
            candidate_raw = _str(candidate.get("ours"))
            if not candidate_raw:
                row_issues.append({
                    "severity": "error",
                    "case_id": case_id,
                    "code": "candidate_png_missing_field",
                    "message": "candidate case is missing ours",
                })
            else:
                candidate_path = Path(_resolve(candidate_cases.parent, candidate_raw))
                if not candidate_path.is_file():
                    row_issues.append({
                        "severity": "error",
                        "case_id": case_id,
                        "code": "candidate_png_missing",
                        "message": f"candidate PNG not found: {candidate_path}",
                    })
                else:
                    candidate_provenance = _file_provenance(candidate_path)
                    row_issues.extend(_sha_mismatch_issue(
                        case_id,
                        "candidate_png",
                        request.get("candidate_png_sha256"),
                        candidate_provenance["sha256"],
                    ))
                    row_issues.extend(_size_mismatch_issue(
                        case_id,
                        "candidate_png",
                        request.get("candidate_png_size_bytes"),
                        candidate_provenance["size_bytes"],
                    ))

        expected_size = request.get("requested_expected_size") or request.get("expected_size")
        row_issues.extend(_expected_size_issues(case_id, expected_size))
        row_issues.extend(_capture_contract_issues(
            case_id,
            request.get("requested_capture_method"),
            request.get("requested_view_contract"),
        ))
        issues.extend(row_issues)
        rows.append({
            "id": case_id,
            "drawing_id": _str(request.get("drawing_id")),
            "recommended_output_name": output_name,
            "source_dxf": str(source_path) if source_path else "",
            "candidate_png": str(candidate_path) if candidate_path else "",
            "requested_capture_method": _str(request.get("requested_capture_method") or "plot-export").lower(),
            "requested_view_contract": _str(request.get("requested_view_contract") or "model-extents").lower(),
            "requested_expected_size": _expected_size_text(expected_size),
            "source_dxf_provenance": source_provenance,
            "candidate_png_provenance": candidate_provenance,
            "issues": row_issues,
        })

    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    issue_code_counts = _issue_code_counts({"issues": issues})
    status = "blocked" if error_count else ("review" if warning_count else "pass")
    payload = {
        "schema": REQUEST_VALIDATION_SCHEMA,
        "request": str(request_json.resolve()),
        "candidate_cases": str(candidate_cases.resolve()),
        "status": status,
        "case_count": len(rows),
        "error_count": error_count,
        "warning_count": warning_count,
        "issue_code_counts": issue_code_counts,
        "source_request_boundary": request_boundary,
        "cases": rows,
        "issues": issues,
        "boundary": {
            "autocad_equivalence_claim": False,
            "requires_returned_autocad_png": False,
            "purpose": "validate request package provenance before AutoCAD PNG fulfilment",
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "reference_request_validation.json"
    md_path = out_dir / "reference_request_validation.md"
    tsv_path = out_dir / "reference_request_validation.tsv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with tsv_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "id\tdrawing_id\trecommended_output_name\trequested_capture_method\t"
            "requested_view_contract\trequested_expected_size\tsource_dxf\tsource_dxf_sha256\t"
            "source_dxf_size_bytes\tcandidate_png\tcandidate_png_sha256\tcandidate_png_size_bytes\t"
            "issue_codes\n"
        )
        for row in rows:
            source_prov = row.get("source_dxf_provenance")
            if not isinstance(source_prov, dict):
                source_prov = {}
            candidate_prov = row.get("candidate_png_provenance")
            if not isinstance(candidate_prov, dict):
                candidate_prov = {}
            issue_codes = _issue_code_labels(row.get("issues"))
            handle.write(
                f"{_tsv(row.get('id'))}\t"
                f"{_tsv(row.get('drawing_id'))}\t"
                f"{_tsv(row.get('recommended_output_name'))}\t"
                f"{_tsv(row.get('requested_capture_method'))}\t"
                f"{_tsv(row.get('requested_view_contract'))}\t"
                f"{_tsv(row.get('requested_expected_size'))}\t"
                f"{_tsv(row.get('source_dxf'))}\t"
                f"{_tsv(source_prov.get('sha256'))}\t"
                f"{_tsv(source_prov.get('size_bytes'))}\t"
                f"{_tsv(row.get('candidate_png'))}\t"
                f"{_tsv(candidate_prov.get('sha256'))}\t"
                f"{_tsv(candidate_prov.get('size_bytes'))}\t"
                f"{_tsv(issue_codes)}\n"
            )
    lines = [
        "# AutoCAD Reference Request Validation",
        "",
        f"- status: `{status}`",
        f"- request: `{request_json.resolve()}`",
        f"- candidate_cases: `{candidate_cases.resolve()}`",
        f"- reference_request_validation_tsv: `{tsv_path}`",
        f"- cases: `{len(rows)}`",
        f"- errors: `{error_count}`",
        f"- warnings: `{warning_count}`",
        f"- issue_code_counts: `{_format_counts(issue_code_counts)}`",
        f"- source_request_boundary: `{_format_boundary(request_boundary)}`",
        "",
        "This validates request-package identity and provenance before AutoCAD PNG fulfilment. "
        "It does not compare renders and does not claim AutoCAD equivalence.",
        "",
        (
            "| Case | Drawing | Output PNG | Capture | View | Expected size | "
            "Source | Source provenance | Candidate | Candidate provenance | Issues |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        issue_text = ", ".join(f"{item['severity']}:{item['code']}" for item in row["issues"]) or "-"
        lines.append(
            f"| {_md_code_cell(row['id'])} | {_md_table_cell(row.get('drawing_id'))} | "
            f"{_md_code_cell(row['recommended_output_name'])} | {_md_code_cell(row.get('requested_capture_method'))} | "
            f"{_md_code_cell(row.get('requested_view_contract'))} | "
            f"{_md_code_cell(row.get('requested_expected_size'))} | "
            f"{_md_code_cell(row.get('source_dxf'))} | "
            f"{_md_code_cell(_provenance_text(row.get('source_dxf_provenance')))} | "
            f"{_md_code_cell(row.get('candidate_png'))} | "
            f"{_md_code_cell(_provenance_text(row.get('candidate_png_provenance')))} | "
            f"{_md_table_cell(issue_text)} |"
        )
    if global_issues:
        lines.extend(["", "## Candidate File Issues", ""])
        for issue in global_issues:
            lines.append(f"- `{issue['severity']}:{issue['code']}` {issue['message']}")
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return payload


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
            expected_size = request.get("requested_expected_size") or request.get("expected_size")
            source_dxf = _resolve(request_json.parent, request.get("source_dxf"))
            missing.append({
                "id": case_id,
                "drawing_id": _str(request.get("drawing_id")),
                "source_dxf": source_dxf,
                "source_dxf_sha256": _str(request.get("source_dxf_sha256")),
                "recommended_output_name": output_name,
                "expected_path": str(expected_path),
                "requested_capture_method": _str(request.get("requested_capture_method") or "plot-export"),
                "requested_view_contract": _str(request.get("requested_view_contract") or "model-extents"),
                "requested_expected_size": _expected_size_text(expected_size),
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
    tsv_path = out_dir / "missing_references.tsv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with tsv_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "id\tdrawing_id\tsource_dxf\tsource_dxf_sha256\trecommended_output_name\texpected_path\t"
            "requested_capture_method\trequested_view_contract\trequested_expected_size\n"
        )
        for item in missing:
            handle.write(
                f"{_tsv(item['id'])}\t"
                f"{_tsv(item.get('drawing_id'))}\t"
                f"{_tsv(item.get('source_dxf'))}\t"
                f"{_tsv(item.get('source_dxf_sha256'))}\t"
                f"{_tsv(item['recommended_output_name'])}\t"
                f"{_tsv(item['expected_path'])}\t"
                f"{_tsv(item.get('requested_capture_method'))}\t"
                f"{_tsv(item.get('requested_view_contract'))}\t"
                f"{_tsv(item.get('requested_expected_size'))}\n"
            )
    lines = [
        "# Missing AutoCAD Reference PNGs",
        "",
        f"- request: `{request_json.resolve()}`",
        f"- reference_dir: `{reference_dir.resolve()}`",
        f"- missing_count: `{len(missing)}`",
        f"- missing_references_tsv: `{tsv_path}`",
        "",
        "| Case | Drawing | Source DXF | Source SHA256 | Expected PNG | Capture | View | Expected size | Expected path |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in missing:
        lines.append(
            f"| {_md_code_cell(item['id'])} | {_md_table_cell(item.get('drawing_id'))} | "
            f"{_md_code_cell(item.get('source_dxf'))} | "
            f"{_md_code_cell(item.get('source_dxf_sha256'))} | "
            f"{_md_code_cell(item['recommended_output_name'])} | "
            f"{_md_code_cell(item.get('requested_capture_method'))} | "
            f"{_md_code_cell(item.get('requested_view_contract'))} | "
            f"{_md_code_cell(item.get('requested_expected_size'))} | "
            f"{_md_code_cell(item['expected_path'])} |"
        )
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return len(missing)


def _existing_batch_artifacts(out_dir: Path) -> list[dict[str, str]]:
    known = (
        ("acad_manifest.json", "acad_manifest"),
        ("candidate_cases.json", "candidate_cases"),
        ("reference_intake.json", "reference_intake_json"),
        ("reference_intake.md", "reference_intake_markdown"),
        ("reference_intake.tsv", "reference_intake_tsv"),
        ("missing_references.json", "missing_references_json"),
        ("missing_references.md", "missing_references_markdown"),
        ("missing_references.tsv", "missing_references_tsv"),
        ("reference_request_validation.json", "reference_request_validation_json"),
        ("reference_request_validation.md", "reference_request_validation_markdown"),
        ("reference_request_validation.tsv", "reference_request_validation_tsv"),
        ("route_summary.json", "route_summary_json"),
        ("route_summary.md", "route_summary_markdown"),
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
        ("reference_intake.tsv", "reference_intake_tsv"),
        ("missing_references.json", "missing_references_json"),
        ("missing_references.md", "missing_references_markdown"),
        ("missing_references.tsv", "missing_references_tsv"),
        ("reference_request_validation.json", "reference_request_validation_json"),
        ("reference_request_validation.md", "reference_request_validation_markdown"),
        ("reference_request_validation.tsv", "reference_request_validation_tsv"),
        ("route_summary.json", "route_summary_json"),
        ("route_summary.md", "route_summary_markdown"),
        ("artifact_index.json", "artifact_index"),
    ):
        path = out_dir / name
        if path.is_file():
            path.unlink()


def _write_batch_artifact_index(
    out_dir: Path,
    validation: dict[str, Any] | None = None,
    run_metadata: dict[str, Any] | None = None,
) -> Path | None:
    artifacts = _existing_batch_artifacts(out_dir)
    if not artifacts:
        return None
    route_summary_json = out_dir / "route_summary.json"
    route_summary_md = out_dir / "route_summary.md"
    existing_kinds = {item["kind"] for item in artifacts}
    if "route_summary_json" not in existing_kinds:
        artifacts.append({"kind": "route_summary_json", "path": str(route_summary_json)})
    if "route_summary_markdown" not in existing_kinds:
        artifacts.append({"kind": "route_summary_markdown", "path": str(route_summary_md)})
    path = out_dir / "artifact_index.json"
    metadata = _batch_index_metadata(out_dir, batch_validation=validation)
    payload = {
        "schema": BATCH_ARTIFACT_INDEX_SCHEMA,
        "boundary": dict(BATCH_ARTIFACT_BOUNDARY),
        **metadata,
        **(run_metadata or {}),
        "count": len(artifacts),
        "artifacts": artifacts,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_batch_route_report(index_path: Path | None) -> dict[str, Any] | None:
    if index_path is None:
        return None
    route_payload = artifact_route.route_artifact_index(index_path)
    artifact_route.write_route_report_files(
        route_payload,
        out_json=index_path.parent / "route_summary.json",
        out_md=index_path.parent / "route_summary.md",
    )
    return route_payload


def _print_route_summary(out_dir: Path, route_payload: dict[str, Any] | None, *, stream: Any = None) -> None:
    if route_payload is None:
        return
    action = route_payload.get("recommended_next_action") or {}
    target = stream or sys.stdout
    print(f"  route summary  : {out_dir / 'route_summary.md'}", file=target)
    print(f"  recommended next action: {action.get('code', '')}", file=target)
    print(f"  recommended next action domain: {action.get('domain', '')}", file=target)
    if action.get("artifact"):
        print(f"  recommended next action artifact: {action.get('artifact', '')}", file=target)
    if route_payload.get("action_artifact_resolved"):
        print(
            f"  recommended next action artifact resolved: {route_payload['action_artifact_resolved']}",
            file=target,
        )
        print(
            f"  recommended next action artifact exists: {bool(route_payload.get('action_artifact_exists'))}",
            file=target,
        )


def _batch_final_exit_code(
    status: str,
    *,
    fail_on_input_review: bool,
) -> int:
    if status == "pass":
        return 0
    if status == "review":
        return 2 if fail_on_input_review else 0
    return 2


def _batch_index_metadata(out_dir: Path, batch_validation: dict[str, Any] | None = None) -> dict[str, Any]:
    request_validation = _read_json(out_dir / "reference_request_validation.json")
    intake = _read_json(out_dir / "reference_intake.json")
    missing = _read_json(out_dir / "missing_references.json")
    manifest = _read_json(out_dir / "acad_manifest.json")

    metadata: dict[str, Any] = {
        "stage": "",
        "status": "",
        "case_count": None,
        "error_count": None,
        "warning_count": None,
    }
    if request_validation:
        source_request_boundary = request_validation.get("source_request_boundary")
        metadata.update({
            "stage": "request_validation",
            "status": str(request_validation.get("status") or ""),
            "case_count": request_validation.get("case_count"),
            "error_count": request_validation.get("error_count"),
            "warning_count": request_validation.get("warning_count"),
            "reference_request_validation_status": str(request_validation.get("status") or ""),
            "reference_request_validation_issue_code_counts": _issue_code_counts(request_validation),
        })
        if isinstance(source_request_boundary, dict):
            metadata["source_request_boundary"] = dict(source_request_boundary)
    if missing:
        metadata.update({
            "stage": "missing_references",
            "status": "blocked",
            "case_count": missing.get("missing_count"),
            "error_count": missing.get("missing_count"),
            "warning_count": 0,
            "missing_count": missing.get("missing_count"),
        })
    if intake:
        metadata.update({
            "stage": "reference_intake",
            "status": str(intake.get("status") or ""),
            "case_count": intake.get("case_count"),
            "error_count": intake.get("error_count"),
            "warning_count": intake.get("warning_count"),
            "reference_intake_status": str(intake.get("status") or ""),
            "reference_intake_issue_code_counts": _issue_code_counts(intake),
        })
    if not request_validation and not missing and not intake and manifest:
        metadata.update({
            "stage": "manifest",
            "status": "pass",
            "case_count": len(manifest.get("cases") or []),
            "error_count": 0,
            "warning_count": 0,
        })
    if batch_validation:
        batch_status = str(batch_validation.get("status") or "")
        metadata["batch_validation_status"] = batch_status
        if batch_status != "pass":
            metadata.update({
                "status": batch_status,
                "case_count": batch_validation.get("case_count"),
                "error_count": sum(1 for issue in batch_validation.get("issues") or [] if issue.get("severity") == "error"),
                "warning_count": sum(1 for issue in batch_validation.get("issues") or [] if issue.get("severity") == "warning"),
            })
    return metadata


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
        expected_size = request.get("requested_expected_size") or request.get("expected_size")
        expected_size_text = _expected_size_text(expected_size)
        expected_size_dims = _expected_size_dimensions(expected_size)
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
        if expected_size_text:
            inspection["requested_expected_size"] = expected_size_text
        width = inspection.get("width")
        height = inspection.get("height")
        if (
            expected_size_dims is not None
            and isinstance(width, int)
            and isinstance(height, int)
            and (width, height) != expected_size_dims
        ):
            row_issues.append({
                "severity": "error",
                "code": "returned_png_size_mismatch",
                "message": (
                    f"returned PNG size {width}x{height} != requested "
                    f"{expected_size_dims[0]}x{expected_size_dims[1]}"
                ),
            })
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
    payload["issue_code_counts"] = _issue_code_counts(payload)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "reference_intake.json"
    md_path = out_dir / "reference_intake.md"
    tsv_path = out_dir / "reference_intake.tsv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with tsv_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "id\tdrawing_id\trecommended_output_name\treturned_png\twidth\theight\t"
            "requested_expected_size\tlong_edge\tmode\thas_alpha\tcorner_white_ratio\t"
            "sha256\tsize_bytes\tidentity_advisory\tissue_codes\n"
        )
        for row in rows:
            inspection = row["inspection"]
            handle.write(
                f"{_tsv(row.get('id'))}\t"
                f"{_tsv(row.get('drawing_id'))}\t"
                f"{_tsv(row.get('recommended_output_name'))}\t"
                f"{_tsv(inspection.get('path'))}\t"
                f"{_tsv(inspection.get('width'))}\t"
                f"{_tsv(inspection.get('height'))}\t"
                f"{_tsv(inspection.get('requested_expected_size'))}\t"
                f"{_tsv(inspection.get('long_edge'))}\t"
                f"{_tsv(inspection.get('mode'))}\t"
                f"{_tsv(inspection.get('has_alpha'))}\t"
                f"{_tsv(inspection.get('corner_white_ratio'))}\t"
                f"{_tsv(inspection.get('sha256'))}\t"
                f"{_tsv(inspection.get('size_bytes'))}\t"
                f"{_tsv(_identity_advisory_text(inspection.get('identity_advisory') or {}))}\t"
                f"{_tsv(_issue_code_labels(row.get('issues')))}\n"
            )
    lines = [
        "# AutoCAD Reference Intake Preflight",
        "",
        f"- status: `{status}`",
        f"- request: `{request_json.resolve()}`",
        f"- reference_dir: `{reference_dir.resolve()}`",
        f"- reference_intake_tsv: `{tsv_path}`",
        f"- cases: `{len(rows)}`",
        f"- errors: `{error_count}`",
        f"- warnings: `{warning_count}`",
        f"- issue_code_counts: `{_format_counts(payload['issue_code_counts'])}`",
        "",
        "This is a capture-quality preflight only. It does not compare against VemCAD and does not claim AutoCAD equivalence.",
        "",
        (
            "| Case | Drawing | PNG | Returned provenance | Size | Expected size | "
            "Long edge | Corner white | Identity advisory | Issues |"
        ),
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
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
            f"| {_md_code_cell(row['id'])} | {_md_table_cell(row.get('drawing_id'))} | "
            f"{_md_code_cell(row['recommended_output_name'])} | "
            f"{_md_code_cell(_provenance_text(inspection))} | {_md_table_cell(size)} | "
            f"{_md_table_cell(inspection.get('requested_expected_size', '-'))} | "
            f"{_md_table_cell(inspection.get('long_edge', '-'))} | {_md_table_cell(inspection.get('corner_white_ratio', '-'))} | "
            f"{_md_table_cell(_identity_advisory_text(inspection.get('identity_advisory') or {}))} | "
            f"{_md_table_cell(issue_text)} |"
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
    request_boundary_expectations: list[tuple[str, Any]] | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    request_validation = _write_reference_request_validation_report(
        out_dir,
        request_json,
        candidate_cases=candidate_cases,
        case_ids=case_ids,
        request_boundary_expectations=request_boundary_expectations,
    )
    if request_validation["status"] == "blocked":
        raise ValueError(
            f"reference request package validation blocked; see {out_dir / 'reference_request_validation.md'}"
        )
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
    parser.add_argument("--validate-request", type=Path, default=None,
                        help="validate a reference_request.json before AutoCAD PNG fulfilment")
    parser.add_argument("--candidate-cases", type=Path, default=None,
                        help="original candidate_cases.json, required with --from-request/--validate-request")
    parser.add_argument("--reference-dir", type=Path, default=None,
                        help="directory containing returned AutoCAD PNGs, required with --from-request")
    parser.add_argument("--case-id", action="append", default=None,
                        help="with --from-request/--validate-request, process only this case id; may repeat")
    parser.add_argument("--require-request-boundary", action="append", default=[],
                        help="with --from-request/--validate-request, require request boundary key=value; may repeat")
    parser.add_argument("--fail-on-input-review", action="store_true",
                        help=(
                            "return exit code 2 when returned-reference intake is in review, "
                            "without changing the default soft-review behavior"
                        ))
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    _clear_batch_outputs(args.out_dir)

    try:
        modes = sum(1 for item in (args.cases, args.from_request, args.validate_request) if item is not None)
        if modes != 1:
            raise ValueError("choose exactly one of --cases, --from-request, or --validate-request")
        request_boundary_expectations = [
            _parse_boundary_expectation(item) for item in args.require_request_boundary
        ]
        if args.validate_request is not None:
            if args.candidate_cases is None:
                raise ValueError("--candidate-cases is required with --validate-request")
            validation = _write_reference_request_validation_report(
                args.out_dir,
                args.validate_request,
                candidate_cases=args.candidate_cases,
                case_ids=set(args.case_id or []) or None,
                request_boundary_expectations=request_boundary_expectations,
            )
            final_exit_code = _batch_final_exit_code(
                str(validation.get("status") or ""),
                fail_on_input_review=args.fail_on_input_review,
            )
            index_path = _write_batch_artifact_index(
                args.out_dir,
                validation=validation,
                run_metadata={
                    "fail_on_input_review": bool(args.fail_on_input_review),
                    "final_exit_code": final_exit_code,
                },
            )
            route_payload = _write_batch_route_report(index_path)
            print(f"AutoCAD reference request validation: {validation['status']} ({validation['case_count']} cases)")
            print(f"  final exit code: {final_exit_code}")
            print(f"  fail on input review: {bool(args.fail_on_input_review)}")
            print(f"  validation     : {args.out_dir / 'reference_request_validation.json'}")
            if index_path is not None:
                print(f"  artifact index : {index_path}")
            _print_route_summary(args.out_dir, route_payload)
            if validation["issues"]:
                for issue in validation["issues"]:
                    print(f"  {issue['severity']} {issue.get('case_id', '')} {issue['code']}: {issue['message']}")
            return final_exit_code
        if args.from_request is not None:
            if args.candidate_cases is None or args.reference_dir is None:
                raise ValueError("--candidate-cases and --reference-dir are required with --from-request")
            manifest_path, candidates_path, validation = build_files_from_request(
                args.from_request,
                candidate_cases=args.candidate_cases,
                reference_dir=args.reference_dir,
                out_dir=args.out_dir,
                case_ids=set(args.case_id or []) or None,
                request_boundary_expectations=request_boundary_expectations,
            )
        else:
            manifest_path, candidates_path, validation = build_files(args.cases, args.out_dir)
    except Exception as exc:
        index_path = _write_batch_artifact_index(
            args.out_dir,
            run_metadata={
                "fail_on_input_review": bool(args.fail_on_input_review),
                "final_exit_code": 2,
            },
        )
        route_payload = _write_batch_route_report(index_path)
        print(f"AutoCAD reference batch: blocked ({exc})", file=sys.stderr)
        print("  final exit code: 2", file=sys.stderr)
        print(f"  fail on input review: {bool(args.fail_on_input_review)}", file=sys.stderr)
        if index_path is not None:
            print(f"  artifact index : {index_path}", file=sys.stderr)
        _print_route_summary(args.out_dir, route_payload, stream=sys.stderr)
        return 2

    metadata = _batch_index_metadata(args.out_dir, batch_validation=validation)
    final_exit_code = _batch_final_exit_code(
        str(metadata.get("status") or validation.get("status") or ""),
        fail_on_input_review=args.fail_on_input_review,
    )
    index_path = _write_batch_artifact_index(
        args.out_dir,
        validation=validation,
        run_metadata={
            "fail_on_input_review": bool(args.fail_on_input_review),
            "final_exit_code": final_exit_code,
        },
    )
    route_payload = _write_batch_route_report(index_path)
    print(f"AutoCAD reference batch: {validation['status']} ({validation['case_count']} cases)")
    print(f"  final exit code: {final_exit_code}")
    print(f"  fail on input review: {bool(args.fail_on_input_review)}")
    print(f"  manifest       : {manifest_path}")
    print(f"  candidate cases: {candidates_path}")
    if index_path is not None:
        print(f"  artifact index : {index_path}")
    _print_route_summary(args.out_dir, route_payload)
    if validation["issues"]:
        for issue in validation["issues"]:
            print(f"  {issue['severity']} {issue['case_id']} {issue['code']}: {issue['message']}")
    return final_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
