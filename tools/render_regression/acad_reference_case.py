#!/usr/bin/env python3
"""Create manifest/candidate JSON files for a matched AutoCAD comparison case."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acad_reference_manifest as arm  # noqa: E402


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _resolve(path: Path) -> str:
    return str(path.expanduser().resolve())


def _optional_path(path: Path | None) -> str:
    return _resolve(path) if path is not None else ""


def _candidate_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": args.case_id,
        "ours": _resolve(args.ours),
    }
    optional_paths = {
        "render_report": args.render_report,
        "semantic_mask": args.semantic_mask,
        "semantic_report": args.semantic_report,
    }
    for key, value in optional_paths.items():
        if value is not None:
            payload[key] = _resolve(value)
    if args.render_image:
        payload["render_image"] = args.render_image
    if args.render_image_digest:
        payload["render_image_digest"] = args.render_image_digest
    if args.diagnostic:
        diagnostics: dict[str, str] = {}
        for item in args.diagnostic:
            if "=" not in item:
                raise ValueError("--diagnostic entries must be key=value")
            key, value = item.split("=", 1)
            diagnostics[key] = value
        payload["diagnostics"] = diagnostics
    return payload


def build_files(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    width, height = _image_size(args.acad_png)
    manifest = {
        "schema": arm.SCHEMA,
        "cases": [
            {
                "id": args.case_id,
                "drawing_id": args.drawing_id,
                "source_dxf": _resolve(args.source_dxf),
                "acad_png": _resolve(args.acad_png),
                "capture_method": args.capture_method,
                "view_contract": args.view_contract,
                "expected_size": {
                    "width": width,
                    "height": height,
                },
            }
        ],
    }
    candidates = [_candidate_payload(args)]
    manifest_path = args.out_dir / "acad_manifest.json"
    candidates_path = args.out_dir / "candidate_cases.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    candidates_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = arm.validate_manifest(manifest_path)
    return manifest_path, candidates_path, validation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acad_reference_case",
        description="Create validated AutoCAD manifest + candidate case files.")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--drawing-id", required=True)
    parser.add_argument("--source-dxf", type=Path, required=True)
    parser.add_argument("--acad-png", type=Path, required=True)
    parser.add_argument("--ours", type=Path, required=True, help="VemCAD candidate PNG")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--capture-method", default="plot-export",
                        choices=sorted(arm.GATE_CAPTURE_METHODS))
    parser.add_argument("--view-contract", default="model-extents",
                        choices=sorted(arm.MATCHED_VIEW_CONTRACTS))
    parser.add_argument("--render-report", type=Path, default=None)
    parser.add_argument("--semantic-mask", type=Path, default=None)
    parser.add_argument("--semantic-report", type=Path, default=None)
    parser.add_argument("--render-image", default="")
    parser.add_argument("--render-image-digest", default="")
    parser.add_argument("--diagnostic", action="append", default=None,
                        help="extra candidate diagnostic key=value; may repeat")
    args = parser.parse_args(argv)

    try:
        manifest_path, candidates_path, validation = build_files(args)
    except Exception as exc:
        print(f"AutoCAD reference case: blocked ({exc})", file=sys.stderr)
        return 2

    print(f"AutoCAD reference case: {validation['status']}")
    print(f"  manifest       : {manifest_path}")
    print(f"  candidate cases: {candidates_path}")
    if validation["issues"]:
        for issue in validation["issues"]:
            print(f"  {issue['severity']} {issue['case_id']} {issue['code']}: {issue['message']}")
    return 0 if validation["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
