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


def _route_summary(out: Path) -> dict:
    assert (out / "route_summary.md").is_file()
    return json.loads((out / "route_summary.json").read_text(encoding="utf-8"))


def test_batch_generator_writes_manifest_and_candidates(tmp_path, capsys):
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
    stdout = capsys.readouterr().out

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
    assert artifact_index["boundary"] == {
        "renders_dxf": False,
        "compares_renders": False,
        "changes_x3_scoring": False,
        "changes_renderer": False,
        "requires_viewspace_match": False,
        "autocad_equivalence_claim": False,
    }
    assert artifact_index["stage"] == "manifest"
    assert artifact_index["status"] == "pass"
    assert artifact_index["case_count"] == 2
    assert artifact_index["error_count"] == 0
    assert artifact_index["warning_count"] == 0
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "acad_manifest",
        "candidate_cases",
        "route_summary_json",
        "route_summary_markdown",
    }
    route = _route_summary(out)
    assert route["kind"] == "batch"
    assert route["recommended_next_action"]["code"] == "continue-to-request-run"
    assert "route summary" in stdout
    assert "recommended next action: continue-to-request-run" in stdout
    assert "recommended next action domain: continue" in stdout

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


def test_batch_generator_validates_reference_request_package_before_fulfilment(tmp_path, capsys):
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
    stdout = capsys.readouterr().out

    validation = json.loads((out / "reference_request_validation.json").read_text(encoding="utf-8"))
    assert validation["schema"] == "vemcad.acad_reference_request_validation/v1"
    assert validation["status"] == "pass"
    assert validation["error_count"] == 0
    assert validation["boundary"]["requires_returned_autocad_png"] is False
    assert validation["boundary"]["autocad_equivalence_claim"] is False
    row = validation["cases"][0]
    assert row["source_dxf_provenance"]["sha256"] == _sha256(source)
    assert row["candidate_png_provenance"]["sha256"] == _sha256(ours)
    assert row["requested_expected_size"] == "1600x1131"
    validation_md = (out / "reference_request_validation.md").read_text(encoding="utf-8")
    assert "AutoCAD Reference Request Validation" in validation_md
    assert "G11_autocad_model_extents.png" in validation_md
    assert "`1600x1131`" in validation_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["stage"] == "request_validation"
    assert artifact_index["status"] == "pass"
    assert artifact_index["case_count"] == 1
    assert artifact_index["error_count"] == 0
    assert artifact_index["warning_count"] == 0
    assert artifact_index["reference_request_validation_status"] == "pass"
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "reference_request_validation_json",
        "reference_request_validation_markdown",
        "route_summary_json",
        "route_summary_markdown",
    }
    route = _route_summary(out)
    assert route["kind"] == "batch"
    assert route["recommended_next_action"]["code"] == "continue-to-request-run"
    assert "route summary" in stdout
    assert "recommended next action: continue-to-request-run" in stdout
    assert "recommended next action domain: continue" in stdout


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
                "requested_capture_method": "screenshot",
                "requested_view_contract": "paper-layout",
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
        "diagnostic_requested_capture_method",
        "unmatched_requested_view_contract",
        "duplicate_recommended_output_name",
        "source_dxf_missing",
        "candidate_missing",
    } <= issue_codes
    assert validation["cases"][0]["requested_expected_size"] == "0xbad"
    validation_md = (out / "reference_request_validation.md").read_text(encoding="utf-8")
    assert "`0xbad`" in validation_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["stage"] == "request_validation"
    assert artifact_index["status"] == "blocked"
    assert artifact_index["error_count"] >= 1
    assert artifact_index["reference_request_validation_status"] == "blocked"
    assert artifact_index["reference_request_validation_issue_code_counts"] == {
        "candidate_missing": 1,
        "candidate_png_sha256_mismatch": 1,
        "candidate_png_size_mismatch": 1,
        "duplicate_candidate_id": 1,
        "duplicate_recommended_output_name": 1,
        "diagnostic_requested_capture_method": 1,
        "invalid_requested_expected_size": 1,
        "source_dxf_missing": 1,
        "source_dxf_sha256_mismatch": 1,
        "source_dxf_size_mismatch": 1,
        "unmatched_requested_view_contract": 1,
        "unsafe_recommended_output_name": 2,
    }
    assert "reference_request_validation_markdown" in {item["kind"] for item in artifact_index["artifacts"]}


