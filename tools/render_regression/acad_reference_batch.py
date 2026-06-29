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


def build_files(cases_json: Path, out_dir: Path) -> tuple[Path, Path, dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = cases_json.parent
    cases = _load_cases(cases_json)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acad_reference_batch",
        description="Create validated AutoCAD manifest + candidate case files from a cases JSON list.")
    parser.add_argument("--cases", type=Path, required=True,
                        help="JSON list of AutoCAD reference cases")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
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
