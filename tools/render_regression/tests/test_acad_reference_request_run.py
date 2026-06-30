import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_reference_request_run as runner  # noqa: E402


def _run_artifact_kinds(out: Path) -> set[str]:
    payload = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "vemcad.acad_reference_request_run_artifact_index/v1"
    return {item["kind"] for item in payload["artifacts"]}


def _png(path: Path, size=(760, 570), box=None, color=(255, 255, 255)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color)
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
    _png(tmp_path / "ours" / "G11.png", size=(1600, 1131), box=[40, 30, 1560, 1100])
    _png(
        tmp_path / "returned" / "G11_autocad_model_extents.png",
        size=(1600, 1131),
        box=[40, 30, 1560, 1100],
    )
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
    assert summary["run_artifact_index"].endswith("artifact_index.json")
    assert summary["batch_exit_code"] == 0
    assert summary["compare_exit_code"] == 0
    assert summary["boundary"]["autocad_equivalence_claim"] is False
    assert summary["reference_request_validation_status"] == "pass"
    assert summary["reference_request_validation_error_count"] == 0
    assert summary["reference_request_validation_markdown"].endswith("reference_request_validation.md")
    assert summary["reference_intake_status"] == "pass"
    assert summary["reference_intake_warning_count"] == 0
    assert summary["reference_intake_markdown"].endswith("reference_intake.md")
    assert summary["compare_summary_markdown"].endswith("summary.md")
    assert summary["recommended_next_action"]["code"] == "review-x3-pass"
    assert summary["recommended_next_action"]["artifact"].endswith("summary.md")
    assert compare_summary["status"] == "pass"
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "recommended_next_action: `review-x3-pass`" in summary_md
    assert _run_artifact_kinds(out) >= {
        "run_summary_json",
        "run_summary_markdown",
        "input_artifact_index",
        "reference_request_validation_json",
        "reference_request_validation_markdown",
        "reference_intake_json",
        "reference_intake_markdown",
        "compare_summary_json",
        "compare_summary_markdown",
        "compare_artifact_index",
    }


def test_reference_request_run_preserves_viewspace_mismatch_exit(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", size=(760, 570), box=[20, 15, 740, 555])
    _png(
        tmp_path / "returned" / "G11_autocad_model_extents.png",
        size=(1600, 1200),
        box=[400, 300, 1200, 900],
    )
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
    assert summary["reference_request_validation_status"] == "pass"
    assert summary["batch_exit_code"] == 0
    assert summary["compare_exit_code"] == 2
    assert summary["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert "do not tune the renderer" in summary["recommended_next_action"]["message"]
    assert compare_summary["status"] == "viewspace_mismatch"


def test_reference_request_run_surfaces_intake_review_warnings(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", size=(760, 570), box=[20, 15, 740, 555])
    _png(
        tmp_path / "returned" / "G11_autocad_model_extents.png",
        size=(900, 600),
        box=[220, 165, 580, 435],
        color=(12, 12, 12),
    )
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
    assert summary["status"] == "viewspace_mismatch"
    assert summary["reference_request_validation_status"] == "pass"
    assert summary["reference_intake_status"] == "review"
    assert summary["reference_intake_warning_count"] == 2
    assert summary["recommended_next_action"]["code"] == "inspect-returned-reference-warnings"
    assert summary["recommended_next_action"]["artifact"].endswith("reference_intake.md")
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "reference_intake_status: `review`" in summary_md
    assert "reference_intake_warnings: `2`" in summary_md
    assert "recommended_next_action: `inspect-returned-reference-warnings`" in summary_md


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
    assert summary["reference_request_validation_status"] == "pass"
    assert summary["missing_references_markdown"].endswith("missing_references.md")
    assert summary["reference_intake_status"] == ""
    assert summary["reference_intake_warning_count"] is None
    assert summary["compare_summary_markdown"] == ""
    assert summary["recommended_next_action"]["code"] == "provide-returned-autocad-pngs"
    assert summary["recommended_next_action"]["artifact"].endswith("missing_references.md")
    assert not (out / "compare" / "summary.json").exists()
    assert _run_artifact_kinds(out) >= {
        "run_summary_json",
        "run_summary_markdown",
        "input_artifact_index",
        "reference_request_validation_json",
        "reference_request_validation_markdown",
        "missing_references_json",
        "missing_references_markdown",
    }
    assert "compare_summary_json" not in _run_artifact_kinds(out)


def test_reference_request_run_surfaces_request_validation_block(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", box=[20, 15, 740, 555])
    _png(
        tmp_path / "returned" / "G11_autocad_model_extents.png",
        size=(1600, 1131),
        box=[40, 30, 1560, 1100],
    )
    request = _request(tmp_path / "reference_request.json")
    payload = json.loads(request.read_text(encoding="utf-8"))
    payload["cases"][0]["source_dxf_sha256"] = "0" * 64
    request.write_text(json.dumps(payload), encoding="utf-8")
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
    assert summary["reference_request_validation_status"] == "blocked"
    assert summary["reference_request_validation_error_count"] == 1
    assert summary["reference_request_validation_markdown"].endswith("reference_request_validation.md")
    assert summary["recommended_next_action"]["code"] == "fix-request-package"
    assert summary["recommended_next_action"]["artifact"].endswith("reference_request_validation.md")
    assert summary["reference_intake_status"] == ""
    assert not (out / "compare" / "summary.json").exists()
    assert _run_artifact_kinds(out) >= {
        "run_summary_json",
        "run_summary_markdown",
        "input_artifact_index",
        "reference_request_validation_json",
        "reference_request_validation_markdown",
    }
    assert "reference_intake_json" not in _run_artifact_kinds(out)
    assert "compare_summary_json" not in _run_artifact_kinds(out)