def test_batch_generator_fulfills_reference_request(tmp_path):
    source = Path(_dxf(tmp_path / "dxf" / "G11.dxf"))
    _png(tmp_path / "ours" / "G11.png", (760, 570), box=[20, 15, 740, 555])
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131), box=[40, 30, 1560, 1100])
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "reason": "recapture-required",
        "case_count": 1,
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "source_dxf_sha256": _sha256(source),
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
    assert artifact_index["boundary"]["compares_renders"] is False
    assert artifact_index["boundary"]["autocad_equivalence_claim"] is False
    assert artifact_index["stage"] == "reference_intake"
    assert artifact_index["status"] == "pass"
    assert artifact_index["case_count"] == 1
    assert artifact_index["error_count"] == 0
    assert artifact_index["warning_count"] == 0
    assert artifact_index["reference_request_validation_status"] == "pass"
    assert artifact_index["reference_intake_status"] == "pass"
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "acad_manifest",
        "candidate_cases",
        "reference_intake_json",
        "reference_intake_markdown",
        "reference_request_validation_json",
        "reference_request_validation_markdown",
        "route_summary_json",
        "route_summary_markdown",
    }
    route = _route_summary(out)
    assert route["kind"] == "batch"
    assert route["recommended_next_action"]["code"] == "continue-to-request-run"

    dry_run = tmp_path / "dry-run-request"
    assert harness.main([
        "--manifest", str(out / "acad_manifest.json"),
        "--out-dir", str(dry_run),
        "--dry-run",
    ]) == 0


def test_batch_generator_validation_blocks_unmatched_capture_contract_before_capture(tmp_path):
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
            "requested_capture_method": "viewport-capture",
            "requested_view_contract": "paper-layout",
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
    ]) == 2

    validation = json.loads((out / "reference_request_validation.json").read_text(encoding="utf-8"))
    assert validation["status"] == "blocked"
    issue_codes = {issue["code"] for issue in validation["issues"]}
    assert issue_codes == {
        "diagnostic_requested_capture_method",
        "unmatched_requested_view_contract",
    }
    row = validation["cases"][0]
    assert row["requested_capture_method"] == "viewport-capture"
    assert row["requested_view_contract"] == "paper-layout"
    validation_md = (out / "reference_request_validation.md").read_text(encoding="utf-8")
    assert "`viewport-capture`" in validation_md
    assert "`paper-layout`" in validation_md


def test_batch_generator_blocks_request_when_source_dxf_provenance_drifts(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570), box=[20, 15, 740, 555])
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131), box=[40, 30, 1560, 1100])
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
    validation = json.loads((out / "reference_request_validation.json").read_text(encoding="utf-8"))
    assert validation["status"] == "blocked"
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["stage"] == "request_validation"
    assert artifact_index["status"] == "blocked"
    assert artifact_index["reference_request_validation_status"] == "blocked"
    assert "reference_request_validation_json" in {item["kind"] for item in artifact_index["artifacts"]}


def test_batch_generator_blocks_request_when_candidate_png_provenance_drifts(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570), box=[20, 15, 740, 555])
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131), box=[40, 30, 1560, 1100])
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
    assert artifact_index["stage"] == "reference_intake"
    assert artifact_index["status"] == "blocked"
    assert artifact_index["batch_validation_status"] == "blocked"
    assert artifact_index["reference_intake_status"] == "review"
    assert {item["kind"] for item in artifact_index["artifacts"]} >= {
        "acad_manifest",
        "candidate_cases",
        "reference_intake_json",
        "reference_intake_markdown",
        "reference_request_validation_json",
        "reference_request_validation_markdown",
    }


