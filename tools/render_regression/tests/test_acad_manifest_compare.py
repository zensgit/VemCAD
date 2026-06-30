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
    assert "\t1\tmatched-pass\tpass-review\t" in tsv_lines[1]
    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    assert "AutoCAD Manifest Compare Summary" in summary_md
    assert "status: `pass`" in summary_md
    assert "autocad_equivalence_claim: `False`" in summary_md
    assert "| `G11` | G11/B11 | `match` | `pass` |" in summary_md
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
    assert "| `G11` | G11/B11 | `mismatch` | `fallback` |" in summary_md
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
    assert "recapture-autocad-or-provide-window" in route_summary_md
    assert "route summary" in stdout
    assert "recommended next action: recapture-autocad-or-provide-window" in stdout
    assert "recommended next action domain: input" in stdout
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
    assert "--recursive" in request_md
    assert "--text" in request_md
    assert "--require-source-boundary autocad_equivalence_claim=false" in request_md
    assert request_md.count("--require-request-boundary autocad_equivalence_claim=false") == 3
    assert request_md.count("--require-request-boundary requires_returned_autocad_png=true") == 3
    assert request_md.count("--require-request-boundary requires_viewspace_match=true") == 3
    assert f"--candidate-cases {candidates}" in request_md
    assert "viewspace_mismatch` still exits `2`" in request_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert {item["kind"] for item in artifact_index["artifacts"]} >= {
        "reference_request_json",
        "reference_request_markdown",
        "route_summary_json",
        "route_summary_markdown",
    }


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
    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    assert "status: `blocked`" in summary_md
    assert "`diagnostic_capture_method`" in summary_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
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
