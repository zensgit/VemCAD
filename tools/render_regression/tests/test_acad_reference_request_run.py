import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_reference_request_run as runner  # noqa: E402


def _run_artifact_index(out: Path) -> dict:
    payload = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "vemcad.acad_reference_request_run_artifact_index/v1"
    return payload


def _run_artifact_kinds(out: Path) -> set[str]:
    payload = _run_artifact_index(out)
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


def _batch_request(path: Path) -> Path:
    path.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "reason": "recapture-required",
        "cases": [
            {
                "id": "G11",
                "drawing_id": "G11/B11",
                "source_dxf": "dxf/B11.dxf",
                "recommended_output_name": "G11_autocad_model_extents.png",
                "requested_capture_method": "plot-export",
                "requested_view_contract": "model-extents",
            },
            {
                "id": "G12",
                "drawing_id": "G12/B12",
                "source_dxf": "dxf/B12.dxf",
                "recommended_output_name": "G12_autocad_model_extents.png",
                "requested_capture_method": "plot-export",
                "requested_view_contract": "model-extents",
            },
        ],
    }), encoding="utf-8")
    return path


def _batch_candidates(path: Path) -> Path:
    path.write_text(json.dumps([
        {
            "id": "G11",
            "ours": "ours/G11.png",
            "diagnostics": {"window_source": "content_bbox"},
        },
        {
            "id": "G12",
            "ours": "ours/G12.png",
            "diagnostics": {"window_source": "content_bbox"},
        },
    ]), encoding="utf-8")
    return path


def test_reference_request_run_fulfills_and_compares_match(tmp_path, capsys):
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
    stdout = capsys.readouterr().out

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    compare_summary = json.loads((out / "compare" / "summary.json").read_text(encoding="utf-8"))
    artifact_index = _run_artifact_index(out)
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
    assert summary["route_summary_json"].endswith("route_summary.json")
    assert summary["route_summary_markdown"].endswith("route_summary.md")
    assert summary["case_actions_tsv"].endswith("case_actions.tsv")
    assert summary["recommended_next_action"]["code"] == "review-x3-pass"
    assert summary["recommended_next_action"]["domain"] == "pass-review"
    assert summary["recommended_next_action"]["artifact"].endswith("summary.md")
    assert summary["case_action_domain_counts"] == {"pass-review": 1}
    assert artifact_index["status"] == "pass"
    assert artifact_index["boundary"] == {
        "renders_dxf": False,
        "compares_renders": True,
        "changes_x3_scoring": False,
        "changes_renderer": False,
        "requires_viewspace_match": True,
        "autocad_equivalence_claim": False,
    }
    assert artifact_index["recommended_next_action"]["code"] == "review-x3-pass"
    assert artifact_index["recommended_next_action"]["domain"] == "pass-review"
    assert artifact_index["case_action_domain_counts"] == {"pass-review": 1}
    assert "recommended next action: review-x3-pass" in stdout
    assert "recommended next action domain: pass-review" in stdout
    assert "case action domain counts: pass-review=1" in stdout
    assert compare_summary["status"] == "pass"
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "recommended_next_action: `review-x3-pass`" in summary_md
    assert "recommended_next_action_domain: `pass-review`" in summary_md
    assert "case_action_domain_counts: `pass-review=1`" in summary_md
    assert "case actions tsv" in summary_md
    case_actions_tsv = (out / "case_actions.tsv").read_text(encoding="utf-8").splitlines()
    assert case_actions_tsv[0] == (
        "id\tdrawing_id\tcode\tdomain\tsource\ttriage_bucket\t"
        "viewspace_status\tx3_band\tissue_count\trecommended_output_name\tartifact"
    )
    assert "G11\tG11/B11\treview-x3-pass\tpass-review\tcompare\tmatched-pass\tmatch\tpass\t\t\t" in case_actions_tsv[1]
    assert "route summary markdown" in summary_md
    assert _run_artifact_kinds(out) >= {
        "run_summary_json",
        "run_summary_markdown",
        "case_actions_tsv",
        "route_summary_json",
        "route_summary_markdown",
        "input_artifact_index",
        "reference_request_validation_json",
        "reference_request_validation_markdown",
        "reference_intake_json",
        "reference_intake_markdown",
        "compare_summary_json",
        "compare_summary_markdown",
        "compare_artifact_index",
    }
    route_summary = json.loads((out / "route_summary.json").read_text(encoding="utf-8"))
    route_summary_md = (out / "route_summary.md").read_text(encoding="utf-8")
    assert route_summary["recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "review-x3-pass": 2,
    }
    assert route_summary["recommended_action_domain_counts"] == {
        "continue": 1,
        "pass-review": 2,
    }
    assert "AutoCAD Artifact Route Report" in route_summary_md
    assert "claim AutoCAD equivalence" in route_summary_md


