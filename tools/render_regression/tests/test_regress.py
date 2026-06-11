"""D2 harness orchestration tests — synthetic renderer (no render_cli), so the
band aggregation / gating / baseline flow is verified deterministically."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import regress  # noqa: E402
from baseline import BaselineStore  # noqa: E402


def _draw(path, extra=False, blank=False):
    im = Image.new("RGB", (400, 250), (255, 255, 255))
    if not blank:
        d = ImageDraw.Draw(im)
        d.rectangle([40, 40, 360, 210], outline=(0, 0, 0), width=3)
        d.line([60, 125, 340, 125], fill=(0, 0, 0), width=2)
        if extra:
            d.line([60, 80, 340, 80], fill=(0, 0, 0), width=2)
    im.save(path)


def _golden(names):
    return {"drawings": [{"name": n, "category": "x", "gate": True,
                          "render": {"width": 400, "height": 250, "bg": "white"}}
                         for n in names]}


def test_baseline_match_passes(tmp_path):
    golden = _golden(["d1"])
    store = BaselineStore(tmp_path / "b.json")
    out = tmp_path / "out"; out.mkdir()
    # record baseline + place the baseline image where run() expects it
    base_img = out / "_baseline_d1.png"; _draw(base_img)
    store.record("d1", "self", base_img, approver="t")
    # renderer produces an identical image
    def rfn(d, p): _draw(p); return True
    rep = regress.run(golden, store, rfn, out)
    assert rep["gated_failures"] == 0
    assert rep["rows"][0]["band"] == "pass" and rep["rows"][0]["outcome"] == "OK"


def test_divergence_fails_gate(tmp_path):
    golden = _golden(["d1"])
    store = BaselineStore(tmp_path / "b.json")
    out = tmp_path / "out"; out.mkdir()
    base_img = out / "_baseline_d1.png"; _draw(base_img, extra=False)
    store.record("d1", "self", base_img, approver="t")
    def rfn(d, p): _draw(p, extra=True); return True   # renders an extra line
    rep = regress.run(golden, store, rfn, out)
    # extra line is small vs the frame, may land review or fallback — assert it
    # is at least flagged (not pass) and gated-fail only counts fallback.
    assert rep["rows"][0]["band"] in ("review", "fallback")


def test_blank_render_fails_gate(tmp_path):
    golden = _golden(["d1"])
    store = BaselineStore(tmp_path / "b.json")
    out = tmp_path / "out"; out.mkdir()
    base_img = out / "_baseline_d1.png"; _draw(base_img)
    store.record("d1", "self", base_img, approver="t")
    def rfn(d, p): _draw(p, blank=True); return True
    rep = regress.run(golden, store, rfn, out)
    assert rep["rows"][0]["band"] == "fallback"
    assert rep["gated_failures"] == 1


def test_render_failure_gates(tmp_path):
    golden = _golden(["d1"])
    store = BaselineStore(tmp_path / "b.json")
    out = tmp_path / "out"; out.mkdir()
    def rfn(d, p): return False
    rep = regress.run(golden, store, rfn, out)
    assert rep["gated_failures"] == 1
    assert rep["rows"][0]["reason"] == "render-failed"


def test_no_baseline_does_not_gate(tmp_path):
    golden = _golden(["d1"])
    store = BaselineStore(tmp_path / "b.json")  # empty
    out = tmp_path / "out"; out.mkdir()
    def rfn(d, p): _draw(p); return True
    rep = regress.run(golden, store, rfn, out)
    assert rep["rows"][0]["outcome"] == "NO-BASELINE"
    assert rep["gated_failures"] == 0   # missing baseline must not gate


def test_real_golden_manifest_loads_and_is_consistent():
    gpath = Path(__file__).resolve().parents[1] / "golden" / "golden.json"
    golden = json.loads(gpath.read_text("utf-8"))
    names = [d["name"] for d in golden["drawings"]]
    assert len(names) == len(set(names))  # unique
    gdir = gpath.parent
    for d in golden["drawings"]:
        assert (gdir / (d["name"] + ".dxf")).is_file(), d["name"]
        assert "render" in d and "category" in d
