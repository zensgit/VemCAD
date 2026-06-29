import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_manifest_compare as harness  # noqa: E402
import acad_reference_case as casegen  # noqa: E402


def _png(path: Path, size=(2339, 1653)) -> str:
    Image.new("RGB", size, (255, 255, 255)).save(path)
    return str(path)


def _dxf(path: Path) -> str:
    path.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    return str(path)


def test_case_generator_writes_valid_manifest_and_candidate_cases(tmp_path):
    acad = _png(tmp_path / "acad.png", (2339, 1653))
    ours = _png(tmp_path / "ours.png", (2339, 1653))
    dxf = _dxf(tmp_path / "B11.dxf")
    report = tmp_path / "report.json"
    report.write_text("{}", encoding="utf-8")
    out_dir = tmp_path / "case"

    rc = casegen.main([
        "--case-id", "G11",
        "--drawing-id", "G11/B11",
        "--source-dxf", dxf,
        "--acad-png", acad,
        "--ours", ours,
        "--render-report", str(report),
        "--render-image", "ghcr.io/zensgit/vemcad-render:main",
        "--diagnostic", "window_source=model-extents",
        "--out-dir", str(out_dir),
    ])

    assert rc == 0
    manifest = json.loads((out_dir / "acad_manifest.json").read_text(encoding="utf-8"))
    candidate = json.loads((out_dir / "candidate_cases.json").read_text(encoding="utf-8"))[0]
    case = manifest["cases"][0]
    assert case["expected_size"] == {"width": 2339, "height": 1653}
    assert case["capture_method"] == "plot-export"
    assert case["view_contract"] == "model-extents"
    assert candidate["id"] == "G11"
    assert candidate["render_report"] == str(report.resolve())
    assert candidate["diagnostics"] == {"window_source": "model-extents"}

    dry_run_out = tmp_path / "dry-run"
    assert harness.main([
        "--manifest", str(out_dir / "acad_manifest.json"),
        "--out-dir", str(dry_run_out),
        "--dry-run",
    ]) == 0


def test_case_generator_blocks_unreadable_autocad_png(tmp_path):
    acad = tmp_path / "acad.png"
    acad.write_text("not an image", encoding="utf-8")
    ours = _png(tmp_path / "ours.png")
    dxf = _dxf(tmp_path / "B11.dxf")

    assert casegen.main([
        "--case-id", "G11",
        "--drawing-id", "G11/B11",
        "--source-dxf", dxf,
        "--acad-png", str(acad),
        "--ours", ours,
        "--out-dir", str(tmp_path / "case"),
    ]) == 2
