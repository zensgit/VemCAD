import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_reference_request_run as runner  # noqa: E402
import acad_artifact_route as route  # noqa: E402


REQUEST_BOUNDARY = {
    "renders_dxf": False,
    "compares_renders": False,
    "changes_x3_scoring": False,
    "changes_renderer": False,
    "requires_returned_autocad_png": True,
    "requires_viewspace_match": True,
    "autocad_equivalence_claim": False,
}


def _run_artifact_index(out: Path) -> dict:
    payload = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "vemcad.acad_reference_request_run_artifact_index/v1"
    return payload


def _run_artifact_kinds(out: Path) -> set[str]:
    payload = _run_artifact_index(out)
    return {item["kind"] for item in payload["artifacts"]}


def _unescaped_pipe_count(line: str) -> int:
    count = 0
    escaped = False
    for char in line:
        if char == "\\" and not escaped:
            escaped = True
            continue
        if char == "|" and not escaped:
            count += 1
        escaped = False
    return count


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


def _request(path: Path, *, case_id="G11", expected_size=None) -> Path:
    case = {
        "id": case_id,
        "drawing_id": f"{case_id}/B11",
        "source_dxf": "dxf/B11.dxf",
        "recommended_output_name": f"{case_id}_autocad_model_extents.png",
        "requested_capture_method": "plot-export",
        "requested_view_contract": "model-extents",
    }
    if expected_size is not None:
        case["requested_expected_size"] = {
            "width": expected_size[0],
            "height": expected_size[1],
        }
    path.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "reason": "recapture-required",
        "boundary": dict(REQUEST_BOUNDARY),
        "cases": [case],
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
        "boundary": dict(REQUEST_BOUNDARY),
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
    assert summary["source_request_boundary"] == REQUEST_BOUNDARY
    assert summary["reference_request_validation_status"] == "pass"
    assert summary["reference_request_validation_error_count"] == 0
    assert summary["reference_request_validation_warning_count"] == 0
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
    assert summary["route_count"] == 3
    assert summary["route_kind_counts"] == {
        "batch": 1,
        "compare": 1,
        "request_run": 1,
    }
    assert summary["route_status_counts"] == {"pass": 3}
    assert summary["route_recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "review-x3-pass": 2,
    }
    assert summary["route_recommended_action_domain_counts"] == {
        "continue": 1,
        "pass-review": 2,
    }
    assert summary["route_compare_case_count"] == 1
    assert summary["route_compared_count"] == 1
    assert summary["route_triage_bucket_counts"] == {"matched-pass": 1}
    assert summary["route_viewspace_status_counts"] == {"match": 1}
    assert summary["route_x3_band_counts"] == {"pass": 1}
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
    assert artifact_index["reference_request_validation_status"] == "pass"
    assert artifact_index["reference_request_validation_error_count"] == 0
    assert artifact_index["reference_request_validation_warning_count"] == 0
    assert artifact_index["source_request_boundary"] == REQUEST_BOUNDARY
    assert artifact_index["reference_intake_status"] == "pass"
    assert artifact_index["reference_intake_error_count"] == 0
    assert artifact_index["reference_intake_warning_count"] == 0
    assert artifact_index["route_count"] == 3
    assert artifact_index["route_kind_counts"] == {
        "batch": 1,
        "compare": 1,
        "request_run": 1,
    }
    assert artifact_index["route_status_counts"] == {"pass": 3}
    assert artifact_index["route_recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "review-x3-pass": 2,
    }
    assert artifact_index["route_recommended_action_domain_counts"] == {
        "continue": 1,
        "pass-review": 2,
    }
    assert artifact_index["route_compare_case_count"] == 1
    assert artifact_index["route_compared_count"] == 1
    assert artifact_index["route_triage_bucket_counts"] == {"matched-pass": 1}
    assert artifact_index["route_viewspace_status_counts"] == {"match": 1}
    assert artifact_index["route_x3_band_counts"] == {"pass": 1}
    routed_run = route.route_artifact_index(out / "artifact_index.json")
    assert routed_run["route_compare_case_count"] == 1
    assert routed_run["route_compared_count"] == 1
    assert routed_run["route_triage_bucket_counts"] == {"matched-pass": 1}
    assert routed_run["route_viewspace_status_counts"] == {"match": 1}
    assert routed_run["route_x3_band_counts"] == {"pass": 1}
    assert "recommended next action: review-x3-pass" in stdout
    assert "recommended next action domain: pass-review" in stdout
    assert "reference request validation issue codes: none" in stdout
    assert "case action domain counts: pass-review=1" in stdout
    assert "route compare cases: 1" in stdout
    assert "route compared cases: 1" in stdout
    assert "route triage buckets: matched-pass=1" in stdout
    assert "route viewspace statuses: match=1" in stdout
    assert "route x3 bands: pass=1" in stdout
    assert compare_summary["status"] == "pass"
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "recommended_next_action: `review-x3-pass`" in summary_md
    assert "recommended_next_action_domain: `pass-review`" in summary_md
    assert "reference_request_validation_warnings: `0`" in summary_md
    assert "reference_intake_errors: `0`" in summary_md
    assert "case_action_counts: `review-x3-pass=1`" in summary_md
    assert "case_action_domain_counts: `pass-review=1`" in summary_md
    assert "source_request_boundary: `autocad_equivalence_claim=False" in summary_md
    assert "requires_returned_autocad_png=True" in summary_md
    assert "route_count: `3`" in summary_md
    assert "route_kind_counts: `batch=1, compare=1, request_run=1`" in summary_md
    assert "route_status_counts: `pass=3`" in summary_md
    assert "route_recommended_action_counts: `continue-to-request-run=1, review-x3-pass=2`" in summary_md
    assert "route_recommended_action_domain_counts: `continue=1, pass-review=2`" in summary_md
    assert "route_compare_case_count: `1`" in summary_md
    assert "route_compared_count: `1`" in summary_md
    assert "route_triage_bucket_counts: `matched-pass=1`" in summary_md
    assert "route_viewspace_status_counts: `match=1`" in summary_md
    assert "route_x3_band_counts: `pass=1`" in summary_md
    assert "case actions tsv" in summary_md
    route_summary_md = (out / "route_summary.md").read_text(encoding="utf-8")
    assert "- reference_request_validation_status: `pass`" in route_summary_md
    assert "- reference_intake_status: `pass`" in route_summary_md
    case_actions_tsv = (out / "case_actions.tsv").read_text(encoding="utf-8").splitlines()
    assert case_actions_tsv[0] == (
        "id\tdrawing_id\tcode\tdomain\tsource\ttriage_bucket\t"
        "viewspace_status\tx3_band\tissue_count\trecommended_output_name\tartifact"
    )
    assert "G11\tG11/B11\treview-x3-pass\tpass-review\tcompare\tmatched-pass\tmatch\tpass\t\t\t" in case_actions_tsv[1]
    assert "route summary markdown" in summary_md
    artifact_kinds = _run_artifact_kinds(out)
    assert artifact_kinds >= {
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
    assert "compare_reference_request_json" not in artifact_kinds
    assert "compare_reference_request_markdown" not in artifact_kinds
    route_summary = json.loads((out / "route_summary.json").read_text(encoding="utf-8"))
    route_summary_md = (out / "route_summary.md").read_text(encoding="utf-8")
    request_run_route = next(item for item in route_summary["routes"] if item["kind"] == "request_run")
    assert request_run_route["route_compare_case_count"] == 1
    assert request_run_route["route_triage_bucket_counts"] == {"matched-pass": 1}
    assert "- route_compare_case_count: `1`" in route_summary_md
    assert "- route_triage_bucket_counts: `matched-pass=1`" in route_summary_md
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


def test_reference_request_run_escapes_markdown_case_action_cells(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11|ours.png", size=(1600, 1131), box=[40, 30, 1560, 1100])
    _png(
        tmp_path / "returned" / "G11|acad_model_extents.png",
        size=(1600, 1131),
        box=[40, 30, 1560, 1100],
    )
    request = tmp_path / "reference_request.json"
    request.write_text(json.dumps({
        "schema": "vemcad.acad_reference_request/v1",
        "reason": "recapture-required",
        "boundary": dict(REQUEST_BOUNDARY),
        "cases": [{
            "id": "G11",
            "drawing_id": "G11|bearing\ncap",
            "source_dxf": "dxf/B11.dxf",
            "recommended_output_name": "G11|acad_model_extents.png",
            "requested_capture_method": "plot-export",
            "requested_view_contract": "model-extents",
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidate_cases.json"
    candidates.write_text(json.dumps([{
        "id": "G11",
        "ours": "ours/G11|ours.png",
        "diagnostics": {"window_source": "content_bbox"},
    }]), encoding="utf-8")

    out = tmp_path / "run|markdown"

    assert runner.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--case-id", "G11",
        "--out-dir", str(out),
    ]) == 0

    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    row = next(line for line in summary_md.splitlines() if line.startswith("| `G11` |"))
    assert "G11\\|bearing cap" in row
    assert _unescaped_pipe_count(row) == 8
    assert "run\\|markdown" in summary_md


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
    assert summary["recommended_next_action"]["artifact"].endswith("compare/reference_request.md")
    assert summary["compare_reference_request_json"].endswith("compare/reference_request.json")
    assert summary["compare_reference_request_markdown"].endswith("compare/reference_request.md")
    assert summary["case_action_counts"] == {
        "recapture-autocad-or-provide-window": 1,
        "review-x3-pass": 1,
    }
    assert summary["case_action_domain_counts"] == {
        "input": 1,
        "pass-review": 1,
    }
    assert summary["route_count"] == 3
    assert summary["route_kind_counts"] == {
        "batch": 1,
        "compare": 1,
        "request_run": 1,
    }
    assert summary["route_status_counts"] == {
        "pass": 1,
        "viewspace_mismatch": 2,
    }
    assert summary["route_recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "recapture-autocad-or-provide-window": 2,
    }
    assert summary["route_recommended_action_domain_counts"] == {
        "continue": 1,
        "input": 2,
    }
    assert summary["route_compare_case_count"] == 2
    assert summary["route_compared_count"] == 2
    assert summary["route_triage_bucket_counts"] == {
        "matched-pass": 1,
        "recapture-required": 1,
    }
    assert summary["route_viewspace_status_counts"] == {
        "match": 1,
        "mismatch": 1,
    }
    assert summary["route_x3_band_counts"] == {"pass": 2}
    assert artifact_index["route_compare_case_count"] == 2
    assert artifact_index["route_compared_count"] == 2
    assert artifact_index["route_triage_bucket_counts"] == {
        "matched-pass": 1,
        "recapture-required": 1,
    }
    assert artifact_index["route_viewspace_status_counts"] == {
        "match": 1,
        "mismatch": 1,
    }
    assert artifact_index["route_x3_band_counts"] == {"pass": 2}
    artifact_kinds = _run_artifact_kinds(out)
    assert "compare_reference_request_json" in artifact_kinds
    assert "compare_reference_request_markdown" in artifact_kinds
    assert "case action counts: recapture-autocad-or-provide-window=1, review-x3-pass=1" in stdout
    assert "case action domain counts: input=1, pass-review=1" in stdout
    assert f"recommended next action artifact: {out / 'compare' / 'reference_request.md'}" in stdout
    assert "route compare cases: 2" in stdout
    assert "route compared cases: 2" in stdout
    assert "route triage buckets: matched-pass=1, recapture-required=1" in stdout
    assert "route viewspace statuses: match=1, mismatch=1" in stdout
    assert "route x3 bands: pass=2" in stdout
    assert artifact_index["case_actions"] == summary["case_actions"]
    assert artifact_index["case_action_counts"] == summary["case_action_counts"]
    assert artifact_index["case_action_domain_counts"] == summary["case_action_domain_counts"]
    assert [item["id"] for item in summary["case_actions"]] == ["G12", "G11"]
    assert summary["case_actions"][0]["code"] == "recapture-autocad-or-provide-window"
    assert summary["case_actions"][0]["domain"] == "input"
    assert summary["case_actions"][0]["source"] == "compare"
    assert summary["case_actions"][0]["triage_bucket"] == "recapture-required"
    assert summary["case_actions"][0]["artifact"].endswith("compare/reference_request.md")
    assert summary["case_actions"][1]["code"] == "review-x3-pass"
    assert summary["case_actions"][1]["domain"] == "pass-review"
    assert summary["case_actions"][1]["triage_bucket"] == "matched-pass"
    assert summary["case_actions"][1]["artifact"].endswith("compare/summary.md")
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert f"recommended next action artifact: `{out / 'compare' / 'reference_request.md'}`" in summary_md
    assert f"compare reference request: `{out / 'compare' / 'reference_request.md'}`" in summary_md
    assert f"compare reference request json: `{out / 'compare' / 'reference_request.json'}`" in summary_md
    assert "route_status_counts: `pass=1, viewspace_mismatch=2`" in summary_md
    assert (
        "route_recommended_action_counts: "
        "`continue-to-request-run=1, recapture-autocad-or-provide-window=2`"
    ) in summary_md
    assert "route_compare_case_count: `2`" in summary_md
    assert "route_compared_count: `2`" in summary_md
    assert "route_triage_bucket_counts: `matched-pass=1, recapture-required=1`" in summary_md
    assert "route_viewspace_status_counts: `match=1, mismatch=1`" in summary_md
    assert "route_x3_band_counts: `pass=2`" in summary_md
    assert "## Case Actions" in summary_md
    assert (
        f"| `G12` | G12/B12 | `recapture-autocad-or-provide-window` | "
        f"`input` | `compare` | `recapture-required` | `{out / 'compare' / 'reference_request.md'}` |"
    ) in summary_md
    assert (
        f"| `G11` | G11/B11 | `review-x3-pass` | "
        f"`pass-review` | `compare` | `matched-pass` | `{out / 'compare' / 'summary.md'}` |"
    ) in summary_md
    case_actions_tsv = (out / "case_actions.tsv").read_text(encoding="utf-8").splitlines()
    assert case_actions_tsv[1].startswith(
        "G12\tG12/B12\trecapture-autocad-or-provide-window\tinput\tcompare\trecapture-required\tmismatch\tpass\t"
    )
    assert case_actions_tsv[1].endswith(f"\t{out / 'compare' / 'reference_request.md'}")
    assert case_actions_tsv[2].startswith(
        "G11\tG11/B11\treview-x3-pass\tpass-review\tcompare\tmatched-pass\tmatch\tpass\t"
    )
    assert case_actions_tsv[2].endswith(f"\t{out / 'compare' / 'summary.md'}")
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
    assert summary["recommended_next_action"]["artifact"].endswith("compare/reference_request.md")
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
    assert summary["reference_intake_issue_code_counts"] == {
        "corner_background_not_white": 1,
        "long_edge_below_requested": 1,
    }
    assert summary["recommended_next_action"]["code"] == "inspect-returned-reference-warnings"
    assert summary["recommended_next_action"]["domain"] == "input-review"
    assert summary["recommended_next_action"]["artifact"].endswith("reference_intake.md")
    assert summary["case_action_domain_counts"] == {"input-review": 1}
    artifact_index = _run_artifact_index(out)
    assert artifact_index["reference_intake_issue_code_counts"] == summary["reference_intake_issue_code_counts"]
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "reference_intake_status: `review`" in summary_md
    assert "reference_intake_warnings: `2`" in summary_md
    assert "reference_intake_issue_codes: `corner_background_not_white=1, long_edge_below_requested=1`" in summary_md
    assert "recommended_next_action: `inspect-returned-reference-warnings`" in summary_md


def test_reference_request_run_routes_intake_blocked_to_fix_returned_input(tmp_path, capsys):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", size=(760, 570), box=[20, 15, 740, 555])
    _png(
        tmp_path / "returned" / "G11_autocad_model_extents.png",
        size=(1200, 900),
        box=[20, 15, 1180, 880],
    )
    request = _request(tmp_path / "reference_request.json", expected_size=(1600, 1131))
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
    assert summary["reference_request_validation_status"] == "pass"
    assert summary["reference_intake_status"] == "blocked"
    assert summary["reference_intake_error_count"] == 1
    assert summary["reference_intake_issue_code_counts"]["returned_png_size_mismatch"] == 1
    assert summary["recommended_next_action"]["code"] == "fix-returned-reference-input"
    assert summary["recommended_next_action"]["domain"] == "input"
    assert summary["recommended_next_action"]["artifact"].endswith("reference_intake.md")
    assert summary["case_action_counts"] == {"fix-returned-reference-input": 1}
    assert summary["case_action_domain_counts"] == {"input": 1}
    assert summary["case_actions"][0]["code"] == "fix-returned-reference-input"
    assert summary["case_actions"][0]["source"] == "reference_intake"
    assert artifact_index["recommended_next_action"] == summary["recommended_next_action"]
    assert artifact_index["case_actions"] == summary["case_actions"]
    assert "recommended next action: fix-returned-reference-input" in stdout
    assert "case action counts: fix-returned-reference-input=1" in stdout
    summary_md = (out / "run_summary.md").read_text(encoding="utf-8")
    assert "reference_intake_errors: `1`" in summary_md
    assert "case_action_counts: `fix-returned-reference-input=1`" in summary_md


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


def test_reference_request_run_clears_stale_compare_artifacts_on_input_blocked_rerun(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", size=(1600, 1131), box=[40, 30, 1560, 1100])
    returned = tmp_path / "returned" / "G11_autocad_model_extents.png"
    _png(returned, size=(1600, 1131), box=[40, 30, 1560, 1100])
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
    assert (out / "compare" / "summary.json").is_file()

    returned.unlink()
    assert runner.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--case-id", "G11",
        "--out-dir", str(out),
    ]) == 2

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    artifact_index = _run_artifact_index(out)
    assert summary["status"] == "input_blocked"
    assert summary["compare_summary_json"] == ""
    assert summary["compare_summary_markdown"] == ""
    assert summary["compare_artifact_index"] == ""
    assert summary["case_action_counts"] == {"provide-returned-autocad-pngs": 1}
    assert summary["case_action_domain_counts"] == {"input": 1}
    assert summary["route_count"] == 2
    assert summary["route_recommended_action_counts"] == {
        "provide-returned-autocad-pngs": 2,
    }
    assert summary["route_recommended_action_domain_counts"] == {"input": 2}
    assert artifact_index["recommended_next_action"]["code"] == "provide-returned-autocad-pngs"
    assert "compare_summary_json" not in _run_artifact_kinds(out)
    assert "compare_summary_markdown" not in _run_artifact_kinds(out)
    assert "compare_artifact_index" not in _run_artifact_kinds(out)
    assert not (out / "compare" / "summary.json").exists()
    case_actions_tsv = (out / "case_actions.tsv").read_text(encoding="utf-8")
    assert "review-x3-pass" not in case_actions_tsv


def test_reference_request_run_surfaces_request_validation_block(tmp_path, capsys):
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
    stdout = capsys.readouterr().out

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "input_blocked"
    assert summary["batch_exit_code"] == 2
    assert summary["compare_exit_code"] is None
    assert summary["reference_request_validation_status"] == "blocked"
    assert summary["reference_request_validation_error_count"] == 1
    assert summary["reference_request_validation_issue_code_counts"] == {"source_dxf_sha256_mismatch": 1}
    assert summary["reference_request_validation_markdown"].endswith("reference_request_validation.md")
    assert "reference request validation issue codes: source_dxf_sha256_mismatch=1" in stdout
    assert summary["recommended_next_action"]["code"] == "fix-request-package"
    assert summary["recommended_next_action"]["domain"] == "input"
    assert summary["recommended_next_action"]["artifact"].endswith("reference_request_validation.md")
    assert summary["case_action_domain_counts"] == {"input": 1}
    assert summary["reference_intake_status"] == ""
    artifact_index = _run_artifact_index(out)
    assert artifact_index["reference_request_validation_issue_code_counts"] == {
        "source_dxf_sha256_mismatch": 1,
    }
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


def test_reference_request_run_can_require_request_boundary(tmp_path):
    _dxf(tmp_path / "dxf" / "B11.dxf")
    _png(tmp_path / "ours" / "G11.png", box=[20, 15, 740, 555])
    _png(
        tmp_path / "returned" / "G11_autocad_model_extents.png",
        size=(1600, 1131),
        box=[40, 30, 1560, 1100],
    )
    request = _request(tmp_path / "reference_request.json")
    payload = json.loads(request.read_text(encoding="utf-8"))
    payload["boundary"]["autocad_equivalence_claim"] = True
    request.write_text(json.dumps(payload), encoding="utf-8")
    candidates = _candidates(tmp_path / "candidate_cases.json")
    out = tmp_path / "run"

    assert runner.main([
        "--from-request", str(request),
        "--candidate-cases", str(candidates),
        "--reference-dir", str(tmp_path / "returned"),
        "--require-request-boundary", "autocad_equivalence_claim=false",
        "--out-dir", str(out),
    ]) == 2

    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "input_blocked"
    assert summary["reference_request_validation_status"] == "blocked"
    assert summary["reference_request_validation_issue_code_counts"] == {
        "request_boundary_mismatch": 1,
    }
    assert summary["recommended_next_action"]["code"] == "fix-request-package"
    assert summary["source_request_boundary"]["autocad_equivalence_claim"] is True
    artifact_index = _run_artifact_index(out)
    assert artifact_index["reference_request_validation_issue_code_counts"] == {
        "request_boundary_mismatch": 1,
    }
    assert not (out / "compare" / "summary.json").exists()
