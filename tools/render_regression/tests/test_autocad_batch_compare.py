"""Batch AutoCAD comparison helper tests — synthetic PNG pairs, no renderer."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import autocad_batch_compare as batch  # noqa: E402


def _framed(path: Path, size: tuple[int, int], box: list[int]) -> str:
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle(box, outline=(0, 0, 0), width=3)
    im.save(path)
    return str(path)


def test_batch_summary_records_framing_mismatch(tmp_path):
    # Same outline aspect, different page-fill: exactly the X3 capture mismatch
    # class that compare_vs_acad flags before interpreting a low IoU as renderer
    # divergence. The batch helper must carry that attribution too.
    acad = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "Gx", "acad": acad, "ours": ours}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main(["--cases", str(cases), "--out-dir", str(out)]) == 0

    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    assert row["framing_mismatch"] is True
    assert row["framing"]["fill_divergence_x"] > 0.05
    assert "framing_mismatch" in (out / "summary.tsv").read_text(encoding="utf-8").splitlines()[0]


def test_batch_reference_envelope_candidate_frame_removes_framing_mismatch(tmp_path):
    acad = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])
    ours = _framed(tmp_path / "ours.png", (800, 600), [40, 30, 760, 570])
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "Gx", "acad": acad, "ours": ours}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--cases", str(cases),
        "--out-dir", str(out),
        "--candidate-frame", "reference-envelope",
    ]) == 0

    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    assert payload["candidate_frame_mode"] == "reference-envelope"
    assert row["candidate_frame"]["mode"] == "reference-envelope"
    assert row["framing_mismatch"] is False
    assert row["source_framing_mismatch"] is True
    assert row["delta_ink_iou"] > 0.0
    assert row["ink_iou"] >= 0.90
    assert Path(row["ours"]).is_file()
    assert Path(row["overlay"]).is_file()
    assert row["source_ours"] == ours
    header = (out / "summary.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert "source_ink_iou" in header
    assert "delta_ink_iou" in header


def test_batch_candidate_style_uses_render_service_acad_display_profile(tmp_path):
    def make(path: Path, color: tuple[int, int, int]) -> str:
        im = Image.new("RGB", (240, 180), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.rectangle([40, 40, 200, 140], outline=color, width=5)
        im.save(path)
        return str(path)

    acad = make(tmp_path / "acad.png", (0, 0, 0))
    ours = make(tmp_path / "ours.png", (120, 120, 120))
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "Gx", "acad": acad, "ours": ours}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--cases", str(cases),
        "--out-dir", str(out),
        "--candidate-style", "acad-display",
        "--candidate-frame", "reference-envelope",
    ]) == 0

    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    assert payload["candidate_style_mode"] == "acad-display"
    assert row["candidate_style"]["mode"] == "acad-display"
    assert row["candidate_frame"]["mode"] == "reference-envelope"
    assert Path(row["candidate_style"]["path"]).parent.name == "styled_candidates"
    assert Path(row["ours"]).parent.name == "framed_candidates"
    assert row["source_color_dist"] > 60.0
    assert row["color_dist"] < row["source_color_dist"]
    assert row["delta_color_dist"] < 0.0
    assert Image.open(row["ours"]).convert("RGB").getpixel((40, 40)) == (0, 0, 0)
    header = (out / "summary.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert "candidate_style_mode" in header
    assert "delta_color_dist" in header


def test_batch_contact_sheet_tolerates_missing_overlay_for_uncomparable_diff(tmp_path):
    # Batch compare writes X3 rows even when diff.py refuses an overlay for a
    # view-space-mismatched pair. The contact sheet should render a placeholder
    # instead of crashing on the absent overlay file.
    acad = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])
    ours = _framed(tmp_path / "ours.png", (800, 600), [20, 220, 780, 380])
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "Gx", "acad": acad, "ours": ours}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main(["--cases", str(cases), "--out-dir", str(out)]) == 0

    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    assert row["diff_comparable"] is False
    assert row["diff_skip_reason"] == "view-space-mismatch"
    assert row["overlay"] == ""
    assert (out / "contact_overlay.png").is_file()


def test_batch_reference_envelope_frames_semantic_mask_with_candidate(tmp_path):
    acad = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])
    ours = _framed(tmp_path / "ours.png", (800, 600), [40, 30, 760, 570])

    mask = tmp_path / "semantic_mask.png"
    im = Image.new("RGB", (800, 600), (0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([40, 30, 760, 570], outline=(31, 119, 180), width=3)
    im.save(mask)

    report = tmp_path / "render_report.json"
    report.write_text(json.dumps({
        "semantic_classes": {
            "schema": "vemcad.render_semantic_classes",
            "schema_version": "0.1",
            "mask_kind": "candidate-renderer-semantic-class-buffer",
            "reference_semantics": "unknown",
            "palette": [
                {"name": "geometry", "rgb": "#1F77B4"},
            ],
        }
    }), encoding="utf-8")

    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{
        "id": "Gx",
        "acad": acad,
        "ours": ours,
        "semantic_mask": str(mask),
        "semantic_report": str(report),
    }]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--cases", str(cases),
        "--out-dir", str(out),
        "--candidate-frame", "reference-envelope",
    ]) == 0

    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    framed_mask = Path(row["semantic"]["mask"])
    assert framed_mask.is_file()
    assert framed_mask.parent.name == "framed_semantic_masks"

    semantic = json.loads((out / "semantic_summary.json").read_text(encoding="utf-8"))
    assert semantic["rows"][0]["class"] == "geometry"
    assert semantic["rows"][0]["candidate_present"] is True


def test_batch_tile_grid_reports_localized_missing_ink(tmp_path):
    def make(path: Path, *, missing_top_right: bool) -> str:
        im = Image.new("RGB", (400, 300), (255, 255, 255))
        d = ImageDraw.Draw(im)
        # Shared outer frame keeps both ink bboxes identical. The only real
        # divergence is the dense annotation-like strokes in the top-right tile.
        d.rectangle([20, 20, 380, 280], outline=(0, 0, 0), width=3)
        if not missing_top_right:
            for y in range(45, 135, 12):
                d.line([230, y, 355, y], fill=(0, 0, 0), width=2)
        im.save(path)
        return str(path)

    acad = make(tmp_path / "acad.png", missing_top_right=False)
    ours = make(tmp_path / "ours.png", missing_top_right=True)
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "Gx", "acad": acad, "ours": ours}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--cases", str(cases),
        "--out-dir", str(out),
        "--tile-grid", "2x2",
    ]) == 0

    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    report = payload["rows"][0]["tile_report"]
    assert report["grid"] == {"cols": 2, "rows": 2}
    assert Path(report["heatmap"]).is_file()
    assert report["worst_tiles"][0]["row"] == 0
    assert report["worst_tiles"][0]["col"] == 1
    assert report["worst_tiles"][0]["missing_pixels"] > 0

    tile_summary = json.loads((out / "tile_summary.json").read_text(encoding="utf-8"))
    assert tile_summary["schema"] == "vemcad.autocad_batch_tile_compare/v1"
    assert len(tile_summary["rows"]) == 4
    assert "severity" in (out / "tile_summary.tsv").read_text(encoding="utf-8").splitlines()[0]


def test_batch_semantic_tile_grid_reports_class_locality(tmp_path):
    acad = _framed(tmp_path / "acad.png", (400, 300), [20, 20, 380, 280])
    ours = _framed(tmp_path / "ours.png", (400, 300), [20, 20, 380, 280])

    # Add a candidate-side dimension-like stroke in the top-right tile that
    # does not overlap AutoCAD ink. The semantic tile report should attribute
    # the local extra ink to the dimension class, not just to a generic bad
    # tile score.
    im = Image.open(ours).convert("RGB")
    d = ImageDraw.Draw(im)
    d.line([230, 70, 355, 70], fill=(0, 0, 0), width=3)
    im.save(ours)

    mask = tmp_path / "semantic_mask.png"
    sem = Image.new("RGB", (400, 300), (0, 0, 0))
    sd = ImageDraw.Draw(sem)
    sd.line([230, 70, 355, 70], fill=(214, 39, 40), width=3)
    sem.save(mask)

    report = tmp_path / "render_report.json"
    report.write_text(json.dumps({
        "semantic_classes": {
            "schema": "vemcad.render_semantic_classes",
            "schema_version": "0.1",
            "mask_kind": "candidate-renderer-semantic-class-buffer",
            "reference_semantics": "unknown",
            "palette": [
                {"name": "geometry", "rgb": "#1F77B4"},
                {"name": "dimension", "rgb": "#D62728"},
            ],
        }
    }), encoding="utf-8")

    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{
        "id": "Gx",
        "acad": acad,
        "ours": ours,
        "semantic_mask": str(mask),
        "semantic_report": str(report),
    }]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--cases", str(cases),
        "--out-dir", str(out),
        "--tile-grid", "2x2",
    ]) == 0

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["rows"][0]["semantic_tile_report"]["grid"] == {"cols": 2, "rows": 2}

    semantic_tiles = json.loads((out / "semantic_tile_summary.json").read_text(encoding="utf-8"))
    dimension_rows = [
        row for row in semantic_tiles["rows"]
        if row["class"] == "dimension" and row["candidate_present"]
    ]
    assert len(dimension_rows) == 1
    row = dimension_rows[0]
    assert row["row"] == 0
    assert row["col"] == 1
    assert row["candidate_pixels"] > 0
    assert row["candidate_precision"] < 0.5
    assert "candidate_precision" in (
        out / "semantic_tile_summary.tsv"
    ).read_text(encoding="utf-8").splitlines()[0]
