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
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acad_reference_manifest as arm  # noqa: E402
import acad_artifact_route as artifact_route  # noqa: E402
import compare_vs_acad as cva  # noqa: E402
import text_provenance_diagnostics as tpd  # noqa: E402


SCHEMA = "vemcad.acad_manifest_compare/v1"
REFERENCE_REQUEST_BOUNDARY = {
    "renders_dxf": False,
    "compares_renders": False,
    "changes_x3_scoring": False,
    "changes_renderer": False,
    "requires_returned_autocad_png": True,
    "requires_viewspace_match": True,
    "autocad_equivalence_claim": False,
}


def _artifact_index_boundary(report: dict[str, Any] | None) -> dict[str, bool]:
    compared_count = int((report or {}).get("compared_count") or 0)
    return {
        "renders_dxf": False,
        "compares_renders": compared_count > 0,
        "changes_x3_scoring": False,
        "changes_renderer": False,
        "requires_viewspace_match": True,
        "autocad_equivalence_claim": False,
    }


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


def _issue_code_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        code = _str(issue.get("code") if isinstance(issue, dict) else "")
        if not code:
            continue
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _format_counts(counts: dict[str, Any]) -> str:
    if not counts:
        return ""
    parts: list[str] = []
    for key in sorted(counts):
        parts.append(f"{key}={counts[key]}")
    return ", ".join(parts)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _clear_compare_outputs(out_dir: Path) -> None:
    for name in (
        "summary.json",
        "summary.md",
        "summary.tsv",
        "artifact_index.json",
        "route_summary.json",
        "route_summary.md",
        "contact_sheet.png",
        "reference_request.json",
        "reference_request.md",
    ):
        path = out_dir / name
        if path.is_file():
            path.unlink()
    for name in ("overlays", "viewspace", "semantic", "text"):
        path = out_dir / name
        if path.is_dir():
            shutil.rmtree(path)


def _print_route_summary(out_dir: Path, route_payload: dict[str, Any]) -> None:
    action = route_payload.get("recommended_next_action") or {}
    print(f"  route summary  : {out_dir / 'route_summary.md'}")
    print(f"  recommended next action: {action.get('code', '')}")
    print(f"  recommended next action domain: {action.get('domain', '')}")
    if action.get("artifact"):
        print(f"  recommended next action artifact: {action.get('artifact', '')}")
    if route_payload.get("action_artifact_resolved"):
        print(f"  recommended next action artifact resolved: {route_payload['action_artifact_resolved']}")
        print(f"  recommended next action artifact exists: {bool(route_payload.get('action_artifact_exists'))}")


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "id\tdrawing_id\tviewspace_status\tx3_band\tink_iou\tcolor_dist\t"
            "aspect_delta\tcompare_exit_code\ttext_flags\ttext_notes\t"
            "triage_rank\ttriage_bucket\trecommended_action_domain\t"
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
                f"{row.get('compare_exit_code', '')}\t{text_flags}\t{text_notes}\t"
                f"{row.get('triage_rank', '')}\t{row.get('triage_bucket', '')}\t"
                f"{row.get('recommended_action_domain', '')}\t{row.get('acad_png', '')}\t"
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
    report: dict[str, Any] | None = None,
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
    payload: dict[str, Any] = {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "boundary": _artifact_index_boundary(report),
        "count": len(artifacts),
        "artifacts": artifacts,
    }
    if report is not None:
        payload.update({
            "status": report.get("status", ""),
            "case_count": report.get("case_count"),
            "compared_count": report.get("compared_count"),
            "issue_count": len(report.get("issues") or []),
            "issue_code_counts": report.get("issue_code_counts") or {},
            "triage_bucket_counts": _count_values(rows, "triage_bucket"),
            "recommended_action_domain_counts": _count_values(rows, "recommended_action_domain"),
            "viewspace_status_counts": _count_values(rows, "viewspace_status"),
            "x3_band_counts": _count_x3_bands(rows),
        })
    return payload


