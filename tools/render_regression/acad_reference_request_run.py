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


def _existing(path: Path) -> str:
    return str(path) if path.is_file() else ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _compare_status(compare_summary: Path) -> str:
    if not compare_summary.is_file():
        return ""
    try:
        payload = json.loads(compare_summary.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(payload.get("status") or "")


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# AutoCAD Reference Request Run",
        "",
        f"- status: `{summary['status']}`",
        f"- batch_exit_code: `{summary['batch_exit_code']}`",
        f"- compare_exit_code: `{summary['compare_exit_code']}`",
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
        ("input artifact index", "input_artifact_index"),
        ("reference intake", "reference_intake_markdown"),
        ("missing references", "missing_references_markdown"),
        ("compare summary", "compare_summary_markdown"),
        ("compare artifact index", "compare_artifact_index"),
    ):
        value = summary.get(key) or ""
        if value:
            lines.append(f"- {label}: `{value}`")
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
        "input_artifact_index": _existing(input_dir / "artifact_index.json"),
        "reference_intake_json": _existing(input_dir / "reference_intake.json"),
        "reference_intake_markdown": _existing(input_dir / "reference_intake.md"),
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
    _write_json(out_dir / "run_summary.json", payload)
    _write_markdown(out_dir / "run_summary.md", payload)
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
    print(f"  run summary: {args.out_dir / 'run_summary.md'}")
    return compare_rc


if __name__ == "__main__":
    raise SystemExit(main())
