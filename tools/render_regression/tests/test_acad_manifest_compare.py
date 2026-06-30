import json
import hashlib
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_reference_manifest as arm  # noqa: E402
import acad_manifest_compare as harness  # noqa: E402


def _png(path: Path, size=(760, 570), box=None) -> str:
    image = Image.new("RGB", size, (255, 255, 255))
    if box is not None:
        draw = ImageDraw.Draw(image)
        draw.rectangle(box, outline=(0, 0, 0), width=3)
    image.save(path)
    return str(path)


def _dxf(path: Path) -> str:
    path.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    return str(path)


def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def _markdown_block_after(markdown: str, marker: str) -> str:
    start = markdown.index(marker)
    end = markdown.index("```", start)
    return markdown[start:end]


def _readme_route_example_block() -> str:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    return _markdown_block_after(
        readme,
        "python3 tools/render_regression/acad_artifact_route.py <run-dir> \\",
    )


def _readme_request_run_example_block() -> str:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    return _markdown_block_after(
        readme,
        "python3 tools/render_regression/acad_reference_request_run.py \\",
    )


def _manifest(
    path: Path,
    *,
    acad: str,
    dxf: str,
    expected_size=(760, 570),
    capture_method="plot-export",
    view_contract="model-extents",
) -> Path:
    path.write_text(json.dumps({
        "schema": arm.SCHEMA,
        "cases": [{
            "id": "G11",
            "drawing_id": "G11/B11",
            "source_dxf": dxf,
            "acad_png": acad,
            "capture_method": capture_method,
            "view_contract": view_contract,
            "expected_size": [expected_size[0], expected_size[1]],
        }],
    }), encoding="utf-8")
    return path


def test_readme_recapture_route_example_documents_handoff_guards():
    block = _readme_route_example_block()
    for expected in [
        "--require-source-boundary autocad_equivalence_claim=false",
        "--require-request-boundary autocad_equivalence_claim=false",
        "--require-request-boundary requires_returned_autocad_png=true",
        "--require-request-boundary requires_viewspace_match=true",
        "--forbid-action-domain input-review",
        "--require-kind batch",
        "--require-kind compare",
        "--require-kind request_run",
        "--require-artifact-kind reference_request_validation_tsv",
        "--require-artifact-kind reference_intake_tsv",
        "--require-artifact-kind case_actions_tsv",
        "--require-artifact-kind summary_tsv",
        "--require-route-count 3",
        "--require-action-artifact-exists",
    ]:
        assert expected in block


def test_readme_recapture_request_run_example_documents_input_review_guard():
    block = _readme_request_run_example_block()
    for expected in [
        "--require-request-boundary autocad_equivalence_claim=false",
        "--require-request-boundary requires_returned_autocad_png=true",
        "--require-request-boundary requires_viewspace_match=true",
        "--fail-on-input-review",
    ]:
        assert expected in block


def test_reference_request_prefers_manifest_expected_size_over_current_png(tmp_path):
    acad = _png(tmp_path / "stale-current-acad.png", size=(640, 480), box=[20, 15, 620, 460])
    ours = _png(tmp_path / "ours.png", size=(800, 600), box=[40, 30, 760, 570])
    dxf = _dxf(tmp_path / "B11.dxf")
    out = tmp_path / "out"
    out.mkdir()

    harness._write_reference_request(out, [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": acad,
        "ours": ours,
        "expected_size": {"width": 800, "height": 600},
        "viewspace_status": "mismatch",
        "x3_summary": {"band": "fallback", "ink_iou": 0.5},
    }])

    request = json.loads((out / "reference_request.json").read_text(encoding="utf-8"))
    assert request["cases"][0]["requested_expected_size"] == {"width": 800, "height": 600}
    request_md = (out / "reference_request.md").read_text(encoding="utf-8")
    assert "`800x600`" in request_md
    assert "`640x480`" not in request_md


