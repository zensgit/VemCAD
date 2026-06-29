#!/usr/bin/env python3
"""Create manifest/candidate JSON files for a batch of AutoCAD reference cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acad_reference_manifest as arm  # noqa: E402


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


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


def _fulfilled_cases(
    request_json: Path,
    *,
    candidate_cases: Path,
    reference_dir: Path,
) -> list[dict[str, Any]]:
    request_cases = _load_request_cases(request_json)
    candidates = _load_candidate_map(candidate_cases)
    fulfilled: list[dict[str, Any]] = []
    for index, request in enumerate(request_cases, start=1):
        case_id = _required(request, "id", index)
        candidate = candidates.get(case_id)
        if candidate is None:
            raise ValueError(f"request case {case_id}: missing candidate case")
        output_name = _required(request, "recommended_output_name", index)
        item: dict[str, Any] = {
            "id": case_id,
            "drawing_id": _required(request, "drawing_id", index),
            "source_dxf": _resolve(request_json.parent, _required(request, "source_dxf", index)),
            "acad_png": str((reference_dir / output_name).resolve()),
            "ours": _resolve(candidate_cases.parent, _required(candidate, "ours", index)),
            "capture_method": _str(request.get("requested_capture_method") or "plot-export"),
            "view_contract": _str(request.get("requested_view_contract") or "model-extents"),
        }
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
) -> int:
    request_cases = _load_request_cases(request_json)
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


def build_files_from_request(
    request_json: Path,
    *,
    candidate_cases: Path,
    reference_dir: Path,
    out_dir: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    missing_count = _write_missing_references_report(
        out_dir,
        request_json,
        reference_dir=reference_dir,
    )
    if missing_count:
        raise ValueError(f"missing {missing_count} returned AutoCAD PNG(s); see {out_dir / 'missing_references.md'}")
    return _build_files(
        _fulfilled_cases(request_json, candidate_cases=candidate_cases, reference_dir=reference_dir),
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
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        if args.from_request is not None:
            if args.candidate_cases is None or args.reference_dir is None:
                raise ValueError("--candidate-cases and --reference-dir are required with --from-request")
            manifest_path, candidates_path, validation = build_files_from_request(
                args.from_request,
                candidate_cases=args.candidate_cases,
                reference_dir=args.reference_dir,
                out_dir=args.out_dir,
            )
        else:
            if args.cases is None:
                raise ValueError("--cases is required unless --from-request is set")
            manifest_path, candidates_path, validation = build_files(args.cases, args.out_dir)
    except Exception as exc:
        print(f"AutoCAD reference batch: blocked ({exc})", file=sys.stderr)
        return 2

    print(f"AutoCAD reference batch: {validation['status']} ({validation['case_count']} cases)")
    print(f"  manifest       : {manifest_path}")
    print(f"  candidate cases: {candidates_path}")
    if validation["issues"]:
        for issue in validation["issues"]:
            print(f"  {issue['severity']} {issue['case_id']} {issue['code']}: {issue['message']}")
    return 0 if validation["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
