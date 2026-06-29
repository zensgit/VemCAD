import json
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


def test_manifest_harness_runs_compare_and_records_match(tmp_path):
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
    assert Path(row["viewspace_report"]).is_file()
    assert Path(row["overlay"]).is_file()
    assert (out / "summary.tsv").is_file()
    tsv_lines = (out / "summary.tsv").read_text(encoding="utf-8").splitlines()
    assert "triage_rank\ttriage_bucket" in tsv_lines[0]
    assert "\t1\tmatched-pass\t" in tsv_lines[1]
    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    assert "AutoCAD Manifest Compare Summary" in summary_md
    assert "status: `pass`" in summary_md
    assert "autocad_equivalence_claim: `False`" in summary_md
    assert "| `G11` | G11/B11 | `match` | `pass` |" in summary_md
    assert "viewspace_mismatch" in summary_md
    assert "## Triage Priority" in summary_md
    assert "| 1 | `G11` | `matched-pass` | `match` | `pass` |" in summary_md
    assert (out / "contact_sheet.png").stat().st_size > 1000
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert artifact_index["schema"] == "vemcad.acad_manifest_compare_artifact_index/v1"
    assert {item["kind"] for item in artifact_index["artifacts"]} >= {
        "summary_json",
        "summary_markdown",
        "summary_tsv",
        "contact_sheet",
        "autocad_reference",
        "vemcad_candidate",
        "x3_overlay",
        "viewspace_report",
    }


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


def test_manifest_harness_blocks_viewspace_mismatch_without_equivalence_claim(tmp_path):
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

    assert rc == 2
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = summary["rows"][0]
    assert summary["status"] == "viewspace_mismatch"
    assert row["viewspace_status"] == "mismatch"
    assert row["compare_exit_code"] == 2
    assert row["triage_rank"] == 1
    assert row["triage_bucket"] == "recapture-required"
    assert row["recommended_action"].startswith("recapture AutoCAD")
    assert summary["boundary"]["autocad_equivalence_claim"] is False
    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    assert "status: `viewspace_mismatch`" in summary_md
    assert "It is not an AutoCAD-equivalence result" in summary_md
    assert "| `G11` | G11/B11 | `mismatch` | `fallback` |" in summary_md
    assert "| 1 | `G11` | `recapture-required` | `mismatch` | `fallback` |" in summary_md
    assert (out / "contact_sheet.png").stat().st_size > 1000


def test_manifest_harness_stops_on_blocked_manifest(tmp_path):
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

    assert rc == 2
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "blocked"
    assert summary["issues"][0]["code"] == "diagnostic_capture_method"
    summary_md = (out / "summary.md").read_text(encoding="utf-8")
    assert "status: `blocked`" in summary_md
    assert "`diagnostic_capture_method`" in summary_md
    artifact_index = json.loads((out / "artifact_index.json").read_text(encoding="utf-8"))
    assert {item["kind"] for item in artifact_index["artifacts"]} == {
        "summary_json",
        "summary_markdown",
    }


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