def _candidates(path: Path, ours: str, **extra) -> Path:
    payload = [{"id": "G11", "ours": ours, **extra}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _render_report(path: Path) -> str:
    path.write_text(json.dumps({
        "schema": "vemcad.render_report",
        "schema_version": "0.1",
        "view": {
            "viewport_w": 760,
            "viewport_h": 570,
            "scale": 1,
        },
        "text_placement": {
            "schema": "vemcad.render_text_placement",
            "schema_version": "0.3",
            "records": [{
                "entity_id": "T1",
                "source_type": "TEXT",
                "semantic_class": "text",
                "text_kind": "text",
                "resolved_family": "Noto Serif CJK SC",
                "target_px": 12,
                "block_height_px": 12,
                "max_line_width_px": 64,
                "screen_x": 100,
                "screen_y": 120,
                "rotation_deg": 15,
                "width_factor": 1,
            }],
        },
    }), encoding="utf-8")
    return str(path)


def test_dry_run_validates_manifest_without_candidate_png(tmp_path):
    acad = _png(tmp_path / "acad.png", box=[20, 15, 740, 555])
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", acad=acad, dxf=dxf)
    out = tmp_path / "out"

    rc = harness.main(["--manifest", str(manifest), "--out-dir", str(out), "--dry-run"])

    assert rc == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "ready"
    assert summary["dry_run"] is True
    assert summary["compared_count"] == 0
    assert summary["boundary"]["renders_dxf"] is False


def test_manifest_harness_clears_stale_compare_artifacts_on_dry_run_rerun(tmp_path):
    acad = _png(tmp_path / "acad.png", box=[20, 15, 740, 555])
    ours = _png(tmp_path / "ours.png", box=[20, 15, 740, 555])
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", acad=acad, dxf=dxf)
    candidates = _candidates(tmp_path / "candidates.json", ours)
    out = tmp_path / "out"

    assert harness.main([
        "--manifest", str(manifest),
        "--candidate-cases", str(candidates),
        "--out-dir", str(out),
    ]) == 0
    assert (out / "summary.tsv").is_file()
    assert (out / "contact_sheet.png").is_file()
    assert any((out / "overlays").glob("*"))
    assert any((out / "viewspace").glob("*"))

    assert harness.main(["--manifest", str(manifest), "--out-dir", str(out), "--dry-run"]) == 0

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert summary["status"] == "ready"
    assert summary["dry_run"] is True
    assert summary["compared_count"] == 0
    artifact_kinds = {item["kind"] for item in artifact_index["artifacts"]}
    assert artifact_kinds == {
        "summary_json",
        "summary_markdown",
        "route_summary_json",
        "route_summary_markdown",
        "autocad_reference",
    }
    assert artifact_index["boundary"]["compares_renders"] is False
    assert artifact_index["compared_count"] == 0
    assert "summary_tsv" not in artifact_kinds
    assert "contact_sheet" not in artifact_kinds
    assert "vemcad_candidate" not in artifact_kinds
    assert "x3_overlay" not in artifact_kinds
    assert "viewspace_report" not in artifact_kinds
    assert not (out / "summary.tsv").exists()
    assert not (out / "contact_sheet.png").exists()
    assert not (out / "overlays").exists()
    assert not (out / "viewspace").exists()
    assert not (out / "reference_request.json").exists()
    assert not (out / "reference_request.md").exists()


def test_manifest_harness_runs_compare_and_records_match(tmp_path, capsys):
    acad = _png(tmp_path / "acad.png", box=[20, 15, 740, 555])
    ours = _png(tmp_path / "ours.png", box=[20, 15, 740, 555])
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", acad=acad, dxf=dxf)
    candidates = _candidates(
        tmp_path / "candidates.json",
        ours,
        render_image_digest="sha256:test",
        diagnostics={"X-Diff-Window-Source": "content_bbox"},
    )
    out = tmp_path / "out"

    rc = harness.main([
        "--manifest", str(manifest),
        "--candidate-cases", str(candidates),
        "--out-dir", str(out),
    ])
    stdout = capsys.readouterr().out

    assert rc == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = summary["rows"][0]
    assert summary["status"] == "pass"
    assert row["viewspace_status"] == "match"
    assert row["x3_summary"]["band"] == "pass"
    assert row["render_image_digest"] == "sha256:test"
    assert row["diagnostics"]["X-Diff-Window-Source"] == "content_bbox"
    assert row["triage_rank"] == 1
    assert row["triage_bucket"] == "matched-pass"
    assert row["recommended_action_domain"] == "pass-review"
    assert summary["recommended_action_domain_counts"] == {"pass-review": 1}
    assert Path(row["viewspace_report"]).is_file()
    assert Path(row["overlay"]).is_file()
    assert (out / "summary.tsv").is_file()
    tsv_lines = (out / "summary.tsv").read_text(encoding="utf-8").splitlines()
    assert "triage_rank\ttriage_bucket\trecommended_action_domain" in tsv_lines[0]
    assert "\t1\tmatched-pass\tpass-review\t760x570\t" in tsv_lines[1]
    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    assert "AutoCAD Manifest Compare Summary" in summary_md
    assert "status: `pass`" in summary_md
    assert "autocad_equivalence_claim: `False`" in summary_md
    assert "| `G11` | G11/B11 | `760x570` | `match` | `pass` |" in summary_md
    assert "`pass-review`" in summary_md
    assert "viewspace_mismatch" in summary_md
    assert "## Triage Priority" in summary_md
    assert "| 1 | `G11` | `matched-pass` | `match` | `pass` |" in summary_md
    assert (out / "contact_sheet.png").stat().st_size > 1000
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["schema"] == "vemcad.acad_manifest_compare_artifact_index/v1"
    assert artifact_index["boundary"] == {
        "renders_dxf": False,
        "compares_renders": True,
        "changes_x3_scoring": False,
        "changes_renderer": False,
        "requires_viewspace_match": True,
        "autocad_equivalence_claim": False,
    }
    assert artifact_index["status"] == "pass"
    assert artifact_index["case_count"] == 1
    assert artifact_index["compared_count"] == 1
    assert artifact_index["issue_count"] == 0
    assert artifact_index["triage_bucket_counts"] == {"matched-pass": 1}
    assert artifact_index["recommended_action_domain_counts"] == {"pass-review": 1}
    assert artifact_index["viewspace_status_counts"] == {"match": 1}
    assert artifact_index["x3_band_counts"] == {"pass": 1}
    assert {item["kind"] for item in artifact_index["artifacts"]} >= {
        "summary_json",
        "summary_markdown",
        "route_summary_json",
        "route_summary_markdown",
        "summary_tsv",
        "contact_sheet",
        "autocad_reference",
        "vemcad_candidate",
        "x3_overlay",
        "viewspace_report",
    }
    route_summary = json.loads((out / "route_summary.json").read_text(encoding="utf-8"))
    route_summary_md = (out / "route_summary.md").read_text(encoding="utf-8")
    assert route_summary["kind"] == "compare"
    assert route_summary["recommended_next_action"]["code"] == "review-x3-pass"
    assert "AutoCAD Artifact Route Report" in route_summary_md
    assert "claim AutoCAD equivalence" in route_summary_md
    assert "route summary" in stdout
    assert "recommended next action: review-x3-pass" in stdout
    assert "recommended next action domain: pass-review" in stdout
    assert not (out / "reference_request.json").exists()
    assert not (out / "reference_request.md").exists()


def test_manifest_harness_surfaces_text_provenance_notes(tmp_path):
    acad = _png(tmp_path / "acad.png", box=[20, 15, 740, 555])
    ours = _png(tmp_path / "ours.png", box=[20, 15, 740, 555])
    report = _render_report(tmp_path / "render_report.json")
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", acad=acad, dxf=dxf)
    candidates = _candidates(tmp_path / "candidates.json", ours, render_report=report)
    out = tmp_path / "out"

    assert harness.main([
        "--manifest", str(manifest),
        "--candidate-cases", str(candidates),
        "--out-dir", str(out),
    ]) == 0

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    text = summary["rows"][0]["text_provenance"]
    assert text["status"] == "available"
    assert text["counts"]["flag_counts"] == {}
    assert text["counts"]["note_counts"] == {"rotated_bbox_is_approximate": 1}
    assert Path(text["summary"]).is_file()
    tsv_header = (out / "summary.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert "text_flags" in tsv_header and "text_notes" in tsv_header
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert "text_provenance_summary" in {item["kind"] for item in artifact_index["artifacts"]}


def test_manifest_harness_blocks_viewspace_mismatch_without_equivalence_claim(tmp_path, capsys):
    acad = _png(tmp_path / "acad.png", size=(800, 600), box=[220, 165, 580, 435])
    ours = _png(tmp_path / "ours.png", size=(760, 570), box=[20, 15, 740, 555])
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", acad=acad, dxf=dxf, expected_size=(800, 600))
    candidates = _candidates(tmp_path / "candidates.json", ours)
    out = tmp_path / "out"

    rc = harness.main([
        "--manifest", str(manifest),
        "--candidate-cases", str(candidates),
        "--out-dir", str(out),
    ])
    stdout = capsys.readouterr().out

    assert rc == 2
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = summary["rows"][0]
    assert summary["status"] == "viewspace_mismatch"
    assert row["viewspace_status"] == "mismatch"
    assert row["compare_exit_code"] == 2
    assert row["triage_rank"] == 1
    assert row["triage_bucket"] == "recapture-required"
    assert row["recommended_action_domain"] == "input"
    assert summary["recommended_action_domain_counts"] == {"input": 1}
    assert row["recommended_action"].startswith("recapture AutoCAD")
    assert summary["boundary"]["autocad_equivalence_claim"] is False
    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    assert "status: `viewspace_mismatch`" in summary_md
    assert "It is not an AutoCAD-equivalence result" in summary_md
    assert "| `G11` | G11/B11 | `800x600` | `mismatch` | `fallback` |" in summary_md
    assert "| 1 | `G11` | `recapture-required` | `mismatch` | `fallback` |" in summary_md
    assert "`input` | recapture AutoCAD" in summary_md
    assert (out / "contact_sheet.png").stat().st_size > 1000
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["status"] == "viewspace_mismatch"
    assert artifact_index["case_count"] == 1
    assert artifact_index["compared_count"] == 1
    assert artifact_index["triage_bucket_counts"] == {"recapture-required": 1}
    assert artifact_index["recommended_action_domain_counts"] == {"input": 1}
    assert artifact_index["viewspace_status_counts"] == {"mismatch": 1}
    assert artifact_index["x3_band_counts"] == {"fallback": 1}
    route_summary = json.loads((out / "route_summary.json").read_text(encoding="utf-8"))
    route_summary_md = (out / "route_summary.md").read_text(encoding="utf-8")
    assert route_summary["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert route_summary["recommended_next_action"]["artifact"] == str(out / "reference_request.md")
    assert route_summary["action_artifact_resolved"] == str((out / "reference_request.md").resolve())
    assert route_summary["action_artifact_exists"] is True
    assert "recapture-autocad-or-provide-window" in route_summary_md
    assert f"- action_artifact: `{out / 'reference_request.md'}`" in route_summary_md
    assert "- action_artifact_exists: `True`" in route_summary_md
    assert "route summary" in stdout
    assert "recommended next action: recapture-autocad-or-provide-window" in stdout
    assert "recommended next action domain: input" in stdout
    assert f"recommended next action artifact: {out / 'reference_request.md'}" in stdout
    assert f"recommended next action artifact resolved: {(out / 'reference_request.md').resolve()}" in stdout
    assert "recommended next action artifact exists: True" in stdout
    request = json.loads((out / "reference_request.json").read_text(encoding="utf-8"))
    assert request["schema"] == "vemcad.acad_reference_request/v1"
    assert request["reason"] == "recapture-required"
    assert request["case_count"] == 1
    assert request["boundary"] == {
        "renders_dxf": False,
        "compares_renders": False,
        "changes_x3_scoring": False,
        "changes_renderer": False,
        "requires_returned_autocad_png": True,
        "requires_viewspace_match": True,
        "autocad_equivalence_claim": False,
    }
    assert request["cases"][0]["id"] == "G11"
    assert request["cases"][0]["requested_view_contract"] == "model-extents"
    assert request["cases"][0]["recommended_output_name"] == "G11_autocad_model_extents.png"
    assert request["cases"][0]["requested_expected_size"] == {"width": 800, "height": 600}
    assert request["cases"][0]["source_dxf_sha256"] == _sha256(dxf)
    assert request["cases"][0]["source_dxf_size_bytes"] == Path(dxf).stat().st_size
    assert request["cases"][0]["candidate_png_sha256"] == _sha256(ours)
    assert request["cases"][0]["candidate_png_size_bytes"] == Path(ours).stat().st_size
    request_md = (out / "reference_request.md").read_text(encoding="utf-8")
    assert "AutoCAD Reference Recapture Request" in request_md
    assert "G11_autocad_model_extents.png" in request_md
    assert "Before Capture Or Fulfilment" in request_md
    assert "acad_reference_batch.py" in request_md
    assert "--validate-request" in request_md
    assert "acad_reference_request_run.py" in request_md
    assert "acad_artifact_route.py <next-run-dir>" in request_md
    request_run_block = _markdown_block_after(
        request_md,
        "python3 tools/render_regression/acad_reference_request_run.py \\",
    )
    route_block = _markdown_block_after(
        request_md,
        "python3 tools/render_regression/acad_artifact_route.py <next-run-dir> \\",
    )
    assert "--recursive" in route_block
    assert "--text" in route_block
    assert "--require-source-boundary autocad_equivalence_claim=false" in request_md
    assert request_md.count("--require-request-boundary autocad_equivalence_claim=false") == 3
    assert request_md.count("--require-request-boundary requires_returned_autocad_png=true") == 3
    assert request_md.count("--require-request-boundary requires_viewspace_match=true") == 3
    assert request_md.count("--fail-on-input-review") == 1
    assert request_md.count("--forbid-action-domain input-review") == 1
    assert request_md.count("--require-kind batch") == 1
    assert request_md.count("--require-kind compare") == 1
    assert request_md.count("--require-kind request_run") == 1
    assert request_md.count("--require-artifact-kind reference_request_validation_tsv") == 1
    assert request_md.count("--require-artifact-kind reference_intake_tsv") == 1
    assert request_md.count("--require-artifact-kind case_actions_tsv") == 1
    assert request_md.count("--require-artifact-kind summary_tsv") == 1
    assert request_md.count("--require-route-count 3") == 1
    assert request_md.count("--require-action-artifact-exists") == 1
    for expected in [
        "--require-request-boundary autocad_equivalence_claim=false",
        "--require-request-boundary requires_returned_autocad_png=true",
        "--require-request-boundary requires_viewspace_match=true",
        "--fail-on-input-review",
    ]:
        assert expected in request_run_block
    for expected in [
        "--require-source-boundary autocad_equivalence_claim=false",
        "--require-request-boundary autocad_equivalence_claim=false",
        "--require-request-boundary requires_returned_autocad_png=true",
        "--require-request-boundary requires_viewspace_match=true",
        "--forbid-action-domain input-review",
        "--require-kind batch",
        "--require-kind compare",
        "--require-kind request_run",
        "--require-artifact-kind reference_request_validation_tsv",
        "--require-artifact-kind reference_intake_tsv",
        "--require-artifact-kind case_actions_tsv",
        "--require-artifact-kind summary_tsv",
        "--require-route-count 3",
        "--require-action-artifact-exists",
    ]:
        assert expected in route_block
    assert f"--candidate-cases {candidates}" in request_md
    assert "viewspace_mismatch` still exits `2`" in request_md
    assert "`mismatch`" in request_md
    assert "`fallback`" in request_md
    assert "`800x600`" in request_md
    assert _sha256(dxf) in request_md
    assert _sha256(ours) in request_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert {item["kind"] for item in artifact_index["artifacts"]} >= {
        "reference_request_json",
        "reference_request_markdown",
        "route_summary_json",
        "route_summary_markdown",
    }


def test_manifest_harness_escapes_markdown_table_cells(tmp_path):
    acad = _png(tmp_path / "acad.png", size=(800, 600), box=[220, 165, 580, 435])
    ours = _png(tmp_path / "ours.png", size=(760, 570), box=[20, 15, 740, 555])
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": arm.SCHEMA,
        "cases": [{
            "id": "G|11",
            "drawing_id": "G11|bearing\ncap",
            "source_dxf": dxf,
            "acad_png": acad,
            "capture_method": "plot-export",
            "view_contract": "model-extents",
            "expected_size": [800, 600],
        }],
    }), encoding="utf-8")
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps([{"id": "G|11", "ours": ours}]), encoding="utf-8")
    out = tmp_path / "out"

    assert harness.main([
        "--manifest", str(manifest),
        "--candidate-cases", str(candidates),
        "--out-dir", str(out),
    ]) == 2

    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    case_row = next(line for line in summary_md.splitlines() if "G11\\|bearing cap" in line)
    assert "`G\\|11`" in case_row
    assert _unescaped_pipe_count(case_row) == 12
    triage_row = next(line for line in summary_md.splitlines() if "`recapture-required`" in line)
    assert "`G\\|11`" in triage_row
    assert _unescaped_pipe_count(triage_row) == 9

    request_md = (out / "reference_request.md").read_text(encoding="utf-8")
    request_row = next(line for line in request_md.splitlines() if "G11\\|bearing cap" in line)
    assert "`G\\|11`" in request_row
    assert "`G_11_autocad_model_extents.png`" in request_row
    assert _unescaped_pipe_count(request_row) == 11


