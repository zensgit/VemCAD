"""Version-diff overlay tests — synthetic PIL pairs, deterministic, no renderer.
The flagship L1 engine: added=green, removed=red, unchanged=grey."""

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diff import diff_overlay, COL_ADDED, COL_REMOVED  # noqa: E402


def _draw(path, *, lines, bg=(255, 255, 255), ink=(0, 0, 0), size=(420, 300)):
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, size[0] - 20, size[1] - 20], outline=ink, width=3)
    for (x0, y0, x1, y1) in lines:
        d.line([x0, y0, x1, y1], fill=ink, width=3)
    im.save(path)
    return path


def _blank(path, bg=(255, 255, 255), size=(420, 300)):
    Image.new("RGB", size, bg).save(path)   # pure background, no ink
    return path


FRAME = []                       # just the border
ONE = [(40, 150, 380, 150)]      # + a midline
TWO = [(40, 150, 380, 150), (40, 90, 380, 90)]


def _count_color(png_path, rgb, tol=40):
    arr = np.asarray(Image.open(png_path).convert("RGB")).astype(int)
    d = np.abs(arr - np.array(rgb)).sum(axis=2)
    return int((d < tol).sum())


def test_identical_has_no_changes(tmp_path):
    a = _draw(tmp_path / "a.png", lines=ONE)
    b = _draw(tmp_path / "b.png", lines=ONE)
    out = tmp_path / "ov.png"
    r = diff_overlay(a, b, out_path=out)
    assert r.aligned and r.comparable
    assert r.changed_fraction < 0.02
    assert r.added_px + r.removed_px < r.unchanged_px * 0.05
    # overlay exists, right size, essentially no green/red
    assert out.is_file()
    assert _count_color(out, COL_ADDED) < 50 and _count_color(out, COL_REMOVED) < 50


def test_added_line_is_green(tmp_path):
    a = _draw(tmp_path / "a.png", lines=ONE)    # ref: 1 midline
    b = _draw(tmp_path / "b.png", lines=TWO)    # candidate: +1 line
    out = tmp_path / "ov.png"
    r = diff_overlay(a, b, out_path=out)
    assert r.added_px > 0
    assert r.added_px > r.removed_px            # net addition
    assert r.changed_fraction > 0.05
    assert _count_color(out, COL_ADDED) > 100        # green present
    assert _count_color(out, (30, 160, 30)) > 100    # pins COL_ADDED to literal green


def test_removed_line_is_red(tmp_path):
    a = _draw(tmp_path / "a.png", lines=TWO)    # ref: 2 lines
    b = _draw(tmp_path / "b.png", lines=ONE)    # candidate: -1 line
    out = tmp_path / "ov.png"
    r = diff_overlay(a, b, out_path=out)
    assert r.removed_px > 0
    assert r.removed_px > r.added_px
    assert _count_color(out, COL_REMOVED) > 100      # red present
    assert _count_color(out, (220, 30, 30)) > 100    # pins COL_REMOVED to literal red


def test_small_shift_not_flagged_as_change(tmp_path):
    a = _draw(tmp_path / "a.png", lines=ONE)
    b = _draw(tmp_path / "b.png", lines=[(42, 151, 382, 151)])  # ~2px shift
    r = diff_overlay(a, b)
    assert r.changed_fraction < 0.05   # alignment + tol absorb the jitter


def test_not_comparable_skips(tmp_path):
    a = _draw(tmp_path / "a.png", lines=ONE)
    b = _draw(tmp_path / "b.png", lines=ONE)
    r = diff_overlay(a, b, comparable=False, skip_reason="bg-mismatch")
    assert not r.comparable and r.skip_reason == "bg-mismatch"


def test_no_overlay_when_out_omitted(tmp_path):
    a = _draw(tmp_path / "a.png", lines=ONE)
    b = _draw(tmp_path / "b.png", lines=TWO)
    r = diff_overlay(a, b)              # no out_path
    assert r.overlay_path is None
    assert r.added_px > 0              # summary still computed


def test_both_blank_is_flagged(tmp_path):
    a = _blank(tmp_path / "a.png")
    b = _blank(tmp_path / "b.png")
    r = diff_overlay(a, b, out_path=tmp_path / "ov.png")
    assert r.comparable and not r.aligned
    assert r.skip_reason == "both-blank"
    assert r.changed_fraction == 0.0
    assert r.added_px == 0 and r.removed_px == 0


def test_blank_candidate_is_all_removed(tmp_path):
    a = _draw(tmp_path / "a.png", lines=ONE)   # ref has ink
    b = _blank(tmp_path / "b.png")             # candidate is empty
    r = diff_overlay(a, b)
    assert r.aligned and r.comparable
    assert r.removed_px > 0 and r.added_px == 0
    assert r.changed_fraction == 1.0           # everything gone