def _count_values(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = _str(row.get(key))
        if value:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _count_x3_bands(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = _str((row.get("x3_summary") or {}).get("band"))
        if value:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _md(value: Any) -> str:
    text = _str(value)
    if not text:
        return ""
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("|", "\\|")


def _md_table_cell(value: Any) -> str:
    text = _md(value)
    if not text:
        return "-"
    return text.replace("`", "\\`")


def _md_code_cell(value: Any) -> str:
    text = _md(value) or "-"
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
        f"- issue_code_counts: `{_md(_format_counts(report.get('issue_code_counts') or {}))}`",
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
                f"| {_md_table_cell(issue.get('case_id'))} | {_md_table_cell(issue.get('severity'))} | "
                f"{_md_code_cell(issue.get('code'))} | {_md_table_cell(issue.get('message'))} |"
            )
        lines.append("")
    rows = report.get("rows") or []
    if rows:
        lines.extend([
            "## Cases",
            "",
            (
                "| Case | Drawing | View-space | X3 band | Ink IoU | Color dist | "
                "Text flags | Text notes | Action domain | Recommended action |"
            ),
            "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
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
                f"| {_md_code_cell(row.get('id'))} | {_md_table_cell(row.get('drawing_id'))} | "
                f"{_md_code_cell(row.get('viewspace_status'))} | {_md_code_cell(summary.get('band'))} | "
                f"{_md_table_cell(summary.get('ink_iou'))} | {_md_table_cell(summary.get('color_dist'))} | "
                f"{_md_table_cell(text_flags)} | {_md_table_cell(text_notes)} | "
                f"{_md_code_cell(row.get('recommended_action_domain'))} | {_md_table_cell(row.get('recommended_action'))} |"
            )
        lines.extend([
            "",
            "## Triage Priority",
            "",
            (
                "| Rank | Case | Bucket | View-space | X3 band | Ink IoU | "
                "Action domain | Recommended next action |"
            ),
            "| ---: | --- | --- | --- | --- | ---: | --- | --- |",
        ])
        for rank, row in enumerate(_triage_rows(rows), start=1):
            summary = row.get("x3_summary") or {}
            bucket = _str(row.get("triage_bucket")) or _triage_bucket(row)
            display_rank = row.get("triage_rank") or rank
            lines.append(
                f"| {_md_table_cell(display_rank)} | {_md_code_cell(row.get('id'))} | {_md_code_cell(bucket)} | "
                f"{_md_code_cell(row.get('viewspace_status'))} | {_md_code_cell(summary.get('band'))} | "
                f"{_md_table_cell(summary.get('ink_iou'))} | "
                f"{_md_code_cell(row.get('recommended_action_domain'))} | {_md_table_cell(row.get('recommended_action'))} |"
            )
        lines.extend(["", "## Artifact Paths", ""])
        for row in rows:
            lines.append(f"### {_md_code_cell(row.get('id'))}")
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
                    lines.append(f"- {label}: {_md_code_cell(value)}")
            text_summary = (row.get("text_provenance") or {}).get("summary")
            if text_summary:
                lines.append(f"- text provenance summary: {_md_code_cell(text_summary)}")
            lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _recapture_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in _triage_rows(rows) if _triage_bucket(row) == "recapture-required"]


def _png_size(path: str) -> dict[str, int] | None:
    if not path:
        return None
    try:
        with Image.open(path) as image:
            width, height = image.size
    except Exception:
        return None
    return {"width": width, "height": height}


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


def _file_provenance(path: str) -> dict[str, Any] | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "size_bytes": file_path.stat().st_size,
    }