def test_manifest_harness_stops_on_blocked_manifest(tmp_path, capsys):
    acad = _png(tmp_path / "acad.png", box=[20, 15, 740, 555])
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(
        tmp_path / "manifest.json",
        acad=acad,
        dxf=dxf,
        capture_method="screenshot",
    )
    out = tmp_path / "out"

    rc = harness.main(["--manifest", str(manifest), "--out-dir", str(out), "--dry-run"])
    stdout = capsys.readouterr().out

    assert rc == 2
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "blocked"
    assert summary["issues"][0]["code"] == "diagnostic_capture_method"
    assert summary["issue_code_counts"] == {"diagnostic_capture_method": 1}
    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    assert "status: `blocked`" in summary_md
    assert "issue_code_counts: `diagnostic_capture_method=1`" in summary_md
    assert "`diagnostic_capture_method`" in summary_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["issue_code_counts"] == {"diagnostic_capture_method": 1}
    assert artifact_index["boundary"]["compares_renders"] is False
    assert artifact_index["boundary"]["autocad_equivalence_claim"] is False
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "summary_json",
        "summary_markdown",
        "route_summary_json",
        "route_summary_markdown",
    }
    route_summary = json.loads((out / "route_summary.json").read_text(encoding="utf-8"))
    assert route_summary["recommended_next_action"]["code"] == "inspect-compare-input-block"
    assert "route summary" in stdout
    assert "recommended next action: inspect-compare-input-block" in stdout
    assert "recommended next action domain: input" in stdout


def test_triage_rows_prioritize_matched_fail_then_recapture_then_pass():
    rows = [
        {
            "id": "C",
            "viewspace_status": "match",
            "x3_summary": {"band": "pass", "ink_iou": 0.99},
        },
        {
            "id": "B",
            "viewspace_status": "mismatch",
            "x3_summary": {"band": "fallback", "ink_iou": 0.10},
        },
        {
            "id": "A",
            "viewspace_status": "match",
            "x3_summary": {"band": "fallback", "ink_iou": 0.40},
        },
    ]

    ordered = harness._triage_rows(rows)

    assert [row["id"] for row in ordered] == ["A", "B", "C"]
    assert [harness._triage_bucket(row) for row in ordered] == [
        "renderer-candidate",
        "recapture-required",
        "matched-pass",
    ]
    assert [harness._recommended_action_domain(row) for row in ordered] == [
        "renderer-candidate",
        "input",
        "pass-review",
    ]
