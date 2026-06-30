import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_manifest_compare as harness  # noqa: E402
import acad_reference_batch as batch  # noqa: E402


def _png(path: Path, size=(320, 240), color=(255, 255, 255), box=None) -> str:
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_batch_generator_writes_manifest_and_candidates(tmp_path):
    _png(tmp_path / "acad" / "G01.png", (320, 240))
    _png(tmp_path / "ours" / "G01.png", (320, 240))
    _png(tmp_path / "acad" / "G02.png", (640, 480))
    _png(tmp_path / "ours" / "G02.png", (640, 480))
    _dxf(tmp_path / "dxf" / "G01.dxf")
    _dxf(tmp_path / "dxf" / "G02.dxf")
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([
        {
            "id": "G01",
            "drawing_id": "G01/source",
            "source_dxf": "dxf/G01.dxf",
            "acad_png": "acad/G01.png",
            "ours": "ours/G01.png",
            "diagnostics": {"window_source": "extents"},
        },
        {
            "id": "G02",
            "drawing_id": "G02/source",
            "source_dxf": "dxf/G02.dxf",
            "acad_png": "acad/G02.png",
            "ours": "ours/G02.png",
            "capture_method": "exportpng",
            "view_contract": "explicit-window",
            "render_image": "ghcr.io/zensgit/vemcad-render:main",
        },
    ]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main(["--cases", str(cases), "--out-dir", str(out)]) == 0

    manifest = json.loads((out / "acad_manifest.json").read_text(encoding="utf-8"))
    candidates = json.loads((out / "candidate_cases.json").read_text(encoding="utf-8"))
    assert [case["id"] for case in manifest["cases"]] == ["G01", "G02"]
    assert manifest["cases"][0]["expected_size"] == {"width": 320, "height": 240}
    assert manifest["cases"][1]["expected_size"] == {"width": 640, "height": 480}
    assert manifest["cases"][1]["capture_method"] == "exportpng"
    assert manifest["cases"][1]["view_contract"] == "explicit-window"
    assert candidates[0]["diagnostics"] == {"window_source": "extents"}
    assert candidates[1]["render_image"] == "ghcr.io/zensgit/vemcad-render:main"
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["schema"] == "vemcad.acad_reference_batch_artifact_index/v1"
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "acad_manifest",
        "candidate_cases",
    }

    dry_run = tmp_path / "dry-run"
    assert harness.main([
        "--manifest", str(out / "acad_manifest.json"),
        "--out-dir", str(dry_run),
        "--dry-run",
    ]) == 0


def test_batch_generator_blocks_bad_cases_json(tmp_path):
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "G01"}]), encoding="utf-8")

    assert batch.main(["--cases", str(cases), "--out-dir", str(tmp_path / "out")]) == 2


def test_batch_generator_validates_reference_request_package_before_fulfilment(tmp_path):
    source = Path(_dxf(tmp_path / "dxf" / "G11.dxf"))
    ours = Path(_png(tmp_path / "ours" / "G11.png", (760, 570)))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "source_dxf_sha256": _sha256(source),
            "source_dxf_size_bytes": source.stat().st_size,
            "candidate_png_sha256": _sha256(ours),
            "candidate_png_size_bytes": ours.stat().st_size,
            "recommended_output_name": "G11_autocad_model_extents.png",
            "requested_expected_size": {"width": 1600, "height": 1131},
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{"id": "G11", "ours": "ours/G11.png"}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--validate-request", str(request),
        "--candidate-cases", str(candidates),
        "--out-dir", str(out),
    ]) == 0

    validation = json.loads((out / "reference_request_validation.json").read_text(encoding="utf-8"))
    assert validation["schema"] == "vemcad.acad_reference_request_validation/v1"
    assert validation["status"] == "pass"
    assert validation["error_count"] == 0
    assert validation["boundary"]["requires_returned_autocad_png"] is False
    assert validation["boundary"]["autocad_equivalence_claim"] is False
    row = validation["cases"][0]
    assert row["source_dxf_provenance"]["sha256"] == _sha256(source)
    assert row["candidate_png_provenance"]["sha256"] == _sha256(ours)
    validation_md = (out / "reference_request_validation.md").read_text(encoding="utf-8")
    assert "AutoCAD Reference Request Validation" in validation_md
    assert "G11_autocad_model_extents.png" in validation_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "reference_request_validation_json",
        "reference_request_validation_markdown",
    }