def test_reference_request_run_writes_per_case_actions_for_batch(tmp_path, capsys):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _dxf(tmp_path / "dxf" / "B12.dxf")
    _png(tmp_path / "ours" / "G11.png", size=(1600, 1131), box=[40, 30, 1560, 1100])
    _png(tmp_path / "returned" / "G11_autocad_model_extents.png", size=(1600, 1131), box=[40, 30, 1560, 1100])
    _png(tmp_path / "ours" / "G12.png", size=(760, 570), box=[20, 15, 740, 555])
    _png(tmp_path / "returned" / "G12_autocad_model_extents.png", size=(1600, 1200), box=[400, 300, 1200, 900])
    request = _batch_request(tmp_path / "reference_request.json")
    candidates = _batch_candidates(tmp_path / "candidate_cases.json")
    out = tmp_path / "run"

    assert runner.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--out-dir", str(out),
    ]) == 2
    stdout = capsys.readouterr().out

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    artifact_index = _run_artifact_index(out)
    assert summary["status"] == "viewspace_mismatch"
    assert summary["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert summary["recommended_next_action"]["domain"] == "input"
    assert summary["case_action_counts"] == {
        "recapture-autocad-or-provide-window": 1,
        "review-x3-pass": 1,
    }
    assert summary["case_action_domain_counts"] == {
        "input": 1,
        "pass-review": 1,
    }
    assert "case action counts: recapture-autocad-or-provide-window=1, review-x3-pass=1" in stdout
    assert "case action domain counts: input=1, pass-review=1" in stdout
    assert artifact_index["case_actions"] == summary["case_actions"]
    assert artifact_index["case_action_counts"] == summary["case_action_counts"]
    assert artifact_index["case_action_domain_counts"] == summary["case_action_domain_counts"]
    assert [item["id"] for item in summary["case_actions"]] == ["G12", "G11"]
    assert summary["case_actions"][0]["code"] == "recapture-autocad-or-provide-window"
    assert summary["case_actions"][0]["domain"] == "input"
    assert summary["case_actions"][0]["source"] == "compare"
    assert summary["case_actions"][0]["triage_bucket"] == "recapture-required"
    assert summary["case_actions"][1]["code"] == "review-x3-pass"
    assert summary["case_actions"][1]["domain"] == "pass-review"
    assert summary["case_actions"][1]["triage_bucket"] == "matched-pass"
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "## Case Actions" in summary_md
    assert "| `G12` | G12/B12 | `recapture-autocad-or-provide-window`" in summary_md
    assert "| `G11` | G11/B11 | `review-x3-pass`" in summary_md
    case_actions_tsv = (out / "case_actions.tsv").read_text(encoding="utf-8").splitlines()
    assert case_actions_tsv[1].startswith(
        "G12\tG12/B12\trecapture-autocad-or-provide-window\tinput\tcompare\trecapture-required\tmismatch\tpass\t"
    )
    assert case_actions_tsv[2].startswith(
        "G11\tG11/B11\treview-x3-pass\tpass-review\tcompare\tmatched-pass\tmatch\tpass\t"
    )
    route_summary = json.loads((out / "route_summary.json").read_text(encoding="utf-8"))
    assert route_summary["recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "recapture-autocad-or-provide-window": 2,
    }
    assert route_summary["recommended_action_domain_counts"] == {
        "continue": 1,
        "input": 2,
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
    assert summary["recommended_next_action"]["domain"] == "input"
    assert "do not tune the renderer" in summary["recommended_next_action"]["message"]
    assert summary["case_action_domain_counts"] == {"input": 1}
    assert compare_summary["status"] == "viewspace_mismatch"
    route_summary_md = (out / "route_summary.md").read_text(encoding="utf-8")
    assert "recapture-autocad-or-provide-window=2" in route_summary_md
    assert "recommended_action_domain_counts: `continue=1, input=2`" in route_summary_md


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
    assert summary["recommended_next_action"]["domain"] == "input-review"
    assert summary["recommended_next_action"]["artifact"].endswith("reference_intake.md")
    assert summary["case_action_domain_counts"] == {"input-review": 1}
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "reference_intake_status: `review`" in summary_md
    assert "reference_intake_warnings: `2`" in summary_md
    assert "recommended_next_action: `inspect-returned-reference-warnings`" in summary_md


def test_reference_request_run_stops_on_missing_reference(tmp_path, capsys):
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
    stdout = capsys.readouterr().out

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    artifact_index = _run_artifact_index(out)
    assert summary["status"] == "input_blocked"
    assert summary["batch_exit_code"] == 2
    assert summary["compare_exit_code"] is None
    assert summary["reference_request_validation_status"] == "pass"
    assert summary["missing_references_markdown"].endswith("missing_references.md")
    assert summary["missing_references_tsv"].endswith("missing_references.tsv")
    assert summary["reference_intake_status"] == ""
    assert summary["reference_intake_warning_count"] is None
    assert summary["compare_summary_markdown"] == ""
    assert summary["recommended_next_action"]["code"] == "provide-returned-autocad-pngs"
    assert summary["recommended_next_action"]["domain"] == "input"
    assert summary["recommended_next_action"]["artifact"].endswith("missing_references.md")
    assert summary["case_action_domain_counts"] == {"input": 1}
    assert artifact_index["status"] == "input_blocked"
    assert artifact_index["boundary"]["compares_renders"] is False
    assert artifact_index["boundary"]["autocad_equivalence_claim"] is False
    assert artifact_index["recommended_next_action"]["code"] == "provide-returned-autocad-pngs"
    assert artifact_index["recommended_next_action"]["domain"] == "input"
    assert artifact_index["case_actions"] == summary["case_actions"]
    assert artifact_index["case_action_counts"] == summary["case_action_counts"]
    assert artifact_index["case_action_domain_counts"] == summary["case_action_domain_counts"]
    assert "recommended next action: provide-returned-autocad-pngs" in stdout
    assert "recommended next action domain: input" in stdout
    assert "case action counts: provide-returned-autocad-pngs=1" in stdout
    assert "case action domain counts: input=1" in stdout
    assert not (out / "compare" / "summary.json").exists()
    assert _run_artifact_kinds(out) >= {
        "run_summary_json",
        "run_summary_markdown",
        "case_actions_tsv",
        "route_summary_json",
        "route_summary_markdown",
        "input_artifact_index",
        "reference_request_validation_json",
        "reference_request_validation_markdown",
        "missing_references_json",
        "missing_references_markdown",
        "missing_references_tsv",
    }
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "missing references tsv" in summary_md
    assert "missing_references.tsv" in summary_md
    assert "compare_summary_json" not in _run_artifact_kinds(out)
    route_summary = json.loads((out / "route_summary.json").read_text(encoding="utf-8"))
    assert route_summary["recommended_action_counts"] == {
        "provide-returned-autocad-pngs": 2,
    }
    assert route_summary["recommended_action_domain_counts"] == {"input": 2}
    case_actions_tsv = (out / "case_actions.tsv").read_text(encoding="utf-8")
    assert "G11\tG11/B11\tprovide-returned-autocad-pngs\tinput\tmissing_references" in case_actions_tsv


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
    assert summary["recommended_next_action"]["domain"] == "input"
    assert summary["recommended_next_action"]["artifact"].endswith("reference_request_validation.md")
    assert summary["case_action_domain_counts"] == {"input": 1}
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
