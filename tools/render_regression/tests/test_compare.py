"""D2 comparator unit tests — synthetic PIL image pairs (deterministic, no
live renderer; the render→compare end-to-end is exercised in CI where the
image builds cleanly)."""

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compare import compare, band_for, TRUST  # noqa: E402
from baseline import BaselineStore  # noqa: E402


def draw(path, *, shift=(0, 0), bg=(30, 30, 35), ink=(255, 255, 255),
         extra_line=False, blank=False, size=(400, 250)):
    im = Image.new("RGB", size, bg)
    if not blank:
        d = ImageDraw.Draw(im)
        sx, sy = shift
        d.rectangle([40 + sx, 40 + sy, 360 + sx, 210 + sy], outline=ink, width=3)
        d.line([60 + sx, 125 + sy, 340 + sx, 125 + sy], fill=ink, width=2)
        if extra_line:
            d.line([60 + sx, 80 + sy, 340 + sx, 80 + sy], fill=(255, 0, 0), width=2)
    im.save(path)
    return path


def test_identical_renders_score_high(tmp_path):
    a = draw(tmp_path / "a.png"); b = draw(tmp_path / "b.png")
    r = compare(a, b)
    assert r.aligned and r.comparable
    assert r.geometry_ink_iou >= 0.97
    assert r.band == "pass"
    assert r.trust == "gate"


def test_small_shift_absorbed_by_alignment(tmp_path):
    a = draw(tmp_path / "a.png")
    b = draw(tmp_path / "b.png", shift=(2, 1))   # 2px shift
    r = compare(a, b)
    # crop-to-bbox removes the global shift; residual within tolerance → pass
    assert r.geometry_ink_iou >= 0.95
    assert r.band in ("pass", "review")


def test_missing_geometry_drops_score(tmp_path):
    a = draw(tmp_path / "a.png", extra_line=True)   # has the red line
    b = draw(tmp_path / "b.png", extra_line=False)  # missing it
    r = compare(a, b)
    assert r.geometry_ink_iou < 0.97   # divergence detected
    assert r.band in ("review", "fallback")


def test_blank_candidate_is_fallback(tmp_path):
    a = draw(tmp_path / "a.png")
    b = draw(tmp_path / "b.png", blank=True)
    r = compare(a, b)
    assert r.geometry_ink_iou == 0.0
    assert r.band == "fallback"


def test_both_blank_match(tmp_path):
    a = draw(tmp_path / "a.png", blank=True)
    b = draw(tmp_path / "b.png", blank=True)
    r = compare(a, b)
    assert r.geometry_ink_iou == 1.0


def test_light_and_dark_bg_both_detect_ink(tmp_path):
    # ink mask is bg-relative, so a white-bg/black-ink pair scores like dark.
    a = draw(tmp_path / "a.png", bg=(255, 255, 255), ink=(0, 0, 0))
    b = draw(tmp_path / "b.png", bg=(255, 255, 255), ink=(0, 0, 0))
    r = compare(a, b)
    assert r.geometry_ink_iou >= 0.97


def test_not_comparable_skips_and_flags(tmp_path):
    a = draw(tmp_path / "a.png"); b = draw(tmp_path / "b.png")
    r = compare(a, b, comparable=False, skip_reason="bg-mismatch")
    assert not r.comparable and r.skip_reason == "bg-mismatch"
    assert r.band == "review"  # never silently passes


def test_viewport_capture_is_advisory_not_gate(tmp_path):
    a = draw(tmp_path / "a.png"); b = draw(tmp_path / "b.png")
    r = compare(a, b, capture_method="viewport-capture")
    assert r.trust == "advisory"   # high score but must not CI-gate
    r2 = compare(a, b, capture_method="dwg-thumbnail")
    assert r2.trust == "record"


def test_band_thresholds():
    assert band_for(0.99) == "pass"
    assert band_for(0.93) == "review"
    assert band_for(0.5) == "fallback"


# ── baseline governance ──
def test_baseline_record_requires_approver(tmp_path):
    img = draw(tmp_path / "x.png")
    store = BaselineStore(tmp_path / "baselines.json")
    with pytest.raises(ValueError):
        store.record("draw1", "self", img, approver="")
    e = store.record("draw1", "self", img, approver="alice", note="first run")
    assert e.sha256 and store.verify_image("draw1", "self", img)
    store.save()
    assert (tmp_path / "baselines.json").is_file()


def test_baseline_tier_precedence(tmp_path):
    img = draw(tmp_path / "x.png")
    store = BaselineStore(tmp_path / "b.json")
    store.record("d", "self", img, approver="a")
    assert store.best("d").tier == "self"
    store.record("d", "acad", img, approver="a")
    assert store.best("d").tier == "acad"   # acad outranks self
    # reload round-trips
    store.save()
    store2 = BaselineStore(tmp_path / "b.json")
    assert store2.best("d").tier == "acad"


def test_baseline_detects_drift(tmp_path):
    a = draw(tmp_path / "a.png")
    store = BaselineStore(tmp_path / "b.json")
    store.record("d", "self", a, approver="a")
    b = draw(tmp_path / "b.png", extra_line=True)  # different bytes
    assert not store.verify_image("d", "self", b)
