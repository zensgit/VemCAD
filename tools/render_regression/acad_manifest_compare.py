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
from types import SimpleNamespace
from typing import Any

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acad_reference_manifest as arm  # noqa: E402
import compare_vs_acad as cva  # noqa: E402
import text_provenance_diagnostics as tpd  # noqa: E402


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
            "aspect_delta\tcompare_exit_code\ttext_flags\ttext_notes\t"
            "acad_png\tours\toverlay\tviewspace_report\n"
        )
        for row in rows:
            summary = row.get("x3_summary") or {}
            text_counts = (row.get("text_provenance") or {}).get("counts") or {}
            text_flags = ",".join(
                f"{key}:{value}" for key, value in sorted((text_counts.get("flag_counts") or {}).items())
            )
            text_notes = ",".join(
                f"{key}:{value}" for key, value in sorted((text_counts.get("note_counts") or {}).items())
            )
            handle.write(
                f"{row['id']}\t{row.get('drawing_id', '')}\t{row.get('viewspace_status', '')}\t"
                f"{summary.get('band', '')}\t{summary.get('ink_iou', '')}\t"
                f"{summary.get('color_dist', '')}\t{summary.get('aspect_delta', '')}\t"
                f"{row.get('compare_exit_code', '')}\t{text_flags}\t{text_notes}\t{row.get('acad_png', '')}\t"
                f"{row.get('ours', '')}\t{row.get('overlay', '')}\t"
                f"{row.get('viewspace_report', '')}\n"
            )