def test_batch_generator_validation_blocks_drift_and_ambiguous_request_package(tmp_path):
    source = Path(_dxf(tmp_path / "dxf" / "G11.dxf"))
    ours = Path(_png(tmp_path / "ours" / "G11.png", (760, 570)))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [
            {
                "id": "G11",
                "drawing_id": "G11/B11",
                "source_dxf": "dxf/G11.dxf",
                "source_dxf_sha256": "0" * 64,
                "source_dxf_size_bytes": source.stat().st_size + 1,
                "candidate_png_sha256": "f" * 64,
                "candidate_png_size_bytes": ours.stat().st_size + 1,
                "recommended_output_name": "../G11.png",
                "requested_expected_size": {"width": 0, "height": "bad"},
            },
            {
                "id": "G12",
                "drawing_id": "G12/B12",
                "source_dxf": "dxf/missing.dxf",
                "recommended_output_name": "../G11.png",
            },
        ],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([
        {"id": "G11", "ours": "ours/G11.png"},
        {"id": "G11", "ours": "ours/G11-duplicate.png"},
    ]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--validate-request", str(request),
        "--candidate-cases", str(candidates),
        "--out-dir", str(out),
    ]) == 2

    validation = json.loads((out / "reference_request_validation.json").read_text(encoding="utf-8"))
    assert validation["status"] == "blocked"
    issue_codes = {issue["code"] for issue in validation["issues"]}
    assert {
        "duplicate_candidate_id",
        "unsafe_recommended_output_name",
        "source_dxf_sha256_mismatch",
        "source_dxf_size_mismatch",
        "candidate_png_sha256_mismatch",
        "candidate_png_size_mismatch",
        "invalid_requested_expected_size",
        "duplicate_recommended_output_name",
        "source_dxf_missing",
        "candidate_missing",
    } <= issue_codes
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert "reference_request_validation_markdown" in {item["kind"] for item in artifact_index["artifacts"]}


def test_batch_generator_fulfills_reference_request(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "reason": "recapture-required",
        "case_count": 1,
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "recommended_output_name": "G11_autocad_model_extents.png",
            "requested_capture_method": "plot-export",
            "requested_view_contract": "model-extents",
            "requested_expected_size": {"width": 1600, "height": 1131},
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{
        "id": "G11",
        "ours": "ours/G11.png",
        "diagnostics": {"window_source": "content_bbox"},
    }]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 0

    manifest = json.loads((out / "acad_manifest.json").read_text(encoding="utf-8"))
    generated_candidates = json.loads((out / "candidate_cases.json").read_text(encoding="utf-8"))
    case = manifest["cases"][0]
    assert case["id"] == "G11"
    assert case["acad_png"].endswith("G11_autocad_model_extents.png")
    assert case["capture_method"] == "plot-export"
    assert case["view_contract"] == "model-extents"
    assert case["expected_size"] == {"width": 1600, "height": 1131}
    assert generated_candidates[0]["ours"].endswith("ours/G11.png")
    assert generated_candidates[0]["diagnostics"] == {"window_source": "content_bbox"}
    intake = json.loads((out / "reference_intake.json").read_text(encoding="utf-8"))
    assert intake["schema"] == "vemcad.acad_reference_intake/v1"
    assert intake["status"] == "pass"
    assert intake["warning_count"] == 0
    assert intake["boundary"]["autocad_equivalence_claim"] is False
    assert intake["cases"][0]["inspection"]["sha256"] == _sha256(
        tmp_path / "returned" / "G11_autocad_model_extents.png"
    )
    intake_md = (out / "reference_intake.md").read_text(encoding="utf-8")
    assert "AutoCAD Reference Intake Preflight" in intake_md
    assert "G11_autocad_model_extents.png" in intake_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "acad_manifest",
        "candidate_cases",
        "reference_intake_json",
        "reference_intake_markdown",
    }

    dry_run = tmp_path / "dry-run-request"
    assert harness.main([
        "--manifest", str(out / "acad_manifest.json"),
        "--out-dir", str(dry_run),
        "--dry-run",
    ]) == 0


def test_batch_generator_blocks_request_when_source_dxf_provenance_drifts(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "source_dxf_sha256": "0" * 64,
            "recommended_output_name": "G11_autocad_model_extents.png",
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{"id": "G11", "ours": "ours/G11.png"}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 2

    assert not (out / "acad_manifest.json").exists()
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert "reference_intake_json" in {item["kind"] for item in artifact_index["artifacts"]}


def test_batch_generator_blocks_request_when_candidate_png_provenance_drifts(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "candidate_png_sha256": "f" * 64,
            "recommended_output_name": "G11_autocad_model_extents.png",
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{"id": "G11", "ours": "ours/G11.png"}]), encoding="utf-8")

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(tmp_path / "out"),
    ]) == 2


