import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_reference_manifest as arm  # noqa: E402


def _png(path: Path, size=(800, 600)) -> str:
    Image.new("RGB", size, (255, 255, 255)).save(path)
    return str(path)


def _dxf(path: Path) -> str:
    path.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    return str(path)


def _manifest(path: Path, cases):
    path.write_text(json.dumps({"schema": arm.SCHEMA, "cases": cases}), encoding="utf-8")
    return path


def test_manifest_accepts_plot_export_with_matching_size(tmp_path):
    acad = _png(tmp_path / "acad.png", (2339, 1653))
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": acad,
        "capture_method": "plot-export",
        "view_contract": "model-extents",
        "expected_size": {"width": 2339, "height": 1653},
    }])

    report = arm.validate_manifest(manifest)

    assert report["status"] == "pass"
    assert report["error_count"] == 0
    assert report["cases"][0]["trust"] == "gate"
    assert report["cases"][0]["actual_size"] == {"width": 2339, "height": 1653}


def test_manifest_rejects_viewport_screenshot_even_when_file_exists(tmp_path):
    acad = _png(tmp_path / "acad.png")
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": acad,
        "capture_method": "screenshot",
        "view_contract": "model-extents",
        "expected_size": [800, 600],
    }])

    report = arm.validate_manifest(manifest)

    assert report["status"] == "blocked"
    assert report["cases"][0]["trust"] == "blocked"
    assert {issue["code"] for issue in report["issues"]} == {"diagnostic_capture_method"}


def test_manifest_requires_drawing_id(tmp_path):
    acad = _png(tmp_path / "acad.png")
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "source_dxf": dxf,
        "acad_png": acad,
        "capture_method": "plot-export",
        "view_contract": "model-extents",
        "expected_size": [800, 600],
    }])

    report = arm.validate_manifest(manifest)

    assert report["status"] == "blocked"
    assert {issue["code"] for issue in report["issues"]} == {"missing_drawing_id"}


def test_manifest_rejects_unmatched_view_contract(tmp_path):
    acad = _png(tmp_path / "acad.png")
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": acad,
        "capture_method": "exportpng",
        "view_contract": "paper-layout",
        "expected_size": [800, 600],
    }])

    report = arm.validate_manifest(manifest)

    assert report["status"] == "blocked"
    assert report["issues"][0]["code"] == "unmatched_view_contract"


def test_manifest_rejects_expected_size_mismatch(tmp_path):
    acad = _png(tmp_path / "acad.png", (801, 600))
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": acad,
        "capture_method": "publish",
        "view_contract": "explicit-window",
        "expected_size": [800, 600],
    }])

    report = arm.validate_manifest(manifest)

    assert report["status"] == "blocked"
    assert report["issues"][0]["code"] == "expected_size_mismatch"


def test_manifest_requires_expected_size(tmp_path):
    acad = _png(tmp_path / "acad.png", (800, 600))
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": acad,
        "capture_method": "plot-export",
        "view_contract": "model-extents",
    }])

    report = arm.validate_manifest(manifest)

    assert report["status"] == "blocked"
    assert report["issues"][0]["code"] == "missing_expected_size"
    assert report["cases"][0]["expected_size"] is None


def test_manifest_rejects_non_integer_expected_size(tmp_path):
    acad = _png(tmp_path / "acad.png", (800, 600))
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": acad,
        "capture_method": "plot-export",
        "view_contract": "model-extents",
        "expected_size": {"width": 800.9, "height": True},
    }])

    report = arm.validate_manifest(manifest)

    assert report["status"] == "blocked"
    assert report["issues"][0]["code"] == "invalid_expected_size"
    assert report["cases"][0]["expected_size"] is None


def test_manifest_rejects_unreadable_acad_png(tmp_path):
    acad = tmp_path / "acad.png"
    acad.write_text("not an image", encoding="utf-8")
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": str(acad),
        "capture_method": "plot-export",
        "view_contract": "model-extents",
        "expected_size": [800, 600],
    }])

    report = arm.validate_manifest(manifest)

    assert report["status"] == "blocked"
    assert report["issues"][0]["code"] == "invalid_acad_png"


def test_cli_writes_validation_report_and_batch_stub(tmp_path, capsys):
    acad = _png(tmp_path / "acad.png")
    dxf = _dxf(tmp_path / "B11.dxf")
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "drawing_id": "G11/B11",
        "source_dxf": dxf,
        "acad_png": acad,
        "capture_method": "plot-raster",
        "view_contract": "model-extents",
        "expected_size": [800, 600],
    }])
    report_out = tmp_path / "validation.json"
    cases_out = tmp_path / "cases.json"

    rc = arm.main([str(manifest), "--json-out", str(report_out), "--batch-cases-out", str(cases_out)])

    assert rc == 0
    assert "pass" in capsys.readouterr().out
    payload = json.loads(report_out.read_text(encoding="utf-8"))
    assert payload["schema"] == arm.REPORT_SCHEMA
    batch_cases = json.loads(cases_out.read_text(encoding="utf-8"))
    assert batch_cases == [{"id": "G11", "acad": acad, "ours": ""}]


def test_cli_returns_two_when_manifest_is_blocked(tmp_path):
    manifest = _manifest(tmp_path / "manifest.json", [{
        "id": "G11",
        "source_dxf": "missing.dxf",
        "acad_png": "missing.png",
        "capture_method": "viewport-capture",
        "view_contract": "model-extents",
    }])

    assert arm.main([str(manifest)]) == 2
