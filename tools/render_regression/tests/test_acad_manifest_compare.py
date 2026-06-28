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
    assert Path(row["viewspace_report"]).is_file()
    assert Path(row["overlay"]).is_file()
    assert (out / "summary.tsv").is_file()


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
    assert row["recommended_action"].startswith("recapture AutoCAD")
    assert summary["boundary"]["autocad_equivalence_claim"] is False


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
