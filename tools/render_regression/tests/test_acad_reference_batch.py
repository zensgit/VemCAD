import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_manifest_compare as harness  # noqa: E402
import acad_reference_batch as batch  # noqa: E402


def _png(path: Path, size=(320, 240)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (255, 255, 255)).save(path)
    return str(path)


def _dxf(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    return str(path)


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
