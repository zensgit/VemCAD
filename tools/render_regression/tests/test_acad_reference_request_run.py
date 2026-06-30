import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_reference_request_run as runner  # noqa: E402


def _png(path: Path, size=(760, 570), box=None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, (255, 255, 255))
    if box is not None:
        draw = ImageDraw.Draw(image)
        draw.rectangle(box, outline=(0, 0, 0), width=3)
    image.save(path)
    return str(path)


def _dxf(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    return str(path)


def _request(path: Path, *, case_id="G11") -> Path:
    path.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "reason": "recapture-required",
        "cases": [{
            "id": case_id,
            "drawing_id": f"{case_id}/B11",
            "source_dxf": "dxf/B11.dxf",
            "recommended_output_name": f"{case_id}_autocad_model_extents.png",
            "requested_capture_method": "plot-export",
            "requested_view_contract": "model-extents",
        }],
    }), encoding="utf-8")
    return path


def _candidates(path: Path, *, case_id="G11") -> Path:
    path.write_text(json.dumps([{
        "id": case_id,
        "ours": "ours/G11.png",
        "diagnostics": {"window_source": "content_bbox"},
    }]), encoding="utf-8")
    return path


def test_reference_request_run_fulfills_and_compares_match(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", box=[20, 15, 740, 555])
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", box=[20, 15, 740, 555])
    request = _request(tmp_path / "reference_request.json")
    candidates = _candidates(tmp_path / "candidate_cases.json")
    out = tmp_path / "run"

    assert runner.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--case-id", "G11",
        "--out-dir", str(out),
    ]) == 0

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    compare_summary = json.loads((out / "compare" / "summary.json").read_text(encoding="utf-8"))
    assert summary["schema"] == "vemcad.acad_reference_request_run/v1"
    assert summary["status"] == "pass"
    assert summary["batch_exit_code"] == 0
    assert summary["compare_exit_code"] == 0
    assert summary["boundary"]["autocad_equivalence_claim"] is False
    assert summary["reference_intake_markdown"].endswith("reference_intake.md")
    assert summary["compare_summary_markdown"].endswith("summary.md")
    assert compare_summary["status"] == "pass"
    assert (out / "run_summary.md").is_file()


def test_reference_request_run_preserves_viewspace_mismatch_exit(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", size=(760, 570), box=[20, 15, 740, 555])
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", size=(800, 600), box=[220, 165, 580, 435])
    request = _request(tmp_path / "reference_request.json")
    candidates = _candidates(tmp_path / "candidate_cases.json")
    out = tmp_path / "run"

    assert runner.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--case-id", "G11",
        "--out-dir", str(out),
    ]) == 2

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    compare_summary = json.loads((out / "compare" / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "viewspace_mismatch"
    assert summary["batch_exit_code"] == 0
    assert summary["compare_exit_code"] == 2
    assert compare_summary["status"] == "viewspace_mismatch"


def test_reference_request_run_stops_on_missing_reference(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", box=[20, 15, 740, 555])
    request = _request(tmp_path / "reference_request.json")
    candidates = _candidates(tmp_path / "candidate_cases.json")
    out = tmp_path / "run"

    assert runner.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--case-id", "G11",
        "--out-dir", str(out),
    ]) == 2

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "input_blocked"
    assert summary["batch_exit_code"] == 2
    assert summary["compare_exit_code"] is None
    assert summary["missing_references_markdown"].endswith("missing_references.md")
    assert summary["compare_summary_markdown"] == ""
    assert not (out / "compare" / "summary.json").exists()
