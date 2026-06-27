import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from sheet_readiness_audit import (  # noqa: E402
    Thresholds,
    analyse_pair,
    image_stats,
    parse_args,
    write_contact_sheets,
)

# Curated sheet-readiness corpus: one synthetic (extents, sheet) pair per
# verdict category, with the verdict analyse_pair MUST return under the
# SHIPPING DEFAULT thresholds (Thresholds()). This is the verdict-logic
# regression gate (distinct from the golden-corpus plumbing gate in
# render-image.yml). The inline list below is the source of truth;
# tools/render_regression/sheet_corpus/corpus.json mirrors it for docs and a
# drift check (test_curated_corpus_json_matches_inline_cases).
_CORPUS_JSON = (
    Path(__file__).resolve().parents[3]
    / "tools"
    / "render_regression"
    / "sheet_corpus"
    / "corpus.json"
)

# (name, extents recipe, sheet recipe, sheet_mode, expected verdict)
CURATED_CASES = [
    ("clean_sheet", "frame", "frame", "detected", "pass"),
    ("over_crop", "frame", "crop", "detected", "fail"),
    ("edge_touch", "frame", "edge", "detected", "review"),
    ("no_frame_fallback", "frame", "frame", "fallback", "review"),
]


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


# ---------------------------------------------------------------------------
# A1a-2: curated sheet-readiness corpus with KNOWN expected verdicts.
# ---------------------------------------------------------------------------

_RECIPE_KW = {
    "frame": {},
    "crop": {"crop": True},
    "edge": {"edge_touch": True},
}


def _render_recipe(recipe: str, path: Path) -> Path:
    if recipe not in _RECIPE_KW:
        raise ValueError(f"unknown fixture recipe: {recipe!r}")
    return _drawing(path, **_RECIPE_KW[recipe])


@pytest.mark.parametrize(
    "name,extents_recipe,sheet_recipe,sheet_mode,expected",
    CURATED_CASES,
    ids=[c[0] for c in CURATED_CASES],
)
def test_curated_corpus_reproduces_known_verdict(
    tmp_path, name, extents_recipe, sheet_recipe, sheet_mode, expected
):
    """Each curated (extents, sheet) pair must yield its KNOWN verdict under
    the shipping DEFAULT thresholds. Uses Thresholds() (no per-case override),
    so this regresses the verdict the audit ships, not a tuned one."""
    extents = _render_recipe(extents_recipe, tmp_path / f"{name}_extents.png")
    sheet = _render_recipe(sheet_recipe, tmp_path / f"{name}_sheet.png")
    result = analyse_pair(
        tmp_path / f"{name}.dxf",
        extents,
        sheet,
        sheet_mode=sheet_mode,
        resolved_view="window" if sheet_mode == "detected" else "extents",
        thresholds=Thresholds(),
        out_root=tmp_path,
    )
    assert result.status == expected, (
        f"{name}: expected {expected}, got {result.status}; notes={result.notes}"
    )


def test_curated_corpus_covers_all_four_categories():
    """Guard against a silently-empty parametrization: the corpus must cover
    exactly the four readiness verdict categories."""
    assert len(CURATED_CASES) == 4
    assert {c[4] for c in CURATED_CASES} == {"pass", "fail", "review"}


def test_cli_accepts_acad_display_style_for_preview_audits(tmp_path):
    args = parse_args([
        "--input-dir", str(tmp_path),
        "--out-dir", str(tmp_path / "out"),
        "--style", "acad-display",
    ])
    assert args.style == "acad-display"


def test_curated_corpus_json_matches_inline_cases():
    """corpus.json is documentation; it must not drift from the inline cases
    that the test actually runs (or one would silently lie about the other)."""
    spec = json.loads(_CORPUS_JSON.read_text("utf-8"))
    assert spec["schema"] == "vemcad.sheet_readiness_corpus/v1"
    json_cases = {
        (c["name"], c["extents"], c["sheet"], c["sheet_mode"], c["expected_verdict"])
        for c in spec["cases"]
    }
    assert json_cases == set(CURATED_CASES)