def test_batch_generator_blocks_returned_png_size_mismatch_when_request_declares_size(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1200, 900))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "recommended_output_name": "G11_autocad_model_extents.png",
            "requested_expected_size": {"width": 1600, "height": 1131},
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{"id": "G11", "ours": "ours/G11.png"}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 2

    manifest = json.loads((out / "acad_manifest.json").read_text(encoding="utf-8"))
    assert manifest["cases"][0]["expected_size"] == {"width": 1600, "height": 1131}
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert {item["kind"] for item in artifact_index["artifacts"]} >= {
        "acad_manifest",
        "candidate_cases",
        "reference_intake_json",
        "reference_intake_markdown",
    }


def test_batch_generator_blocks_request_without_returned_png(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "recommended_output_name": "G11_autocad_model_extents.png",
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{"id": "G11", "ours": "ours/G11.png"}]), encoding="utf-8")

    out = tmp_path / "out"

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 2
    missing = json.loads((out / "missing_references.json").read_text(encoding="utf-8"))
    assert missing["schema"] == "vemcad.acad_reference_missing/v1"
    assert missing["missing_count"] == 1
    assert missing["missing"][0]["id"] == "G11"
    assert missing["missing"][0]["recommended_output_name"] == "G11_autocad_model_extents.png"
    missing_md = (out / "missing_references.md").read_text(encoding="utf-8")
    assert "Missing AutoCAD Reference PNGs" in missing_md
    assert "G11_autocad_model_extents.png" in missing_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "missing_references_json",
        "missing_references_markdown",
    }


def test_batch_generator_clears_stale_missing_reports_on_successful_rerun(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "recommended_output_name": "G11_autocad_model_extents.png",
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{"id": "G11", "ours": "ours/G11.png"}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 2
    assert (out / "missing_references.md").is_file()

    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131))
    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 0

    assert not (out / "missing_references.json").exists()
    assert not (out / "missing_references.md").exists()
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert "missing_references_markdown" not in {item["kind"] for item in artifact_index["artifacts"]}


def test_batch_generator_fulfills_subset_of_reference_request(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _dxf(tmp_path / "dxf" / "G04.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    _png(tmp_path / "ours" / "G04.png", (760, 570))
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [
            {
                "id": "G11",
                "drawing_id": "G11/B11",
                "source_dxf": "dxf/G11.dxf",
                "recommended_output_name": "G11_autocad_model_extents.png",
            },
            {
                "id": "G04",
                "drawing_id": "G04/B04",
                "source_dxf": "dxf/G04.dxf",
                "recommended_output_name": "G04_autocad_model_extents.png",
            },
        ],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([
        {"id": "G11", "ours": "ours/G11.png"},
        {"id": "G04", "ours": "ours/G04.png"},
    ]), encoding="utf-8")

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--case-id", "G11",
        "--out-dir", str(tmp_path / "subset"),
    ]) == 0
    manifest = json.loads((tmp_path / "subset" / "acad_manifest.json").read_text(encoding="utf-8"))
    generated_candidates = json.loads((tmp_path / "subset" / "candidate_cases.json").read_text(encoding="utf-8"))
    assert [case["id"] for case in manifest["cases"]] == ["G11"]
    assert [case["id"] for case in generated_candidates] == ["G11"]

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(tmp_path / "all"),
    ]) == 2
    missing = json.loads((tmp_path / "all" / "missing_references.json").read_text(encoding="utf-8"))
    assert missing["missing_count"] == 1
    assert missing["missing"][0]["id"] == "G04"


def test_batch_generator_intake_warns_on_low_resolution_or_non_white_png(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (900, 600), color=(12, 12, 12))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "recommended_output_name": "G11_autocad_model_extents.png",
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{"id": "G11", "ours": "ours/G11.png"}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 0

    intake = json.loads((out / "reference_intake.json").read_text(encoding="utf-8"))
    assert intake["status"] == "review"
    assert intake["warning_count"] == 2
    issue_codes = {issue["code"] for issue in intake["cases"][0]["issues"]}
    assert issue_codes == {"long_edge_below_requested", "corner_background_not_white"}
    intake_md = (out / "reference_intake.md").read_text(encoding="utf-8")
    assert "warning:long_edge_below_requested" in intake_md
    assert "warning:corner_background_not_white" in intake_md


def test_batch_generator_intake_warns_on_candidate_returned_ink_aspect_divergence(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (1600, 1131), box=[720, 100, 880, 1030])
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131), box=[100, 500, 1500, 650])
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "recommended_output_name": "G11_autocad_model_extents.png",
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{"id": "G11", "ours": "ours/G11.png"}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 0

    intake = json.loads((out / "reference_intake.json").read_text(encoding="utf-8"))
    assert intake["status"] == "review"
    assert intake["warning_count"] == 1
    row = intake["cases"][0]
    assert row["issues"][0]["code"] == "ink_bbox_aspect_divergence"
    advisory = row["inspection"]["identity_advisory"]
    assert advisory["diagnostic_only"] is True
    assert advisory["ink_bbox_aspect_delta"] > 0.25