def test_batch_generator_blocks_request_without_returned_png(tmp_path, capsys):
    source = Path(_dxf(tmp_path / "dxf" / "G11.dxf"))
    _png(tmp_path / "ours" / "G11.png", (760, 570))
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": "dxf/G11.dxf",
            "source_dxf_sha256": _sha256(source),
            "recommended_output_name": "G11_autocad_model_extents.png",
            "requested_capture_method": "plot-export",
            "requested_view_contract": "model-extents",
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
    stderr = capsys.readouterr().err
    missing = json.loads((out / "missing_references.json").read_text(encoding="utf-8"))
    assert missing["schema"] == "vemcad.acad_reference_missing/v1"
    assert missing["missing_count"] == 1
    assert missing["missing"][0]["id"] == "G11"
    assert missing["missing"][0]["source_dxf"].endswith("dxf/G11.dxf")
    assert missing["missing"][0]["source_dxf_sha256"] == _sha256(source)
    assert missing["missing"][0]["recommended_output_name"] == "G11_autocad_model_extents.png"
    assert missing["missing"][0]["requested_capture_method"] == "plot-export"
    assert missing["missing"][0]["requested_view_contract"] == "model-extents"
    assert missing["missing"][0]["requested_expected_size"] == "1600x1131"
    missing_md = (out / "missing_references.md").read_text(encoding="utf-8")
    assert "Missing AutoCAD Reference PNGs" in missing_md
    assert "dxf/G11.dxf" in missing_md
    assert "G11_autocad_model_extents.png" in missing_md
    assert "`plot-export`" in missing_md
    assert "`model-extents`" in missing_md
    assert "`1600x1131`" in missing_md
    assert "missing_references_tsv" in missing_md
    missing_tsv = (out / "missing_references.tsv").read_text(encoding="utf-8").splitlines()
    assert missing_tsv[0] == (
        "id\tdrawing_id\tsource_dxf\tsource_dxf_sha256\trecommended_output_name\texpected_path\t"
        "requested_capture_method\trequested_view_contract\trequested_expected_size"
    )
    assert missing_tsv[1].startswith("G11\tG11/B11\t")
    assert "dxf/G11.dxf" in missing_tsv[1]
    assert f"\t{_sha256(source)}\t" in missing_tsv[1]
    assert "\tG11_autocad_model_extents.png\t" in missing_tsv[1]
    assert missing_tsv[1].endswith("\tplot-export\tmodel-extents\t1600x1131")
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["stage"] == "missing_references"
    assert artifact_index["status"] == "blocked"
    assert artifact_index["case_count"] == 1
    assert artifact_index["missing_count"] == 1
    assert artifact_index["reference_request_validation_status"] == "pass"
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "missing_references_json",
        "missing_references_markdown",
        "missing_references_tsv",
        "reference_request_validation_json",
        "reference_request_validation_markdown",
        "route_summary_json",
        "route_summary_markdown",
    }
    route = _route_summary(out)
    assert route["kind"] == "batch"
    assert route["recommended_next_action"]["code"] == "provide-returned-autocad-pngs"
    assert "route summary" in stderr
    assert "recommended next action: provide-returned-autocad-pngs" in stderr
    assert "recommended next action domain: input" in stderr


def test_batch_generator_clears_stale_missing_reports_on_successful_rerun(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (760, 570), box=[20, 15, 740, 555])
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
    assert (out / "missing_references.tsv").is_file()

    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131), box=[40, 30, 1560, 1100])
    assert batch.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 0

    assert not (out / "missing_references.json").exists()
    assert not (out / "missing_references.md").exists()
    assert not (out / "missing_references.tsv").exists()
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["stage"] == "reference_intake"
    assert artifact_index["status"] == "pass"
    assert "missing_references_markdown" not in {item["kind"] for item in artifact_index["artifacts"]}
    assert "missing_references_tsv" not in {item["kind"] for item in artifact_index["artifacts"]}


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
    _png(tmp_path / "ours" / "G11.png", (760, 570), box=[20, 15, 740, 555])
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
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["stage"] == "reference_intake"
    assert artifact_index["status"] == "review"
    assert artifact_index["warning_count"] == 2
    assert artifact_index["reference_intake_status"] == "review"
    assert artifact_index["reference_request_validation_issue_code_counts"] == {}
    assert artifact_index["reference_intake_issue_code_counts"] == {
        "corner_background_not_white": 1,
        "long_edge_below_requested": 1,
    }
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


def test_batch_generator_intake_warns_on_blank_returned_reference(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (1600, 1131), box=[40, 30, 1560, 1100])
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131))
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
    assert row["issues"][0]["code"] == "returned_reference_blank"
    advisory = row["inspection"]["identity_advisory"]
    assert advisory["diagnostic_only"] is True
    assert advisory["returned_ink"]["status"] == "blank"
    assert advisory["candidate_ink"]["status"] == "available"
    intake_md = (out / "reference_intake.md").read_text(encoding="utf-8")
    assert "warning:returned_reference_blank" in intake_md


def test_batch_generator_intake_warns_on_blank_candidate_render(tmp_path):
    _dxf(tmp_path / "dxf" / "G11.dxf")
    _png(tmp_path / "ours" / "G11.png", (1600, 1131))
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", (1600, 1131), box=[40, 30, 1560, 1100])
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
    assert row["issues"][0]["code"] == "candidate_render_blank"
    advisory = row["inspection"]["identity_advisory"]
    assert advisory["diagnostic_only"] is True
    assert advisory["returned_ink"]["status"] == "available"
    assert advisory["candidate_ink"]["status"] == "blank"
    intake_md = (out / "reference_intake.md").read_text(encoding="utf-8")
    assert "warning:candidate_render_blank" in intake_md
