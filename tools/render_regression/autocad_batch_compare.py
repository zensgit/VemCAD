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
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare as cmp  # noqa: E402
import diff as dff  # noqa: E402


def _render_service_styles():
    """Load render-service postprocess styles lazily.

    Batch comparison is an offline diagnostic, but it must use the same
    AutoCAD-like colour profiles as /render so review evidence does not drift
    from the service implementation.
    """
    service_root = Path(__file__).resolve().parents[2] / "services" / "render"
    if str(service_root) not in sys.path:
        sys.path.insert(0, str(service_root))
    from app.renderer import apply_acad_display_style, apply_acad_plot_style

    return {
        "acad-display": apply_acad_display_style,
        "acad-plot": apply_acad_plot_style,
    }


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


def _placeholder(size: tuple[int, int], text: str) -> Image.Image:
    out = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(out)
    draw.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=(200, 200, 200))
    y = 12
    for line in text.splitlines()[:8]:
        draw.text((12, y), line[:72], fill=(80, 80, 80))
        y += 18
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
        path_value = row.get(key)
        path = Path(path_value) if path_value else None
        if path is not None and path.is_file():
            thumb = _thumb(path, (tile_w - 44, tile_h - 68))
        else:
            reason = str(row.get("diff_skip_reason") or row.get("skip_reason") or "not written")
            thumb = _placeholder((tile_w - 44, tile_h - 68), f"no {key} image\n{reason}")
        sheet.paste(thumb, (x + (tile_w - thumb.width) // 2, y + 60))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def _parse_tile_grid(value: str) -> tuple[int, int]:
    normalized = value.lower().replace(",", "x")
    parts = [p.strip() for p in normalized.split("x") if p.strip()]
    if len(parts) != 2:
        raise ValueError("--tile-grid must be formatted as COLSxROWS, for example 4x3")
    cols, rows = (int(parts[0]), int(parts[1]))
    if cols < 1 or rows < 1 or cols > 24 or rows > 24:
        raise ValueError("--tile-grid dimensions must be in the range 1..24")
    return cols, rows


def _tile_bounds(cols: int, rows: int, width: int, height: int):
    for row in range(rows):
        y0 = round(row * height / rows)
        y1 = round((row + 1) * height / rows)
        for col in range(cols):
            x0 = round(col * width / cols)
            x1 = round((col + 1) * width / cols)
            yield row, col, x0, y0, x1, y1


def _write_tile_heatmap(
    tiles: list[dict[str, Any]],
    out: Path,
    *,
    cols: int,
    rows: int,
    canvas: tuple[int, int],
) -> None:
    width, height = canvas
    image = Image.new("RGB", (width, height), (252, 252, 252))
    draw = ImageDraw.Draw(image, "RGBA")
    for tile in tiles:
        x0, y0, x1, y1 = tile["bbox_px"]
        if tile["band"] == "absent":
            fill = (245, 245, 245, 255)
        else:
            loss = max(0.0, min(1.0, 1.0 - float(tile["ink_iou"])))
            red = int(70 + 185 * loss)
            green = int(210 - 160 * loss)
            fill = (red, green, 80, 190)
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=fill, outline=(70, 70, 70, 230))
        label = "blank" if tile["band"] == "absent" else f"{tile['ink_iou']:.2f}"
        draw.text((x0 + 6, y0 + 6), f"{tile['row']},{tile['col']} {label}", fill=(0, 0, 0, 255))
    draw.rectangle([0, 0, width - 1, height - 1], outline=(0, 0, 0, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)


def _tile_diagnostics(
    case_id: str,
    acad: Path,
    candidate: Path,
    *,
    grid: tuple[int, int],
    out_dir: Path,
) -> dict[str, Any]:
    cols, rows = grid
    ra, rb = cmp._load_rgb(Path(acad)), cmp._load_rgb(Path(candidate))
    ga, gb = ra.mean(axis=2), rb.mean(axis=2)
    ma, mb = cmp._ink_mask(ga), cmp._ink_mask(gb)
    bbox_a, bbox_b = cmp._ink_bbox(ma), cmp._ink_bbox(mb)
    canvas = cmp.CANVAS
    if bbox_a is None or bbox_b is None:
        return {
            "grid": {"cols": cols, "rows": rows},
            "canvas": list(canvas),
            "comparable": False,
            "skip_reason": "both-blank" if bbox_a is None and bbox_b is None else "blank-side",
            "heatmap": "",
            "worst_tiles": [],
            "tiles": [],
        }

    ref = cmp._crop_resize_to_bbox(ma, bbox_a, canvas)
    cand = cmp._crop_resize_to_bbox(mb, bbox_b, canvas)
    dx, dy = cmp._best_shift(ref, cand)
    cand_shift = cmp._shift(cand, dy, dx)
    width, height = canvas
    tiles: list[dict[str, Any]] = []
    total_ref = max(int(ref.sum()), 1)
    total_cand = max(int(cand_shift.sum()), 1)
    for row, col, x0, y0, x1, y1 in _tile_bounds(cols, rows, width, height):
        ref_tile = ref[y0:y1, x0:x1]
        cand_tile = cand_shift[y0:y1, x0:x1]
        ref_px = int(ref_tile.sum())
        cand_px = int(cand_tile.sum())
        if ref_px == 0 and cand_px == 0:
            score = 1.0
            band = "absent"
        else:
            score = cmp._ink_iou_tol(ref_tile, cand_tile, tol=cmp.DILATE_TOL)
            band = cmp.band_for(score)
        cand_d = cmp._dilate(cand_tile, cmp.DILATE_TOL)
        ref_d = cmp._dilate(ref_tile, cmp.DILATE_TOL)
        missing_px = int(np.logical_and(ref_tile, ~cand_d).sum())
        extra_px = int(np.logical_and(cand_tile, ~ref_d).sum())
        severity = (1.0 - score) * (ref_px + cand_px)
        tiles.append({
            "row": row,
            "col": col,
            "bbox_px": [x0, y0, x1, y1],
            "ink_iou": round(float(score), 4),
            "band": band,
            "ref_pixels": ref_px,
            "cand_pixels": cand_px,
            "ref_fraction": round(ref_px / total_ref, 6),
            "cand_fraction": round(cand_px / total_cand, 6),
            "missing_pixels": missing_px,
            "extra_pixels": extra_px,
            "severity": round(float(severity), 3),
        })
    heatmap = out_dir / f"{case_id}_tile_heatmap.png"
    _write_tile_heatmap(tiles, heatmap, cols=cols, rows=rows, canvas=canvas)
    worst_tiles = sorted(
        [tile for tile in tiles if tile["band"] != "absent"],
        key=lambda item: (item["severity"], 1.0 - item["ink_iou"]),
        reverse=True,
    )[:6]
    return {
        "grid": {"cols": cols, "rows": rows},
        "canvas": list(canvas),
        "comparable": True,
        "skip_reason": "",
        "dx": dx,
        "dy": dy,
        "heatmap": str(heatmap),
        "worst_tiles": worst_tiles,
        "tiles": tiles,
    }


def _semantic_tile_diagnostics(
    case_id: str,
    acad: Path,
    candidate: Path,
    *,
    semantic_mask: Path,
    render_report: Path,
    grid: tuple[int, int],
) -> dict[str, Any]:
    cols, rows = grid
    classes_meta, palette = cmp._semantic_classes_from_report(render_report)
    ra, rb = cmp._load_rgb(Path(acad)), cmp._load_rgb(Path(candidate))
    sem = cmp._load_rgb(Path(semantic_mask))
    canvas = cmp.CANVAS
    if sem.shape[:2] != rb.shape[:2]:
        return {
            "grid": {"cols": cols, "rows": rows},
            "canvas": list(canvas),
            "comparable": False,
            "skip_reason": "semantic-mask-size-mismatch",
            "classes": [],
        }

    ga, gb = ra.mean(axis=2), rb.mean(axis=2)
    ma, mb = cmp._ink_mask(ga), cmp._ink_mask(gb)
    bbox_a, bbox_b = cmp._ink_bbox(ma), cmp._ink_bbox(mb)
    if bbox_a is None or bbox_b is None:
        return {
            "grid": {"cols": cols, "rows": rows},
            "canvas": list(canvas),
            "comparable": False,
            "skip_reason": "both-blank" if bbox_a is None and bbox_b is None else "blank-side",
            "classes": [],
        }

    ref = cmp._crop_resize_to_bbox(ma, bbox_a, canvas)
    cand = cmp._crop_resize_to_bbox(mb, bbox_b, canvas)
    dx, dy = cmp._best_shift(ref, cand)
    class_masks = cmp._semantic_palette_masks(sem, palette)
    width, height = canvas
    rows_out: list[dict[str, Any]] = []
    for tile_row, tile_col, x0, y0, x1, y1 in _tile_bounds(cols, rows, width, height):
        ref_tile = ref[y0:y1, x0:x1]
        ref_d = cmp._dilate(ref_tile, cmp.DILATE_TOL)
        ref_total = float(ref_tile.sum())
        tile_area = float(max(1, (x1 - x0) * (y1 - y0)))
        for name, rgb, _ in palette:
            class_mask = cmp._crop_resize_to_bbox(class_masks[name], bbox_b, canvas)
            shifted = cmp._shift(class_mask, dy, dx)
            class_tile = shifted[y0:y1, x0:x1]
            cand_pixels = int(class_tile.sum())
            if cand_pixels:
                overlap = int(np.logical_and(class_tile, ref_d).sum())
                precision = overlap / float(cand_pixels)
                coverage = (
                    np.logical_and(ref_tile, cmp._dilate(class_tile, cmp.DILATE_TOL)).sum() / ref_total
                    if ref_total else 0.0
                )
            else:
                precision = 0.0
                coverage = 0.0
            rows_out.append({
                "id": case_id,
                "row": tile_row,
                "col": tile_col,
                "bbox_px": [x0, y0, x1, y1],
                "class": name,
                "rgb": rgb,
                "candidate_pixels": cand_pixels,
                "candidate_fraction": round(cand_pixels / tile_area, 6),
                "candidate_precision": round(float(precision), 4),
                "reference_coverage": round(float(coverage), 4),
                "candidate_present": cand_pixels > 0,
                "band": "absent" if not cand_pixels else cmp.band_for(float(precision)),
            })
    return {
        "grid": {"cols": cols, "rows": rows},
        "canvas": list(canvas),
        "comparable": True,
        "skip_reason": "",
        "dx": dx,
        "dy": dy,
        "reference_semantics": str(classes_meta.get("reference_semantics", "unknown")),
        "candidate_semantics": str(classes_meta.get("mask_kind", "candidate-renderer-semantic-class-buffer")),
        "classes": rows_out,
    }


def _background_rgb(img: Image.Image) -> tuple[int, int, int]:
    arr = np.asarray(img.convert("RGB"))
    edge = np.concatenate(
        [
            arr[:3, :, :].reshape(-1, 3),
            arr[-3:, :, :].reshape(-1, 3),
            arr[:, :3, :].reshape(-1, 3),
            arr[:, -3:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    return tuple(int(round(v)) for v in np.median(edge, axis=0))


def _ink_bbox(path: Path) -> Optional[tuple[int, int, int, int]]:
    with Image.open(path) as opened:
        img = opened.convert("RGB")
        img.load()
    gray = np.asarray(img).mean(axis=2)
    edge = np.concatenate(
        [gray[:3, :].ravel(), gray[-3:, :].ravel(), gray[:, :3].ravel(), gray[:, -3:].ravel()]
    )
    bg = float(np.median(edge))
    mask = np.abs(gray - bg) > 32.0
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return None
    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]
    return int(c0), int(r0), int(c1) + 1, int(r1) + 1


def _scale_bbox_to_size(
    bbox: tuple[int, int, int, int],
    from_size: tuple[int, int],
    to_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    fw, fh = from_size
    tw, th = to_size
    return (
        int(round(x0 / fw * tw)),
        int(round(y0 / fh * th)),
        int(round(x1 / fw * tw)),
        int(round(y1 / fh * th)),
    )


def _paste_bbox(
    src: Path,
    dst: Path,
    *,
    source_bbox: tuple[int, int, int, int],
    target_bbox: tuple[int, int, int, int],
    background: tuple[int, int, int],
    resample: Image.Resampling,
) -> None:
    with Image.open(src) as opened:
        img = opened.convert("RGB")
        img.load()
    sx0, sy0, sx1, sy1 = source_bbox
    tx0, ty0, tx1, ty1 = target_bbox
    target_w = max(1, tx1 - tx0)
    target_h = max(1, ty1 - ty0)
    crop = img.crop((sx0, sy0, sx1, sy1)).resize((target_w, target_h), resample)
    out = Image.new("RGB", img.size, background)
    out.paste(crop, (tx0, ty0))
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)


def _frame_candidate_to_reference(
    acad: Path,
    candidate: Path,
    out: Path,
    *,
    semantic_mask: Optional[Path] = None,
    semantic_out: Optional[Path] = None,
) -> dict[str, Any]:
    """Diagnostic-only: frame candidate ink into the AutoCAD reference envelope.

    This is not a render mode. It answers whether the remaining X3 delta survives
    after paper/capture envelope differences are removed for a known AutoCAD
    reference PNG.
    """
    ref_bbox = _ink_bbox(acad)
    cand_bbox = _ink_bbox(candidate)
    if ref_bbox is None or cand_bbox is None:
        out.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(candidate) as opened:
            opened.save(out)
        return {
            "mode": "fallback",
            "reason": "blank-side",
            "reference_bbox_px": list(ref_bbox) if ref_bbox else None,
            "candidate_bbox_px": list(cand_bbox) if cand_bbox else None,
        }
    with Image.open(acad) as ref_img, Image.open(candidate) as cand_img:
        target_bbox = _scale_bbox_to_size(ref_bbox, ref_img.size, cand_img.size)
        background = _background_rgb(cand_img)
    _paste_bbox(
        candidate, out,
        source_bbox=cand_bbox,
        target_bbox=target_bbox,
        background=background,
        resample=Image.Resampling.LANCZOS,
    )
    semantic_written = None
    if semantic_mask is not None and semantic_out is not None:
        _paste_bbox(
            semantic_mask, semantic_out,
            source_bbox=cand_bbox,
            target_bbox=target_bbox,
            background=(0, 0, 0),
            resample=Image.Resampling.NEAREST,
        )
        semantic_written = str(semantic_out)
    return {
        "mode": "reference-envelope",
        "reference_bbox_px": list(ref_bbox),
        "candidate_bbox_px": list(cand_bbox),
        "target_bbox_px": list(target_bbox),
        "semantic_mask": semantic_written,
    }


def _style_candidate(source: Path, out: Path, style: str) -> tuple[Path, dict[str, Any]]:
    if style == "source":
        return source, {"mode": "source", "path": str(source)}
    styles = _render_service_styles()
    if style not in styles:
        raise ValueError(f"unknown candidate style: {style}")
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, out)
    styles[style](out)
    return out, {"mode": style, "path": str(out), "source": str(source)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch compare AutoCAD PNGs to VemCAD PNGs.")
    parser.add_argument("--cases", type=Path, required=True, help="JSON list of {id, acad, ours}")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--capture-method", default="plot-raster")
    parser.add_argument(
        "--candidate-frame",
        choices=("none", "reference-envelope"),
        default="none",
        help=(
            "diagnostic-only candidate reframing before scoring. "
            "reference-envelope frames VemCAD ink into the AutoCAD PNG ink envelope."
        ),
    )
    parser.add_argument(
        "--candidate-style",
        choices=("source", "acad-display", "acad-plot"),
        default="source",
        help=(
            "diagnostic-only candidate colour profile before scoring. "
            "source preserves the PNG; acad-display and acad-plot reuse the /render service profiles."
        ),
    )
    parser.add_argument(
        "--tile-grid",
        default="",
        help=(
            "optional diagnostic local-error grid as COLSxROWS, for example 4x3. "
            "Scores tiles after the same global X3 crop/resize/shift alignment."
        ),
    )
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases)
    tile_grid = _parse_tile_grid(args.tile_grid) if args.tile_grid else None
    args.out_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir = args.out_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    styled_dir = args.out_dir / "styled_candidates"
    framed_dir = args.out_dir / "framed_candidates"
    semantic_framed_dir = args.out_dir / "framed_semantic_masks"
    tile_dir = args.out_dir / "tile_heatmaps"

    rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    tile_rows: list[dict[str, Any]] = []
    semantic_tile_rows: list[dict[str, Any]] = []
    for case in cases:
        overlay = overlay_dir / f"{case['id']}_overlay.png"
        source_result = cmp.compare(case["acad"], case["ours"], capture_method=args.capture_method)
        source_framing = cmp.framing_divergence(case["acad"], case["ours"])
        candidate, candidate_style = _style_candidate(
            case["ours"],
            styled_dir / f"{case['id']}_candidate_{args.candidate_style}.png",
            args.candidate_style,
        )
        semantic_mask = case.get("semantic_mask")
        candidate_frame = {"mode": "none"}
        if args.candidate_frame == "reference-envelope":
            frame_source = candidate
            candidate = framed_dir / f"{case['id']}_candidate_reference_envelope.png"
            semantic_out = None
            if semantic_mask is not None:
                semantic_out = semantic_framed_dir / f"{case['id']}_semantic_reference_envelope.png"
            candidate_frame = _frame_candidate_to_reference(
                case["acad"],
                frame_source,
                candidate,
                semantic_mask=semantic_mask,
                semantic_out=semantic_out,
            )
            if candidate_frame.get("semantic_mask"):
                semantic_mask = Path(str(candidate_frame["semantic_mask"]))

        result = cmp.compare(case["acad"], candidate, capture_method=args.capture_method)
        framing = cmp.framing_divergence(case["acad"], candidate)
        diff_result = dff.diff_overlay(case["acad"], candidate, out_path=overlay)
        row = {
            "id": case["id"],
            "acad": str(case["acad"]),
            "ours": str(candidate),
            "source_ours": str(case["ours"]),
            "overlay": diff_result.overlay_path or "",
            "diff_comparable": diff_result.comparable,
            "diff_skip_reason": diff_result.skip_reason,
            "candidate_style": candidate_style,
            "candidate_frame": candidate_frame,
            "source_ink_iou": source_result.ink_iou,
            "source_color_dist": source_result.color_dist,
            "source_framing_mismatch": source_framing["framing_mismatch"],
            "source_framing": source_framing,
            "delta_ink_iou": round(result.ink_iou - source_result.ink_iou, 6),
            "delta_color_dist": round(result.color_dist - source_result.color_dist, 6),
            "ink_iou": result.ink_iou,
            "ssim": result.ssim,
            "color_dist": result.color_dist,
            "aspect_delta": result.aspect_delta,
            "comparable": result.comparable,
            "band": result.band,
            "skip_reason": result.skip_reason,
            "framing_mismatch": framing["framing_mismatch"],
            "framing": framing,
        }
        if tile_grid is not None:
            tile_report = _tile_diagnostics(
                case["id"],
                case["acad"],
                candidate,
                grid=tile_grid,
                out_dir=tile_dir,
            )
            row["tile_report"] = {
                "grid": tile_report["grid"],
                "canvas": tile_report["canvas"],
                "comparable": tile_report["comparable"],
                "skip_reason": tile_report["skip_reason"],
                "dx": tile_report.get("dx", 0),
                "dy": tile_report.get("dy", 0),
                "heatmap": tile_report["heatmap"],
                "worst_tiles": tile_report["worst_tiles"],
            }
            for tile in tile_report["tiles"]:
                tile_rows.append({
                    "id": case["id"],
                    **tile,
                    "heatmap": tile_report["heatmap"],
                })
        rows.append(row)
        if "semantic_mask" in case and "semantic_report" in case:
            report = cmp.compare_semantic_classes(
                case["acad"],
                candidate,
                candidate_mask_path=semantic_mask,
                render_report_path=case["semantic_report"],
                capture_method=args.capture_method,
            )
            row["semantic"] = {
                "diagnostic_kind": report.diagnostic_kind,
                "comparable": report.comparable,
                "skip_reason": report.skip_reason,
                "mask": str(semantic_mask),
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
            if tile_grid is not None:
                semantic_tile_report = _semantic_tile_diagnostics(
                    case["id"],
                    case["acad"],
                    candidate,
                    semantic_mask=semantic_mask,
                    render_report=case["semantic_report"],
                    grid=tile_grid,
                )
                row["semantic_tile_report"] = {
                    "grid": semantic_tile_report["grid"],
                    "canvas": semantic_tile_report["canvas"],
                    "comparable": semantic_tile_report["comparable"],
                    "skip_reason": semantic_tile_report["skip_reason"],
                    "dx": semantic_tile_report.get("dx", 0),
                    "dy": semantic_tile_report.get("dy", 0),
                    "reference_semantics": semantic_tile_report.get("reference_semantics", "unknown"),
                    "candidate_semantics": semantic_tile_report.get("candidate_semantics", "unknown"),
                }
                semantic_tile_rows.extend(semantic_tile_report["classes"])

    summary = {
        "schema": "vemcad.autocad_batch_compare/v1",
        "capture_method": args.capture_method,
        "candidate_style_mode": args.candidate_style,
        "candidate_frame_mode": args.candidate_frame,
        "count": len(rows),
        "rows": rows,
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (args.out_dir / "summary.tsv").open("w", encoding="utf-8") as f:
        f.write(
            "id\tink_iou\tssim\tcolor_dist\taspect_delta\tcomparable\tband\t"
            "source_ink_iou\tsource_color_dist\tdelta_ink_iou\tdelta_color_dist\t"
            "source_framing_mismatch\tcandidate_style_mode\t"
            "framing_mismatch\tfill_divergence_x\tfill_divergence_y\t"
            "candidate_frame_mode\tacad\tours\tsource_ours\toverlay\n"
        )
        for row in rows:
            framing = row["framing"]
            f.write(
                f"{row['id']}\t{row['ink_iou']}\t{row['ssim']}\t{row['color_dist']}\t"
                f"{row['aspect_delta']}\t{row['comparable']}\t{row['band']}\t"
                f"{row['source_ink_iou']}\t{row['source_color_dist']}\t"
                f"{row['delta_ink_iou']}\t{row['delta_color_dist']}\t"
                f"{row['source_framing_mismatch']}\t{row['candidate_style']['mode']}\t"
                f"{row['framing_mismatch']}\t"
                f"{framing['fill_divergence_x']}\t{framing['fill_divergence_y']}\t"
                f"{row['candidate_frame']['mode']}\t"
                f"{row['acad']}\t{row['ours']}\t{row['source_ours']}\t{row['overlay']}\n"
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

    if tile_rows:
        tile_summary = {
            "schema": "vemcad.autocad_batch_tile_compare/v1",
            "capture_method": args.capture_method,
            "candidate_style_mode": args.candidate_style,
            "candidate_frame_mode": args.candidate_frame,
            "grid": {"cols": tile_grid[0], "rows": tile_grid[1]} if tile_grid else None,
            "count": len(tile_rows),
            "note": (
                "Diagnostic local-error tiles after the same global X3 alignment. "
                "This is not a pass/fail gate and not a semantic split."
            ),
            "rows": tile_rows,
        }
        (args.out_dir / "tile_summary.json").write_text(
            json.dumps(tile_summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with (args.out_dir / "tile_summary.tsv").open("w", encoding="utf-8") as f:
            f.write(
                "id\trow\tcol\tink_iou\tband\tref_pixels\tcand_pixels\t"
                "ref_fraction\tcand_fraction\tmissing_pixels\textra_pixels\t"
                "severity\theatmap\n"
            )
            for row in tile_rows:
                f.write(
                    f"{row['id']}\t{row['row']}\t{row['col']}\t{row['ink_iou']}\t"
                    f"{row['band']}\t{row['ref_pixels']}\t{row['cand_pixels']}\t"
                    f"{row['ref_fraction']}\t{row['cand_fraction']}\t"
                    f"{row['missing_pixels']}\t{row['extra_pixels']}\t"
                    f"{row['severity']}\t{row['heatmap']}\n"
                )

    if semantic_tile_rows:
        semantic_tile_summary = {
            "schema": "vemcad.autocad_batch_semantic_tile_compare/v1",
            "capture_method": args.capture_method,
            "candidate_style_mode": args.candidate_style,
            "candidate_frame_mode": args.candidate_frame,
            "grid": {"cols": tile_grid[0], "rows": tile_grid[1]} if tile_grid else None,
            "count": len(semantic_tile_rows),
            "note": (
                "Candidate semantic class diagnostics per local tile after the same global X3 alignment. "
                "AutoCAD reference semantics are unknown; rows report candidate class overlap with AutoCAD ink."
            ),
            "rows": semantic_tile_rows,
        }
        (args.out_dir / "semantic_tile_summary.json").write_text(
            json.dumps(semantic_tile_summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with (args.out_dir / "semantic_tile_summary.tsv").open("w", encoding="utf-8") as f:
            f.write(
                "id\trow\tcol\tclass\trgb\tcandidate_pixels\tcandidate_fraction\t"
                "candidate_precision\treference_coverage\tcandidate_present\tband\n"
            )
            for row in semantic_tile_rows:
                f.write(
                    f"{row['id']}\t{row['row']}\t{row['col']}\t{row['class']}\t{row['rgb']}\t"
                    f"{row['candidate_pixels']}\t{row['candidate_fraction']}\t"
                    f"{row['candidate_precision']}\t{row['reference_coverage']}\t"
                    f"{row['candidate_present']}\t{row['band']}\n"
                )

    _write_contact(rows, args.out_dir / "contact_autocad.png", "acad", "AutoCAD reference")
    _write_contact(rows, args.out_dir / "contact_vemcad.png", "ours", "VemCAD candidate")
    _write_contact(rows, args.out_dir / "contact_overlay.png", "overlay", "overlay red=missing green=extra")

    failed = [r for r in rows if r["band"] == "fallback" or not r["comparable"]]
    framing_mismatches = [r for r in rows if r["framing_mismatch"]]
    print(f"batch compare: {len(rows)} total, {len(failed)} fallback/not-comparable")
    print(f"framing mismatches: {len(framing_mismatches)}")
    if semantic_rows:
        print(f"semantic classes: {len(semantic_rows)} rows")
    if tile_rows:
        print(f"tile diagnostics: {len(tile_rows)} rows")
    if semantic_tile_rows:
        print(f"semantic tile classes: {len(semantic_tile_rows)} rows")
    print(f"summary: {args.out_dir / 'summary.tsv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