def _write_reference_request(
    out_dir: Path,
    rows: list[dict[str, Any]],
    *,
    candidate_cases: str = "",
) -> list[dict[str, str]]:
    recaptures = _recapture_rows(rows)
    if not recaptures:
        return []
    json_path = out_dir / "reference_request.json"
    md_path = out_dir / "reference_request.md"
    cases: list[dict[str, Any]] = []
    for row in recaptures:
        case_id = _str(row.get("id"))
        case = {
            "id": case_id,
            "drawing_id": row.get("drawing_id", ""),
            "source_dxf": row.get("source_dxf", ""),
            "current_acad_png": row.get("acad_png", ""),
            "current_viewspace_status": row.get("viewspace_status", ""),
            "current_x3_band": (row.get("x3_summary") or {}).get("band", ""),
            "current_ink_iou": (row.get("x3_summary") or {}).get("ink_iou", ""),
            "triage_rank": row.get("triage_rank", ""),
            "triage_bucket": row.get("triage_bucket", ""),
            "requested_capture_method": "plot-export",
            "requested_view_contract": "model-extents",
            "recommended_output_name": f"{_safe_case_name(case_id)}_autocad_model_extents.png",
            "instructions": (
                "Export from AutoCAD model space at drawing extents, white background, "
                "monochrome off, no toolbar/chrome, long edge >= 1600px."
            ),
        }
        expected_size = _png_size(_str(row.get("acad_png")))
        if expected_size is not None:
            case["requested_expected_size"] = expected_size
        source_provenance = _file_provenance(_str(row.get("source_dxf")))
        if source_provenance is not None:
            case["source_dxf_sha256"] = source_provenance["sha256"]
            case["source_dxf_size_bytes"] = source_provenance["size_bytes"]
        candidate_provenance = _file_provenance(_str(row.get("ours")))
        if candidate_provenance is not None:
            case["candidate_png_sha256"] = candidate_provenance["sha256"]
            case["candidate_png_size_bytes"] = candidate_provenance["size_bytes"]
        cases.append(case)
    payload = {
        "schema": "vemcad.acad_reference_request/v1",
        "reason": "recapture-required",
        "case_count": len(cases),
        "boundary": dict(REFERENCE_REQUEST_BOUNDARY),
        "cases": cases,
    }
    _write_json(json_path, payload)
    lines = [
        "# AutoCAD Reference Recapture Request",
        "",
        "These cases failed the view-space contract. They need fresh AutoCAD model-extents exports before X3 can be interpreted as render fidelity.",
        "",
        (
            "| Rank | Case | Drawing | Current view | Current X3 | Expected size | "
            "Requested PNG | Source DXF | Source SHA256 | Candidate SHA256 |"
        ),
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        lines.append(
            f"| {_md_table_cell(case['triage_rank'])} | {_md_code_cell(case['id'])} | "
            f"{_md_table_cell(case['drawing_id'])} | "
            f"{_md_code_cell(case.get('current_viewspace_status'))} | "
            f"{_md_code_cell(case.get('current_x3_band'))} | "
            f"{_md_code_cell(_expected_size_text(case.get('requested_expected_size')))} | "
            f"{_md_code_cell(case['recommended_output_name'])} | {_md_code_cell(case['source_dxf'])} | "
            f"{_md_code_cell(case.get('source_dxf_sha256'))} | {_md_code_cell(case.get('candidate_png_sha256'))} |"
        )
    lines.extend([
        "",
        "## Capture Contract",
        "",
        "- AutoCAD model space, drawing EXTENTS / fit-to-drawing.",
        "- White background.",
        "- Monochrome off; preserve layer colors.",
        "- No toolbar, viewport chrome, screenshot crop, or post-scaled image.",
        "- Long edge >= 1600 px.",
        "- If a custom plot window is used, record the AutoCAD world rectangle and use `explicit-window` instead of this request.",
    ])
    candidate_arg = candidate_cases or "<candidate_cases.json>"
    lines.extend([
        "",
        "## Before Capture Or Fulfilment",
        "",
        "Validate the request package before spending time in AutoCAD:",
        "",
        "```bash",
        "python3 tools/render_regression/acad_reference_batch.py \\",
        f"  --validate-request {json_path} \\",
        f"  --candidate-cases {candidate_arg} \\",
        "  --require-request-boundary autocad_equivalence_claim=false \\",
        "  --require-request-boundary requires_returned_autocad_png=true \\",
        "  --require-request-boundary requires_viewspace_match=true \\",
        "  --out-dir <request-validation-dir>",
        "```",
        "",
        "## After The PNGs Are Returned",
        "",
        "Place the returned AutoCAD PNGs in one directory using the requested filenames, then run:",
        "",
        "```bash",
        "python3 tools/render_regression/acad_reference_request_run.py \\",
        f"  --from-request {json_path} \\",
        f"  --candidate-cases {candidate_arg} \\",
        "  --reference-dir <returned-png-dir> \\",
        "  --require-request-boundary autocad_equivalence_claim=false \\",
        "  --require-request-boundary requires_returned_autocad_png=true \\",
        "  --require-request-boundary requires_viewspace_match=true \\",
        "  --fail-on-input-review \\",
        "  --out-dir <next-run-dir>",
        "```",
        "",
        "Then inspect the machine-readable route summary before interpreting pixels:",
        "",
        "```bash",
        "python3 tools/render_regression/acad_artifact_route.py <next-run-dir> \\",
        "  --recursive \\",
        "  --text \\",
        "  --require-source-boundary autocad_equivalence_claim=false \\",
        "  --require-request-boundary autocad_equivalence_claim=false \\",
        "  --require-request-boundary requires_returned_autocad_png=true \\",
        "  --require-request-boundary requires_viewspace_match=true \\",
        "  --require-kind batch \\",
        "  --require-kind compare \\",
        "  --require-kind request_run \\",
        "  --require-route-count 3 \\",
        "  --require-action-artifact-exists",
        "```",
        "",
        "For a partial return, repeat `--case-id <ID>` to process only the cases that have PNGs.",
        "The wrapper preserves the X3 exit code: `viewspace_mismatch` still exits `2` and is not an AutoCAD-equivalence result.",
    ])
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return [
        {"id": "", "kind": "reference_request_json", "path": str(json_path)},
        {"id": "", "kind": "reference_request_markdown", "path": str(md_path)},
    ]


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


def _recommended_action_domain(row: dict[str, Any]) -> str:
    bucket = _triage_bucket(row)
    if bucket == "renderer-candidate":
        return artifact_route.ACTION_DOMAINS["inspect-renderer-candidate"]
    if bucket == "recapture-required":
        return artifact_route.ACTION_DOMAINS["recapture-autocad-or-provide-window"]
    if bucket == "matched-pass":
        return artifact_route.ACTION_DOMAINS["review-x3-pass"]
    return artifact_route.ACTION_DOMAINS["inspect-returned-reference-warnings"]


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


def _annotate_triage(rows: list[dict[str, Any]]) -> None:
    for rank, row in enumerate(_triage_rows(rows), start=1):
        row["triage_rank"] = rank
        row["triage_bucket"] = _triage_bucket(row)
        row["recommended_action_domain"] = _recommended_action_domain(row)


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

    if rows:
        _annotate_triage(rows)

    report = {
        "schema": SCHEMA,
        "manifest": str(manifest_path),
        "candidate_cases": str(candidate_cases) if candidate_cases is not None else "",
        "status": status,
        "case_count": len(validation["cases"]),
        "compared_count": len(rows) if not dry_run else 0,
        "dry_run": dry_run,
        "issues": issues,
        "issue_code_counts": _issue_code_counts(issues),
        "validation": validation,
        "rows": rows,
        "recommended_action_domain_counts": _count_values(rows, "recommended_action_domain"),
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

    _clear_compare_outputs(args.out_dir)
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
    route_summary_json = args.out_dir / "route_summary.json"
    route_summary_md = args.out_dir / "route_summary.md"
    _write_json(summary_json, report)
    contact_sheet = ""
    if report["rows"] and not args.dry_run:
        _write_tsv(summary_tsv, report["rows"])
        contact_sheet = _write_contact_sheet(args.out_dir / "contact_sheet.png", report["rows"])
    _write_markdown_summary(summary_md, report, contact_sheet=contact_sheet)
    reference_request_artifacts = _write_reference_request(
        args.out_dir,
        report["rows"],
        candidate_cases=report.get("candidate_cases", ""),
    )
    run_artifacts = [
        {"id": "", "kind": "summary_json", "path": str(summary_json)},
        {"id": "", "kind": "summary_markdown", "path": str(summary_md)},
        {"id": "", "kind": "route_summary_json", "path": str(route_summary_json)},
        {"id": "", "kind": "route_summary_markdown", "path": str(route_summary_md)},
    ]
    if summary_tsv.is_file():
        run_artifacts.append({"id": "", "kind": "summary_tsv", "path": str(summary_tsv)})
    if contact_sheet:
        run_artifacts.append({"id": "", "kind": "contact_sheet", "path": contact_sheet})
    run_artifacts.extend(reference_request_artifacts)
    _write_json(artifact_index, _artifact_index(
        report["rows"],
        report=report,
        run_artifacts=run_artifacts,
    ))
    route_payload = artifact_route.route_artifact_index(artifact_index)
    artifact_route.write_route_report_files(
        route_payload,
        out_json=route_summary_json,
        out_md=route_summary_md,
    )

    print(
        f"AutoCAD manifest compare: {report['status']} "
        f"({report['compared_count']}/{report['case_count']} compared, {len(report['issues'])} issues)"
    )
    _print_route_summary(args.out_dir, route_payload)
    for issue in report["issues"]:
        print(f"  {issue['severity']} {issue['case_id']} {issue['code']}: {issue['message']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
