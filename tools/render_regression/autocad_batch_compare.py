#!/usr/bin/env python3
"""Batch X3 comparisons for AutoCAD PNG references vs VemCAD PNG renders.

This tool does not render. It makes a repeatable report from already-produced
PNGs, so customer/training drawings can stay outside git while the comparison
method remains versioned.

Cases JSON shape:

[
  {
    "id": "G01",
    "acad": "/path/to/autocad.png",
    "ours": "/path/to/vemcad.png",
    "semantic_mask": "/path/to/render_cli-class-mask.png",
    "semantic_report": "/path/to/render_cli-report.json"
  }
]

`semantic_mask` and `semantic_report` are optional. When both are present, the
tool also writes candidate-side semantic class diagnostics. AutoCAD reference
semantics are unknown, so these rows are diagnostic evidence, not a pass/fail
gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare as cmp  # noqa: E402
import diff as dff  # noqa: E402


def _load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("cases JSON must be a non-empty list")
    cases: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"case {index} must be an object")
        cid = str(item.get("id") or item.get("name") or f"case{index:03d}")
        acad = Path(str(item.get("acad") or ""))
        ours = Path(str(item.get("ours") or ""))
        if not acad.is_file():
            raise FileNotFoundError(f"{cid}: AutoCAD PNG not found: {acad}")
        if not ours.is_file():
            raise FileNotFoundError(f"{cid}: VemCAD PNG not found: {ours}")
        case: dict[str, Any] = {"id": cid, "acad": acad, "ours": ours}
        semantic_mask_raw = item.get("semantic_mask")
        semantic_report_raw = item.get("semantic_report")
        if semantic_mask_raw or semantic_report_raw:
            if not semantic_mask_raw or not semantic_report_raw:
                raise ValueError(f"{cid}: semantic_mask and semantic_report must be provided together")
            semantic_mask = Path(str(semantic_mask_raw))
            semantic_report = Path(str(semantic_report_raw))
            if not semantic_mask.is_file():
                raise FileNotFoundError(f"{cid}: semantic mask PNG not found: {semantic_mask}")
            if not semantic_report.is_file():
                raise FileNotFoundError(f"{cid}: semantic render report not found: {semantic_report}")
            case["semantic_mask"] = semantic_mask
            case["semantic_report"] = semantic_report
        cases.append(case)
    return cases


def _thumb(path: Path, size: tuple[int, int]) -> Image.Image:
    img = Image.open(path).convert("RGB")
    thumb = ImageOps.contain(img, size)
    out = Image.new("RGB", size, "white")
    out.paste(thumb, ((size[0] - thumb.width) // 2, (size[1] - thumb.height) // 2))
    return out


def _write_contact(rows: list[dict[str, Any]], out: Path, key: str, title: str) -> None:
    if not rows:
        return
    tile_w, tile_h = 520, 360
    cols = 3
    rows_count = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (tile_w * cols, tile_h * rows_count), (238, 238, 238))
    draw = ImageDraw.Draw(sheet)
    for i, row in enumerate(rows):
        x = (i % cols) * tile_w
        y = (i // cols) * tile_h
        draw.rectangle([x, y, x + tile_w - 1, y + tile_h - 1], outline=(190, 190, 190))
        draw.text(
            (x + 8, y + 8),
            f"{row['id']} IoU {row['ink_iou']:.4f} aspect {row['aspect_delta']:.4f}",
            fill=(0, 0, 0),
        )
        draw.text((x + 8, y + 30), title, fill=(60, 60, 60))
        thumb = _thumb(Path(row[key]), (tile_w - 44, tile_h - 68))
        sheet.paste(thumb, (x + (tile_w - thumb.width) // 2, y + 60))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch compare AutoCAD PNGs to VemCAD PNGs.")
    parser.add_argument("--cases", type=Path, required=True, help="JSON list of {id, acad, ours}")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--capture-method", default="plot-raster")
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir = args.out_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    for case in cases:
        overlay = overlay_dir / f"{case['id']}_overlay.png"
        result = cmp.compare(case["acad"], case["ours"], capture_method=args.capture_method)
        dff.diff_overlay(case["acad"], case["ours"], out_path=overlay)
        row = {
            "id": case["id"],
            "acad": str(case["acad"]),
            "ours": str(case["ours"]),
            "overlay": str(overlay),
            "ink_iou": result.ink_iou,
            "ssim": result.ssim,
            "color_dist": result.color_dist,
            "aspect_delta": result.aspect_delta,
            "comparable": result.comparable,
            "band": result.band,
            "skip_reason": result.skip_reason,
        }
        rows.append(row)
        if "semantic_mask" in case and "semantic_report" in case:
            report = cmp.compare_semantic_classes(
                case["acad"],
                case["ours"],
                candidate_mask_path=case["semantic_mask"],
                render_report_path=case["semantic_report"],
                capture_method=args.capture_method,
            )
            row["semantic"] = {
                "diagnostic_kind": report.diagnostic_kind,
                "comparable": report.comparable,
                "skip_reason": report.skip_reason,
                "mask": str(case["semantic_mask"]),
                "report": str(case["semantic_report"]),
            }
            for class_row in report.classes:
                semantic_rows.append(
                    {
                        "id": case["id"],
                        "class": class_row.name,
                        "rgb": class_row.rgb,
                        "candidate_pixels": class_row.candidate_pixels,
                        "candidate_fraction": class_row.candidate_fraction,
                        "candidate_precision": class_row.candidate_precision,
                        "reference_coverage": class_row.reference_coverage,
                        "candidate_present": class_row.candidate_present,
                        "band": class_row.band,
                    }
                )

    summary = {
        "schema": "vemcad.autocad_batch_compare/v1",
        "capture_method": args.capture_method,
        "count": len(rows),
        "rows": rows,
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (args.out_dir / "summary.tsv").open("w", encoding="utf-8") as f:
        f.write("id\tink_iou\tssim\tcolor_dist\taspect_delta\tcomparable\tband\tacad\tours\toverlay\n")
        for row in rows:
            f.write(
                f"{row['id']}\t{row['ink_iou']}\t{row['ssim']}\t{row['color_dist']}\t"
                f"{row['aspect_delta']}\t{row['comparable']}\t{row['band']}\t"
                f"{row['acad']}\t{row['ours']}\t{row['overlay']}\n"
            )
    if semantic_rows:
        semantic_summary = {
            "schema": "vemcad.autocad_batch_semantic_compare/v1",
            "capture_method": args.capture_method,
            "count": len(semantic_rows),
            "rows": semantic_rows,
            "note": cmp.SEMANTIC_CLASS_NOTE,
        }
        (args.out_dir / "semantic_summary.json").write_text(
            json.dumps(semantic_summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with (args.out_dir / "semantic_summary.tsv").open("w", encoding="utf-8") as f:
            f.write(
                "id\tclass\trgb\tcandidate_pixels\tcandidate_fraction\t"
                "candidate_precision\treference_coverage\tcandidate_present\tband\n"
            )
            for row in semantic_rows:
                f.write(
                    f"{row['id']}\t{row['class']}\t{row['rgb']}\t"
                    f"{row['candidate_pixels']}\t{row['candidate_fraction']}\t"
                    f"{row['candidate_precision']}\t{row['reference_coverage']}\t"
                    f"{row['candidate_present']}\t{row['band']}\n"
                )

    _write_contact(rows, args.out_dir / "contact_autocad.png", "acad", "AutoCAD reference")
    _write_contact(rows, args.out_dir / "contact_vemcad.png", "ours", "VemCAD candidate")
    _write_contact(rows, args.out_dir / "contact_overlay.png", "overlay", "overlay red=missing green=extra")

    failed = [r for r in rows if r["band"] == "fallback" or not r["comparable"]]
    print(f"batch compare: {len(rows)} total, {len(failed)} fallback/not-comparable")
    if semantic_rows:
        print(f"semantic classes: {len(semantic_rows)} rows")
    print(f"summary: {args.out_dir / 'summary.tsv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