def test_blank_reference_is_all_added(tmp_path):
    a = _blank(tmp_path / "a.png")             # ref is empty
    b = _draw(tmp_path / "b.png", lines=ONE)   # candidate has ink
    r = diff_overlay(a, b)
    assert r.aligned and r.comparable
    assert r.added_px > 0 and r.removed_px == 0
    assert r.changed_fraction == 1.0           # everything new


def _box(path, *, x0, y0, x1, y1, size=(420, 300)):
    im = Image.new("RGB", size, (255, 255, 255))
    ImageDraw.Draw(im).rectangle([x0, y0, x1, y1], outline=(0, 0, 0), width=3)
    im.save(path)
    return path


def test_view_space_mismatch_is_flagged(tmp_path):
    # A's ink bbox is wide (300x100, aspect 3.0), B's is square (200x200,
    # aspect 1.0): the drawing's extents changed between revisions, so the two
    # renders are NOT in a shared view-space — flag, don't silently mis-diff.
    a = _box(tmp_path / "a.png", x0=40, y0=100, x1=340, y1=200)
    b = _box(tmp_path / "b.png", x0=110, y0=50, x1=310, y1=250)
    out = tmp_path / "ov.png"
    r = diff_overlay(a, b, out_path=out)
    assert not r.comparable
    assert r.skip_reason == "view-space-mismatch"
    assert r.changed_fraction == 0.0
    assert r.overlay_path is None and not out.exists()  # no misleading overlay


def test_minor_extent_change_still_diffs(tmp_path):
    # bbox aspect within ASPECT_TOL (~1.7% wider) → guard must NOT fire.
    a = _box(tmp_path / "a.png", x0=40, y0=100, x1=340, y1=200)   # 300x100
    b = _box(tmp_path / "b.png", x0=40, y0=100, x1=345, y1=200)   # 305x100
    r = diff_overlay(a, b)
    assert r.comparable and r.aligned


# ---- shared_view (common-window) mode: both renders share view-space ----

def test_shared_view_detects_positional_change(tmp_path):
    # SAME shape, MOVED within a shared window (the case the per-extents path
    # silently re-centres into a FALSE 'identical'). shared_view must score it
    # as a real change: the left box is removed, the right box is added.
    a = _box(tmp_path / "a.png", x0=40, y0=110, x1=160, y1=190)   # left box
    b = _box(tmp_path / "b.png", x0=260, y0=110, x1=380, y1=190)  # same box, moved right
    out = tmp_path / "ov.png"
    r = diff_overlay(a, b, out_path=out, shared_view=True)
    assert r.comparable and r.aligned
    assert r.changed_fraction > 0.5            # NOT a false 'no change'
    assert r.added_px > 0 and r.removed_px > 0  # left gone, right new
    assert out.is_file()


def test_shared_view_extents_grew_is_comparable(tmp_path):
    # A square-ish, B wider (extents grew): the per-extents path would flag
    # view-space-mismatch; in shared_view (both already in the union window)
    # the pair is comparable and the added width shows as a real change.
    a = _box(tmp_path / "a.png", x0=40, y0=110, x1=160, y1=190)
    b = _box(tmp_path / "b.png", x0=40, y0=110, x1=380, y1=190)   # grew in X
    r = diff_overlay(a, b, shared_view=True)
    assert r.comparable and r.aligned
    assert r.skip_reason == ""
    assert r.added_px > 0

    # Contrast: the SAME pair through the legacy per-extents path is correctly
    # skipped (independent crop normalises the aspect difference away / flags it),
    # proving shared_view is what unlocks the comparison — not a behaviour change
    # to the existing path.
    r_legacy = diff_overlay(a, b)
    assert r_legacy.skip_reason == "view-space-mismatch"


def test_shared_view_identical_is_unchanged(tmp_path):
    a = _box(tmp_path / "a.png", x0=60, y0=110, x1=360, y1=190)
    b = _box(tmp_path / "b.png", x0=60, y0=110, x1=360, y1=190)
    r = diff_overlay(a, b, shared_view=True)
    assert r.comparable and r.aligned
    assert r.changed_fraction < 0.02
    assert r.added_px + r.removed_px < r.unchanged_px * 0.05


def test_shared_view_both_blank(tmp_path):
    r = diff_overlay(_blank(tmp_path / "a.png"), _blank(tmp_path / "b.png"),
                     shared_view=True)
    assert r.comparable and not r.aligned and r.skip_reason == "both-blank"
