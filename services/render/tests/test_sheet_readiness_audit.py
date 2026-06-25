import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from sheet_readiness_audit import (  # noqa: E402
    Thresholds,
    analyse_pair,
    image_stats,
    write_contact_sheets,
)


def _drawing(path: Path, *, crop: bool = False, edge_touch: bool = False):
    img = Image.new("RGB", (500, 350), "white")
    d = ImageDraw.Draw(img)
    if crop:
        d.rectangle((60, 60, 120, 120), outline="black", width=4)
    else:
        d.rectangle((60, 60, 440, 300), outline="black", width=4)
        d.line((80, 170, 420, 170), fill="black", width=4)
        d.line((250, 80, 250, 280), fill="black", width=4)
    if edge_touch:
        d.line((0, 5, 499, 5), fill="black", width=5)
    img.save(path)
    return path


def test_image_stats_detects_ink_and_edges(tmp_path):
    p = _drawing(tmp_path / "edge.png", edge_touch=True)
    stats = image_stats(p)
    assert stats.ink_px > 600
    assert stats.edge_ink_fraction > 0.02
    assert stats.bbox is not None


def test_audit_passes_clean_sheet_pair(tmp_path):
    extents = _drawing(tmp_path / "extents.png")
    sheet = _drawing(tmp_path / "sheet.png")
    result = analyse_pair(
        tmp_path / "a.dxf",
        extents,
        sheet,
        sheet_mode="detected",
        resolved_view="window",
        thresholds=Thresholds(min_ink_px=100),
        out_root=tmp_path,
    )
    assert result.status == "pass"
    assert result.retained_ink_fraction and result.retained_ink_fraction > 0.95


def test_audit_fails_heavy_ink_loss(tmp_path):
    extents = _drawing(tmp_path / "extents.png")
    sheet = _drawing(tmp_path / "sheet.png", crop=True)
    result = analyse_pair(
        tmp_path / "a.dxf",
        extents,
        sheet,
        sheet_mode="detected",
        resolved_view="window",
        thresholds=Thresholds(min_ink_px=100, retained_fail=0.6, retained_review=0.8),
        out_root=tmp_path,
    )
    assert result.status == "fail"
    assert "retained very little" in " ".join(result.notes)


def test_audit_marks_fallback_for_review(tmp_path):
    extents = _drawing(tmp_path / "extents.png")
    sheet = _drawing(tmp_path / "sheet.png")
    result = analyse_pair(
        tmp_path / "a.dxf",
        extents,
        sheet,
        sheet_mode="fallback",
        resolved_view="extents",
        thresholds=Thresholds(min_ink_px=100),
        out_root=tmp_path,
    )
    assert result.status == "review"
    assert "fell back" in " ".join(result.notes)


def test_contact_sheet_writes_review_png(tmp_path):
    extents = _drawing(tmp_path / "extents.png")
    sheet = _drawing(tmp_path / "sheet.png")
    result = analyse_pair(
        tmp_path / "a.dxf",
        extents,
        sheet,
        sheet_mode="detected",
        resolved_view="window",
        thresholds=Thresholds(min_ink_px=100),
        out_root=tmp_path,
    )
    sheets = write_contact_sheets([result], tmp_path)
    assert sheets == ["contact_sheet_01.png"]
    assert (tmp_path / sheets[0]).stat().st_size > 1000
