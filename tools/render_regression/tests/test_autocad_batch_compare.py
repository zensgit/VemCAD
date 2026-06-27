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
    assert row["ink_iou"] >= 0.90
    assert Path(row["ours"]).is_file()
    assert Path(row["overlay"]).is_file()
    assert row["source_ours"] == ours


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
