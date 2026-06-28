"""Text provenance diagnostics for render_cli reports.

This is an observability helper for G11-style AutoCAD comparison work. It reads
`render_cli --report` text_placement records and turns them into reviewable
entity-level rows, buckets, and an optional overlay. It does not render, compare
against AutoCAD, or change any gate threshold.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw


SCHEMA = "vemcad.text_provenance_diagnostics/v1"


KIND_COLORS = {
    "text": (31, 119, 180),
    "mtext": (148, 103, 189),
    "attrib": (255, 127, 14),
    "attdef": (214, 39, 40),
    "dimension": (44, 160, 44),
    "": (127, 127, 127),
}


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _text_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    text_placement = report.get("text_placement")
    if not isinstance(text_placement, dict):
        return []
    records = text_placement.get("records")
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _screen_bbox(record: dict[str, Any]) -> dict[str, float] | None:
    x = _float(record.get("screen_x"))
    y = _float(record.get("screen_y"))
    width = _float(record.get("max_line_width_px"))
    height = _float(record.get("block_height_px"))
    if x is None or y is None or width is None or height is None:
        return None
    return {
        "left": x,
        "top": y - height,
        "right": x + max(width, 0.0),
        "bottom": y,
        "width": max(width, 0.0),
        "height": max(height, 0.0),
    }


def _union_bbox(bboxes: Iterable[dict[str, float] | None]) -> dict[str, float] | None:
    vals = [bbox for bbox in bboxes if bbox is not None]
    if not vals:
        return None
    left = min(v["left"] for v in vals)
    top = min(v["top"] for v in vals)
    right = max(v["right"] for v in vals)
    bottom = max(v["bottom"] for v in vals)
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top,
    }


def _layout_flags(record: dict[str, Any], bbox: dict[str, float] | None, viewport: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    source_type = _str(record.get("source_type"))
    text_kind = _str(record.get("text_kind"))
    block_name = _str(record.get("block_name"))
    attribute_tag = _str(record.get("attribute_tag"))

    if not text_kind:
        flags.append("missing_text_kind")
    if source_type == "INSERT" and not block_name:
        flags.append("missing_block_name_for_insert")
    if text_kind in {"attrib", "attdef"} and not attribute_tag:
        flags.append("missing_attribute_tag")
    if not _str(record.get("resolved_family")):
        flags.append("missing_resolved_family")
    if _str(record.get("text_style_known")) and not _boolish(record.get("text_style_known")):
        flags.append("unknown_text_style")

    target_px = _float(record.get("target_px"))
    font_px = _float(record.get("font_px"))
    block_height_px = _float(record.get("block_height_px"))
    if target_px and block_height_px:
        # `font_px` is QFont's pixel size, chosen so the actual glyph tight bbox
        # reaches the target. For sparse ATTDEF glyphs it can legitimately be
        # much larger than target_px. Flag the visible text block instead.
        ratio = block_height_px / target_px
        if ratio < 0.65 or ratio > 1.45:
            flags.append("block_height_target_ratio_outlier")
    elif target_px and font_px:
        # Last-resort only for older reports that do not carry block_height_px.
        ratio = font_px / target_px
        if ratio < 0.75 or ratio > 1.75:
            flags.append("font_px_target_ratio_outlier")

    width_factor = _float(record.get("width_factor"))
    if width_factor is not None and (width_factor < 0.35 or width_factor > 1.5):
        flags.append("width_factor_outlier")

    viewport_w = _float(viewport.get("viewport_w"))
    viewport_h = _float(viewport.get("viewport_h"))
    if bbox and viewport_w and viewport_h:
        if bbox["right"] < 0 or bbox["bottom"] < 0 or bbox["left"] > viewport_w or bbox["top"] > viewport_h:
            flags.append("bbox_outside_viewport")
        elif bbox["left"] < 0 or bbox["top"] < 0 or bbox["right"] > viewport_w or bbox["bottom"] > viewport_h:
            flags.append("bbox_partially_outside_viewport")

    return flags


def _layout_notes(record: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    rotation = _float(record.get("rotation_deg")) or 0.0
    if abs(rotation) > 0.01:
        notes.append("rotated_bbox_is_approximate")
    return notes


def _record_row(record: dict[str, Any], viewport: dict[str, Any]) -> dict[str, Any]:
    bbox = _screen_bbox(record)
    flags = _layout_flags(record, bbox, viewport)
    notes = _layout_notes(record)
    font_px = _float(record.get("font_px"))
    target_px = _float(record.get("target_px"))
    block_height_px = _float(record.get("block_height_px"))
    return {
        "entity_id": _str(record.get("entity_id")),
        "source_type": _str(record.get("source_type")),
        "semantic_class": _str(record.get("semantic_class")),
        "block_name": _str(record.get("block_name")),
        "text_kind": _str(record.get("text_kind")),
        "attribute_tag": _str(record.get("attribute_tag")),
        "text_style": _str(record.get("text_style")),
        "text_font_file": _str(record.get("text_font_file")),
        "text_bigfont_file": _str(record.get("text_bigfont_file")),
        "requested_family": _str(record.get("requested_family")),
        "resolved_family": _str(record.get("resolved_family")),
        "height_world": _float(record.get("height_world")),
        "font_px": font_px,
        "target_px": target_px,
        "block_height_px": block_height_px,
        "font_target_ratio": font_px / target_px if font_px is not None and target_px else None,
        "block_height_target_ratio": block_height_px / target_px if block_height_px is not None and target_px else None,
        "max_line_width_px": _float(record.get("max_line_width_px")),
        "screen_x": _float(record.get("screen_x")),
        "screen_y": _float(record.get("screen_y")),
        "rotation_deg": _float(record.get("rotation_deg")) or 0.0,
        "width_factor": _float(record.get("width_factor")),
        "effective_width_factor": _str(record.get("text_effective_width_factor")),
        "line_count": _float(record.get("line_count")),
        "non_empty_line_count": _float(record.get("non_empty_line_count")),
        "screen_bbox": bbox,
        "layout_flags": flags,
        "layout_notes": notes,
    }


def _matches(row: dict[str, Any], args: argparse.Namespace) -> bool:
    def in_filter(field: str, values: list[str] | None) -> bool:
        return not values or row[field] in values

    if args.title_block:
        if not (row["block_name"] or row["attribute_tag"] or row["semantic_class"] == "insert_text"):
            return False
    return (
        in_filter("block_name", args.block)
        and in_filter("source_type", args.source_type)
        and in_filter("text_kind", args.text_kind)
        and in_filter("semantic_class", args.semantic_class)
    )


def analyze_report(report: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    viewport = report.get("view") if isinstance(report.get("view"), dict) else {}
    all_rows = [_record_row(record, viewport) for record in _text_records(report)]
    rows = [row for row in all_rows if _matches(row, args)]
    rows.sort(key=lambda row: (
        row.get("screen_y") if row.get("screen_y") is not None else -1,
        row.get("screen_x") if row.get("screen_x") is not None else -1,
        row.get("entity_id"),
    ))

    grouped: dict[tuple[str, str, str, bool, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(
            row["source_type"],
            row["text_kind"],
            row["block_name"],
            bool(row["attribute_tag"]),
            row["semantic_class"],
        )].append(row)

    buckets = []
    for key, bucket_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        source_type, text_kind, block_name, has_attribute_tag, semantic_class = key
        buckets.append({
            "source_type": source_type,
            "text_kind": text_kind,
            "block_name": block_name,
            "has_attribute_tag": has_attribute_tag,
            "semantic_class": semantic_class,
            "count": len(bucket_rows),
            "entity_ids": [row["entity_id"] for row in bucket_rows],
            "screen_bbox": _union_bbox(row["screen_bbox"] for row in bucket_rows),
            "flags": sorted({flag for row in bucket_rows for flag in row["layout_flags"]}),
            "notes": sorted({note for row in bucket_rows for note in row["layout_notes"]}),
        })

    flag_counts = Counter(flag for row in rows for flag in row["layout_flags"])
    note_counts = Counter(note for row in rows for note in row["layout_notes"])
    return {
        "schema": SCHEMA,
        "source": report.get("source", ""),
        "render_report_schema": report.get("schema", ""),
        "render_report_schema_version": report.get("schema_version", ""),
        "text_placement_schema": (report.get("text_placement") or {}).get("schema", ""),
        "text_placement_schema_version": (report.get("text_placement") or {}).get("schema_version", ""),
        "filter": {
            "title_block": bool(args.title_block),
            "block": args.block or [],
            "source_type": args.source_type or [],
            "text_kind": args.text_kind or [],
            "semantic_class": args.semantic_class or [],
        },
        "counts": {
            "all_text_records": len(all_rows),
            "selected_text_records": len(rows),
            "bucket_count": len(buckets),
            "flag_counts": dict(sorted(flag_counts.items())),
            "note_counts": dict(sorted(note_counts.items())),
        },
        "viewport": {
            "width": _float(viewport.get("viewport_w")),
            "height": _float(viewport.get("viewport_h")),
            "scale": _float(viewport.get("scale")),
            "clip": viewport.get("clip"),
        },
        "selected_screen_bbox": _union_bbox(row["screen_bbox"] for row in rows),
        "buckets": buckets,
        "records": rows,
    }


def write_tsv(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "entity_id", "source_type", "semantic_class", "block_name", "text_kind",
        "attribute_tag", "text_style", "text_font_file", "text_bigfont_file",
        "resolved_family", "font_px", "target_px", "block_height_px",
        "font_target_ratio", "block_height_target_ratio",
        "max_line_width_px", "screen_x", "screen_y", "rotation_deg",
        "width_factor", "layout_flags", "layout_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for row in payload["records"]:
            flat = {field: row.get(field, "") for field in fields}
            flat["layout_flags"] = ",".join(row.get("layout_flags", []))
            flat["layout_notes"] = ",".join(row.get("layout_notes", []))
            writer.writerow(flat)


def write_overlay(image_path: Path, payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    for row in payload["records"]:
        bbox = row.get("screen_bbox")
        if not bbox:
            continue
        kind = row.get("text_kind", "")
        color = KIND_COLORS.get(kind, (127, 127, 127))
        outline = color + (230,)
        fill = color + (32,)
        xy = [bbox["left"], bbox["top"], bbox["right"], bbox["bottom"]]
        draw.rectangle(xy, outline=outline, fill=fill, width=2)
        label = row.get("attribute_tag") or row.get("entity_id") or kind or "text"
        label = f"{kind or '?'}:{label}"
        lx, ly = bbox["left"], max(0, bbox["top"] - 12)
        draw.rectangle([lx, ly, lx + min(180, 7 * len(label) + 6), ly + 12], fill=(255, 255, 255, 210))
        draw.text((lx + 3, ly), label, fill=outline)
    image.save(path)


def _print_summary(payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    print("Text provenance diagnostics")
    print(f"  source             : {payload['source']}")
    print(f"  text schema        : {payload['text_placement_schema']} {payload['text_placement_schema_version']}")
    print(f"  selected / all     : {counts['selected_text_records']} / {counts['all_text_records']}")
    print(f"  buckets            : {counts['bucket_count']}")
    if counts["flag_counts"]:
        print("  flags              : " + ", ".join(f"{k}={v}" for k, v in counts["flag_counts"].items()))
    else:
        print("  flags              : none")
    if counts.get("note_counts"):
        print("  notes              : " + ", ".join(f"{k}={v}" for k, v in counts["note_counts"].items()))
    else:
        print("  notes              : none")
    for bucket in payload["buckets"][:12]:
        tag = "tag" if bucket["has_attribute_tag"] else "no-tag"
        print("  - count=%-3d source=%-9s kind=%-7s block=%-14s %s flags=%s notes=%s" % (
            bucket["count"],
            bucket["source_type"] or "(empty)",
            bucket["text_kind"] or "(empty)",
            bucket["block_name"] or "(empty)",
            tag,
            ",".join(bucket["flags"]) or "-",
            ",".join(bucket.get("notes", [])) or "-",
        ))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="text_provenance_diagnostics",
        description="Summarize render_cli text_placement provenance records.")
    ap.add_argument("report", type=Path, help="render_cli --report JSON")
    ap.add_argument("--image", type=Path, default=None, help="candidate render PNG for overlay")
    ap.add_argument("--out-dir", type=Path, default=None, help="directory for default JSON/TSV/overlay outputs")
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--tsv-out", type=Path, default=None)
    ap.add_argument("--overlay-out", type=Path, default=None)
    ap.add_argument("--title-block", action="store_true", help="keep likely title-block/block text rows")
    ap.add_argument("--block", action="append", default=None, help="block_name filter; may repeat")
    ap.add_argument("--source-type", action="append", default=None, help="source_type filter; may repeat")
    ap.add_argument("--text-kind", action="append", default=None, help="text_kind filter; may repeat")
    ap.add_argument("--semantic-class", action="append", default=None, help="semantic_class filter; may repeat")
    ap.add_argument("--print-summary", action="store_true")
    args = ap.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    payload = analyze_report(report, args)

    out_dir = args.out_dir
    json_out = args.json_out or (out_dir / "text_provenance_summary.json" if out_dir else None)
    tsv_out = args.tsv_out or (out_dir / "text_provenance_records.tsv" if out_dir else None)
    overlay_out = args.overlay_out or (out_dir / "text_provenance_overlay.png" if out_dir and args.image else None)

    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if tsv_out:
        write_tsv(payload, tsv_out)
    if overlay_out:
        if args.image is None:
            ap.error("--overlay-out requires --image")
        write_overlay(args.image, payload, overlay_out)
    if args.print_summary or not any([json_out, tsv_out, overlay_out]):
        _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
