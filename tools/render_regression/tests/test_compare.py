"""D2 comparator unit tests — synthetic PIL image pairs (deterministic, no
live renderer; the render→compare end-to-end is exercised in CI where the
image builds cleanly)."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compare import (  # noqa: E402
    compare,
    compare_color_classes,
    compare_semantic_classes,
    band_for,
    TRUST,
)
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
    assert r.ink_iou >= 0.97
    assert r.band == "pass"
    assert r.trust == "gate"


def test_small_shift_absorbed_by_alignment(tmp_path):
    a = draw(tmp_path / "a.png")
    b = draw(tmp_path / "b.png", shift=(2, 1))   # 2px shift
    r = compare(a, b)
    # crop-to-bbox removes the global shift; residual within tolerance → pass
    assert r.ink_iou >= 0.95
    assert r.band in ("pass", "review")


def test_missing_geometry_drops_score(tmp_path):
    a = draw(tmp_path / "a.png", extra_line=True)   # has the red line
    b = draw(tmp_path / "b.png", extra_line=False)  # missing it
    r = compare(a, b)
    assert r.ink_iou < 0.97   # divergence detected
    assert r.band in ("review", "fallback")


def _class(report, name):
    return next(row for row in report.classes if row.name == name)


def test_color_class_diagnostics_find_missing_red_line(tmp_path):
    # The overall comparator says "different"; the diagnostic split says *why*:
    # black geometry still matches, while AutoCAD's red display layer is absent
    # from the candidate. This is display-colour triage, not CAD semantics.
    a = draw(tmp_path / "acad.png", bg=(255, 255, 255), ink=(0, 0, 0), extra_line=True)
    b = draw(tmp_path / "ours.png", bg=(255, 255, 255), ink=(0, 0, 0), extra_line=False)
    report = compare_color_classes(a, b)
    dark = _class(report, "dark")
    red = _class(report, "red")
    yellow = _class(report, "yellow")

    assert report.aligned and report.comparable
    assert not report.semantic
    assert dark.ink_iou >= 0.97
    assert red.ref_present and not red.cand_present
    assert red.ink_iou == 0.0
    assert yellow.band == "absent"


def _semantic_fixture(tmp_path, *, mask_size=(420, 300)):
    ref = tmp_path / "acad.png"
    cand = tmp_path / "ours.png"
    mask = tmp_path / "classes.png"
    report = tmp_path / "render_report.json"

    for path in (ref, cand):
        im = Image.new("RGB", (420, 300), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.rectangle([20, 20, 400, 280], outline=(0, 0, 0), width=3)
        d.line([40, 150, 380, 150], fill=(0, 0, 0), width=3)
        d.rectangle([70, 60, 150, 92], outline=(0, 0, 0), width=3)
        im.save(path)

    m = Image.new("RGB", mask_size, (0, 0, 0))
    d = ImageDraw.Draw(m)
    d.rectangle([20, 20, 400, 280], outline=(31, 119, 180), width=3)   # geometry
    d.line([40, 150, 380, 150], fill=(31, 119, 180), width=3)
    d.rectangle([70, 60, 150, 92], outline=(255, 127, 14), width=3)    # text
    m.save(mask)

    report.write_text(json.dumps({
        "semantic_classes": {
            "schema": "vemcad.render_semantic_classes",
            "schema_version": "0.1",
            "mask_kind": "candidate-renderer-semantic-class-buffer",
            "reference_semantics": "unknown",
            "palette": [
                {"name": "geometry", "rgb": "#1F77B4"},
                {"name": "text", "rgb": "#FF7F0E"},
                {"name": "dimension", "rgb": "#D62728"},
            ],
        }
    }), encoding="utf-8")
    return ref, cand, mask, report


def _semantic_class(report, name):
    return next(row for row in report.classes if row.name == name)


def test_semantic_class_diagnostics_use_candidate_class_buffer(tmp_path):
    ref, cand, mask, render_report = _semantic_fixture(tmp_path)

    report = compare_semantic_classes(
        ref, cand,
        candidate_mask_path=mask,
        render_report_path=render_report,
    )
    geometry = _semantic_class(report, "geometry")
    text = _semantic_class(report, "text")
    dimension = _semantic_class(report, "dimension")

    assert report.semantic
    assert report.diagnostic_kind == "candidate-semantic-class-ink"
    assert report.reference_semantics == "unknown"
    assert report.candidate_semantics == "candidate-renderer-semantic-class-buffer"
    assert report.aligned and report.comparable
    assert geometry.candidate_precision >= 0.97
    assert geometry.reference_coverage > 0.5
    assert text.candidate_precision >= 0.97
    assert text.reference_coverage > 0.05
    assert dimension.band == "absent"


def test_semantic_class_diagnostics_reject_mask_size_mismatch(tmp_path):
    ref, cand, mask, render_report = _semantic_fixture(tmp_path, mask_size=(210, 150))

    report = compare_semantic_classes(
        ref, cand,
        candidate_mask_path=mask,
        render_report_path=render_report,
    )

    assert report.semantic
    assert not report.comparable
    assert report.skip_reason == "semantic-mask-size-mismatch"


def test_blank_candidate_is_fallback(tmp_path):
    a = draw(tmp_path / "a.png")
    b = draw(tmp_path / "b.png", blank=True)
    r = compare(a, b)
    assert r.ink_iou == 0.0
    assert r.band == "fallback"


def test_both_blank_is_fallback_not_silent_pass(tmp_path):
    # Both-blank scores 1.0 numerically but a gated drawing being blank is a
    # failure — band must be fallback so it cannot silently pass the gate.
    a = draw(tmp_path / "a.png", blank=True)
    b = draw(tmp_path / "b.png", blank=True)
    r = compare(a, b)
    assert r.band == "fallback"


def _grid(path, n=20, bg=(255, 255, 255), ink=(0, 0, 0), size=(420, 300)):
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    d.rectangle([5, 5, size[0] - 5, size[1] - 5], outline=ink, width=2)
    for i in range(n):
        y = 15 + i * (size[1] - 30) // n
        d.line([10, y, size[0] - 10, y], fill=ink, width=1)
    im.save(path)
    return path


def test_dense_thin_line_self_compare_passes(tmp_path):
    # Regression for the NEAREST-resize false-FAIL: identical dense 1px line art
    # must score pass, not review (the self-baseline tier depends on this).
    a = _grid(tmp_path / "a.png"); b = _grid(tmp_path / "b.png")
    r = compare(a, b)
    assert r.ink_iou >= 0.97, r.ink_iou
    assert r.band == "pass"


def test_wrong_color_routed_to_review(tmp_path):
    # Grayscale ink-IoU is blind to color; a B4/layer-color regression (same
    # geometry, wrong ink color) must not silently pass.
    a = draw(tmp_path / "a.png", ink=(255, 255, 255), bg=(30, 30, 35))
    b = draw(tmp_path / "b.png", ink=(255, 0, 0), bg=(30, 30, 35))  # red ink
    r = compare(a, b)
    assert r.color_dist > 60.0
    assert r.band != "pass"   # demoted to review by color divergence


def _rect(path, box, bg=(30, 30, 35), ink=(255, 255, 255), size=(400, 400)):
    im = Image.new("RGB", size, bg)
    ImageDraw.Draw(im).rectangle(box, outline=ink, width=3)
    im.save(path)
    return path


def test_stretched_shape_routed_to_review(tmp_path):
    # Same outline, genuinely different ink-bbox aspect (a vertical-stretch
    # render bug). ink-IoU is high after bbox-crop; the aspect guard keeps it
    # out of 'pass'.
    a = _rect(tmp_path / "a.png", [40, 40, 360, 210])   # 320x170, aspect 1.88
    b = _rect(tmp_path / "b.png", [40, 40, 360, 300])   # 320x260, aspect 1.23
    r = compare(a, b)
    assert r.aspect_delta > 0.06, r.aspect_delta
    assert r.band != "pass"


def test_light_and_dark_bg_both_detect_ink(tmp_path):
    # ink mask is bg-relative, so a white-bg/black-ink pair scores like dark.
    a = draw(tmp_path / "a.png", bg=(255, 255, 255), ink=(0, 0, 0))
    b = draw(tmp_path / "b.png", bg=(255, 255, 255), ink=(0, 0, 0))
    r = compare(a, b)
    assert r.ink_iou >= 0.97


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