def _thumb(path: str, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    thumb = ImageOps.contain(image, size)
    out = Image.new("RGB", size, "white")
    out.paste(thumb, ((size[0] - thumb.width) // 2, (size[1] - thumb.height) // 2))
    return out


def _placeholder(size: tuple[int, int], text: str) -> Image.Image:
    out = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(out)
    draw.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=(190, 190, 190))
    y = 12
    for line in text.splitlines()[:8]:
        draw.text((12, y), line[:64], fill=(70, 70, 70))
        y += 18
    return out


def _contact_cell(path: str, size: tuple[int, int], *, missing: str) -> Image.Image:
    if path and Path(path).is_file():
        return _thumb(path, size)
    return _placeholder(size, missing)


def _write_contact_sheet(path: Path, rows: list[dict[str, Any]]) -> str:
    """Write a quick-review AutoCAD / VemCAD / overlay contact sheet.

    The JSON/TSV files remain authoritative. This PNG is deliberately only a
    review affordance for unattended runs: after a batch finishes, the operator
    can scan one artifact before drilling into per-case overlays.
    """
    if not rows:
        return ""
    tile_w, tile_h = 360, 255
    label_h = 54
    pad = 12
    cols = 3
    row_h = label_h + tile_h + pad
    width = pad * (cols + 1) + tile_w * cols
    height = pad + row_h * len(rows)
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    status_colors = {
        "match": (45, 140, 70),
        "mismatch": (195, 120, 0),
        "unavailable": (160, 70, 70),
    }
    y = pad
    for row in rows:
        status = str(row.get("viewspace_status") or "")
        color = status_colors.get(status, (90, 90, 90))
        summary = row.get("x3_summary") or {}
        title = (
            f"{row.get('id', '')}  view={status or '?'}  "
            f"IoU={summary.get('ink_iou', '')}  band={summary.get('band', '')}"
        )
        draw.text((pad, y), title, fill=color)
        reason = str(row.get("viewspace_reason") or row.get("recommended_action") or "")
        if reason:
            draw.text((pad, y + 18), reason[:150], fill=(55, 55, 55))
        for col, (label, key) in enumerate((
            ("AutoCAD", "acad_png"),
            ("VemCAD", "ours"),
            ("overlay", "overlay"),
        )):
            x = pad + col * (tile_w + pad)
            image = _contact_cell(
                str(row.get(key) or ""),
                (tile_w, tile_h),
                missing=f"no {label} image",
            )
            canvas.paste(image, (x, y + label_h))
            draw.rectangle(
                [x, y + label_h, x + tile_w - 1, y + label_h + tile_h - 1],
                outline=color,
                width=3,
            )
            draw.text((x + 6, y + label_h + 6), label, fill=color)
        y += row_h
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return str(path)


def _text_provenance_summary(render_report: str, out_path: Path) -> dict[str, Any]:
    if not render_report:
        return {"status": "unavailable", "reason": "no_render_report"}
    try:
        report = json.loads(Path(render_report).read_text(encoding="utf-8"))
        payload = tpd.analyze_report(
            report,
            SimpleNamespace(
                title_block=False,
                block=None,
                source_type=None,
                text_kind=None,
                semantic_class=None,
            ),
        )
        _write_json(out_path, payload)
        return {
            "status": "available",
            "summary": str(out_path),
            "schema": payload["schema"],
            "text_placement_schema": payload["text_placement_schema"],
            "text_placement_schema_version": payload["text_placement_schema_version"],
            "counts": payload["counts"],
            "selected_screen_bbox": payload["selected_screen_bbox"],
        }
    except Exception as exc:  # Diagnostic-only: do not turn X3 gate into text-provenance gate.
        return {
            "status": "error",
            "render_report": render_report,
            "error": str(exc),
        }


def _artifact_index(
    rows: list[dict[str, Any]],
    *,
    run_artifacts: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    artifacts: list[dict[str, str]] = []
    artifacts.extend(run_artifacts or [])
    for row in rows:
        for key, kind in (
            ("acad_png", "autocad_reference"),
            ("ours", "vemcad_candidate"),
            ("overlay", "x3_overlay"),
            ("viewspace_report", "viewspace_report"),
            ("render_report", "render_report"),
            ("semantic_mask", "semantic_mask"),
            ("semantic_class_report", "semantic_class_report"),
        ):
            path = row.get(key)
            if path:
                artifacts.append({"id": row["id"], "kind": kind, "path": str(path)})
        text_summary = (row.get("text_provenance") or {}).get("summary")
        if text_summary:
            artifacts.append({"id": row["id"], "kind": "text_provenance_summary", "path": str(text_summary)})
    return {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "count": len(artifacts),
        "artifacts": artifacts,
    }


def _md(value: Any) -> str:
    text = _str(value)
    if not text:
        return ""
    return text.replace("|", "\\|").replace("\n", " ")


def _write_markdown_summary(path: Path, report: dict[str, Any], *, contact_sheet: str = "") -> None:
    """Write a human-readable review summary beside the machine JSON/TSV.

    The JSON remains authoritative; this report is for unattended batch review
    and for pasting into development/verification ledgers without losing the
    view-space boundary.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    boundary = report.get("boundary") or {}
    lines = [
        "# AutoCAD Manifest Compare Summary",
        "",
        "## Result",
        "",
        f"- status: `{_md(report.get('status'))}`",
        f"- cases: `{report.get('compared_count', 0)}/{report.get('case_count', 0)}` compared",
        f"- issues: `{len(report.get('issues') or [])}`",
        f"- dry_run: `{bool(report.get('dry_run'))}`",
        "",
        "## Boundary",
        "",
        f"- renders_dxf: `{bool(boundary.get('renders_dxf'))}`",
        f"- requires_viewspace_match: `{bool(boundary.get('requires_viewspace_match'))}`",
        f"- autocad_equivalence_claim: `{bool(boundary.get('autocad_equivalence_claim'))}`",
        "",
        (
            "**Important:** `viewspace_mismatch` means the AutoCAD reference and "
            "VemCAD candidate are not in the same view-space. It is not an "
            "AutoCAD-equivalence result and must not trigger renderer tuning by itself."
        ),
        "",
    ]
    if contact_sheet:
        lines.extend([
            "## Quick Review Artifact",
            "",
            f"- contact_sheet: `{_md(contact_sheet)}`",
            "",
        ])
    issues = report.get("issues") or []
    if issues:
        lines.extend([
            "## Issues",
            "",
            "| Case | Severity | Code | Message |",
            "| --- | --- | --- | --- |",
        ])
        for issue in issues:
            lines.append(
                f"| {_md(issue.get('case_id'))} | {_md(issue.get('severity'))} | "
                f"`{_md(issue.get('code'))}` | {_md(issue.get('message'))} |"
            )
        lines.append("")
    rows = report.get("rows") or []
    if rows:
        lines.extend([
            "## Cases",
            "",
            (
                "| Case | Drawing | View-space | X3 band | Ink IoU | Color dist | "
                "Text flags | Text notes | Recommended action |"
            ),
            "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
        ])
        for row in rows:
            summary = row.get("x3_summary") or {}
            text_counts = (row.get("text_provenance") or {}).get("counts") or {}
            flag_counts = text_counts.get("flag_counts") or {}
            note_counts = text_counts.get("note_counts") or {}
            text_flags = ", ".join(
                f"{key}:{value}" for key, value in sorted(flag_counts.items())
            ) or "-"
            text_notes = ", ".join(
                f"{key}:{value}" for key, value in sorted(note_counts.items())
            ) or "-"
            lines.append(
                f"| `{_md(row.get('id'))}` | {_md(row.get('drawing_id'))} | "
                f"`{_md(row.get('viewspace_status'))}` | `{_md(summary.get('band'))}` | "
                f"{_md(summary.get('ink_iou'))} | {_md(summary.get('color_dist'))} | "
                f"{_md(text_flags)} | {_md(text_notes)} | {_md(row.get('recommended_action'))} |"
            )
        lines.extend([
            "",
            "## Triage Priority",
            "",
            (
                "| Rank | Case | Bucket | View-space | X3 band | Ink IoU | "
                "Recommended next action |"
            ),
            "| ---: | --- | --- | --- | --- | ---: | --- |",
        ])
        for rank, row in enumerate(_triage_rows(rows), start=1):
            summary = row.get("x3_summary") or {}
            bucket = _triage_bucket(row)
            lines.append(
                f"| {rank} | `{_md(row.get('id'))}` | `{bucket}` | "
                f"`{_md(row.get('viewspace_status'))}` | `{_md(summary.get('band'))}` | "
                f"{_md(summary.get('ink_iou'))} | {_md(row.get('recommended_action'))} |"
            )
        lines.extend(["", "## Artifact Paths", ""])
        for row in rows:
            lines.append(f"### `{_md(row.get('id'))}`")
            for label, key in (
                ("AutoCAD reference", "acad_png"),
                ("VemCAD candidate", "ours"),
                ("overlay", "overlay"),
                ("view-space report", "viewspace_report"),
                ("render report", "render_report"),
                ("semantic mask", "semantic_mask"),
                ("semantic class report", "semantic_class_report"),
            ):
                value = _str(row.get(key))
                if value:
                    lines.append(f"- {label}: `{_md(value)}`")
            text_summary = (row.get("text_provenance") or {}).get("summary")
            if text_summary:
                lines.append(f"- text provenance summary: `{_md(text_summary)}`")
            lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _triage_bucket(row: dict[str, Any]) -> str:
    status = _str(row.get("viewspace_status"))
    band = _str((row.get("x3_summary") or {}).get("band"))
    if status == "match" and band != "pass":
        return "renderer-candidate"
    if status == "mismatch":
        return "recapture-required"
    if status == "match":
        return "matched-pass"
    return "input-review"


def _triage_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket_order = {
        "renderer-candidate": 0,
        "recapture-required": 1,
        "input-review": 2,
        "matched-pass": 3,
    }

    def key(row: dict[str, Any]) -> tuple[int, float, str]:
        summary = row.get("x3_summary") or {}
        try:
            ink_iou = float(summary.get("ink_iou"))
        except (TypeError, ValueError):
            ink_iou = 1.0
        return (bucket_order.get(_triage_bucket(row), 99), ink_iou, _str(row.get("id")))

    return sorted(rows, key=key)


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
    text_summary_path = out_dir / "text" / f"{safe}_text_provenance.json"
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        rc = cva.main(argv)
    view_payload = json.loads(viewspace.read_text(encoding="utf-8"))
    render_report = candidate.get("render_report", "")
    return {
        "id": case_id,
        "drawing_id": case["drawing_id"],
        "source_dxf": case["source_dxf"],
        "acad_png": case["acad_png"],
        "ours": candidate["ours"],
        "render_report": render_report,
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
        "text_provenance": _text_provenance_summary(render_report, text_summary_path),
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
    summary_json = args.out_dir / "summary.json"
    summary_md = args.out_dir / "summary.md"
    summary_tsv = args.out_dir / "summary.tsv"
    artifact_index = args.out_dir / "artifact_index.json"
    _write_json(summary_json, report)
    contact_sheet = ""
    if report["rows"] and not args.dry_run:
        _write_tsv(summary_tsv, report["rows"])
        contact_sheet = _write_contact_sheet(args.out_dir / "contact_sheet.png", report["rows"])
    _write_markdown_summary(summary_md, report, contact_sheet=contact_sheet)
    run_artifacts = [
        {"id": "", "kind": "summary_json", "path": str(summary_json)},
        {"id": "", "kind": "summary_markdown", "path": str(summary_md)},
    ]
    if summary_tsv.is_file():
        run_artifacts.append({"id": "", "kind": "summary_tsv", "path": str(summary_tsv)})
    if contact_sheet:
        run_artifacts.append({"id": "", "kind": "contact_sheet", "path": contact_sheet})
    _write_json(artifact_index, _artifact_index(
        report["rows"],
        run_artifacts=run_artifacts,
    ))

    print(
        f"AutoCAD manifest compare: {report['status']} "
        f"({report['compared_count']}/{report['case_count']} compared, {len(report['issues'])} issues)"
    )
    for issue in report["issues"]:
        print(f"  {issue['severity']} {issue['case_id']} {issue['code']}: {issue['message']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
