"""Common-window (§5 view-space) upgrade — unit tests.

Covers the locally-verifiable surface with NO render_cli binary:
  * DXF HEADER extents parsing ($EXTMIN/$EXTMAX)
  * union-window math + extents-differ predicate
  * RenderParams.windowed (validation, cache-key impact, as_dict)
  * RenderService._build_argv (--window plumbing)
  * DiffService.diff_bytes orchestration via the renderer-stub pattern
    (the real diff engine runs; numpy/Pillow are present in dev)

The actual DXF -> render_cli -> overlay pixel path stays binary-gated in the
CI image (test_diff_api.py::needs_render_cli); here we prove that when two
revisions' extents differ, both renders are driven with the union window.
"""

import asyncio
from pathlib import Path

from PIL import Image, ImageDraw

import app.diffrunner as diffrunner
from app.cache import cache_key
from app.diffrunner import DiffService
from app.dxfextents import extents_differ, parse_dxf_extents, union_window
from app.renderer import ParamError, RenderParams


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _dxf(extmin, extmax) -> bytes:
    """Minimal DXF HEADER carrying $EXTMIN/$EXTMAX (group codes 10=x, 20=y)."""
    lines = ["0", "SECTION", "2", "HEADER"]
    if extmin is not None:
        lines += ["9", "$EXTMIN", "10", str(extmin[0]), "20", str(extmin[1])]
    if extmax is not None:
        lines += ["9", "$EXTMAX", "10", str(extmax[0]), "20", str(extmax[1])]
    lines += ["0", "ENDSEC", "0", "EOF", ""]
    return "\n".join(lines).encode("ascii")


def _inked_png(path: Path) -> Path:
    im = Image.new("RGB", (420, 300), (255, 255, 255))
    ImageDraw.Draw(im).rectangle([20, 20, 400, 280], outline=(0, 0, 0), width=3)
    im.save(path)
    return path


def _box_png(path: Path, x0, y0, x1, y1) -> Path:
    """A box at an explicit position on a fixed-size canvas (simulates a render
    in a shared window — the canvas size is constant, the geometry moves)."""
    im = Image.new("RGB", (420, 300), (255, 255, 255))
    ImageDraw.Draw(im).rectangle([x0, y0, x1, y1], outline=(0, 0, 0), width=3)
    im.save(path)
    return path


class _FakeCache:
    def __init__(self):
        self.reports = {}
        self.artifacts = {}

    def get_report(self, key):
        return self.reports.get(key)

    def get(self, key, fmt):
        return self.artifacts.get((key, fmt))

    def put(self, key, fmt, path, report):
        self.artifacts[(key, fmt)] = Path(path)
        self.reports[key] = report
        return Path(path)

    def put_report_only(self, key, report):
        self.reports[key] = report


class _FakeSvc:
    """Stub RenderService: records the params of every render and returns a
    pre-baked PNG (per-content so A and B can differ), so DiffService runs the
    real diff engine with no binary."""

    def __init__(self, default_png: Path, by_content=None, content_bbox=None):
        self.cache = _FakeCache()
        self.cli_sha = "clisha"
        self.font_fp = "fontfp"
        self.default_png = default_png
        self.by_content = by_content or {}
        # content bytes -> (xmin,ymin,xmax,ymax): when set, the render's report
        # carries view.content_bbox (simulates render_cli #392).
        self.content_bbox = content_bbox or {}
        self.received = []

    async def render_bytes(self, content, params, content_sha=None):
        self.received.append(params)
        key = "rk-%s-%s" % (content_sha or id(content), params.view)
        cb = self.content_bbox.get(content)
        if cb is not None:
            self.cache.reports[key] = {"render_cli_report": {"view": {"content_bbox": {
                "min_x": cb[0], "min_y": cb[1], "max_x": cb[2], "max_y": cb[3]}}}}
        return self.by_content.get(content, self.default_png), key, False


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# DXF extents parsing
# --------------------------------------------------------------------------

def test_parse_extents_from_fixture():
    content = (Path(__file__).parent / "fixtures" / "block_ellipse.dxf").read_bytes()
    assert parse_dxf_extents(content) == (0.0, 0.0, 200.0, 100.0)


def test_parse_extents_synthetic():
    assert parse_dxf_extents(_dxf((1.0, 2.0), (11.0, 7.0))) == (1.0, 2.0, 11.0, 7.0)


def test_parse_extents_missing_returns_none():
    assert parse_dxf_extents(_dxf((0.0, 0.0), None)) is None
    assert parse_dxf_extents(b"not a dxf at all") is None


def test_parse_extents_degenerate_returns_none():
    # xmax <= xmin  /  ymax <= ymin -> unusable, fall back to per-extents.
    assert parse_dxf_extents(_dxf((5.0, 0.0), (5.0, 10.0))) is None
    assert parse_dxf_extents(_dxf((0.0, 9.0), (10.0, 9.0))) is None


# --------------------------------------------------------------------------
# union + differ
# --------------------------------------------------------------------------

def test_union_window():
    assert union_window((0, 0, 10, 10), (5, -5, 20, 8)) == (0, -5, 20, 10)


def test_extents_differ():
    assert extents_differ((0, 0, 10, 10), (0, 0, 20, 10)) is True
    assert extents_differ((0, 0, 10, 10), (0, 0, 10, 10)) is False
    assert extents_differ((0, 0, 10, 10), (0, 0, 10, 10 + 1e-9)) is False  # within eps


# --------------------------------------------------------------------------
# RenderParams.windowed
# --------------------------------------------------------------------------

def test_windowed_sets_view_and_window():
    p = RenderParams.parse("png", 800, 600, "dark", "extents")
    w = p.windowed((0.0, 0.0, 200.0, 100.0))
    assert w.view == "window"
    assert w.window == (0.0, 0.0, 200.0, 100.0)
    assert p.window is None  # original untouched (frozen)


def test_windowed_changes_cache_key_and_as_dict():
    p = RenderParams.parse("png", 800, 600, "dark", "extents")
    w = p.windowed((0.0, 0.0, 200.0, 100.0))
    assert "window" not in p.as_dict()          # non-windowed key unchanged
    assert w.as_dict()["window"] == [0.0, 0.0, 200.0, 100.0]
    k0 = cache_key("sha", p.as_dict(), "cli", "fp")
    k1 = cache_key("sha", w.as_dict(), "cli", "fp")
    assert k0 != k1


def test_windowed_rejects_degenerate_and_nonfinite():
    p = RenderParams.parse("png", 800, 600, "dark", "extents")
    for bad in [(0, 0, 0, 10), (0, 0, 10, 0), (0, 0, -1, 10), (0, 0, 1, 2, 3)]:
        try:
            p.windowed(bad)
            assert False, "expected ParamError for %r" % (bad,)
        except ParamError:
            pass
    try:
        p.windowed((0.0, 0.0, float("inf"), 10.0))
        assert False, "expected ParamError for inf"
    except ParamError:
        pass


# --------------------------------------------------------------------------
# argv plumbing
# --------------------------------------------------------------------------

def test_build_argv_includes_window_when_set():
    from app.renderer import RenderService
    p = RenderParams.parse("png", 800, 600, "white", "extents").windowed((0.0, 0.0, 200.0, 100.0))
    argv = RenderService._build_argv("render_cli", "in.dxf", "out.png", p, "rep.json", None)
    assert "--window" in argv
    # repr-based (round-trippable, no %g 6-sig-fig truncation/clipping).
    assert argv[argv.index("--window") + 1] == "0.0,0.0,200.0,100.0"


def test_build_argv_no_window_by_default():
    from app.renderer import RenderService
    p = RenderParams.parse("png", 800, 600, "white", "extents")
    argv = RenderService._build_argv("render_cli", "in.dxf", "out.png", p, "rep.json", "/fonts")
    assert "--window" not in argv
    assert argv[argv.index("--font-dir") + 1] == "/fonts"


# --------------------------------------------------------------------------
# DiffService orchestration (stubbed renderer, real diff engine)
# --------------------------------------------------------------------------

def test_diff_window_from_content_bbox(tmp_path):
    # v2 primary path: the window comes from REAL geometry (render_cli
    # content_bbox), NOT the header. Headers here are deliberately stale-small
    # (50/60) while content_bbox is the real 100/200 — the window must use the
    # latter, proving v2 ignores the stale header.
    a = _dxf((0.0, 0.0), (50.0, 50.0))
    b = _dxf((0.0, 0.0), (60.0, 50.0))
    png_a = _box_png(tmp_path / "a.png", 40, 110, 160, 190)
    png_b = _box_png(tmp_path / "b.png", 40, 110, 380, 190)
    svc = _FakeSvc(png_a, by_content={a: png_a, b: png_b},
                   content_bbox={a: (0.0, 0.0, 100.0, 100.0),
                                 b: (0.0, 0.0, 200.0, 100.0)})
    diffsvc = DiffService(svc)

    params = RenderParams.parse("png", 800, 600, "dark", "extents")
    overlay, summary, key, hit = _run(diffsvc.diff_bytes(a, b, params))

    # 2 extents renders (read content_bbox) + 2 windowed re-renders.
    assert len(svc.received) == 4
    assert svc.received[0].window is None and svc.received[1].window is None  # extents pass
    # Union of the CONTENT_BBOXes (0,0,200,100) — not the headers (50/60).
    assert svc.received[2].window == (0.0, 0.0, 200.0, 100.0)
    assert svc.received[3].window == (0.0, 0.0, 200.0, 100.0)
    assert summary.get("common_window") == [0.0, 0.0, 200.0, 100.0]
    assert summary.get("window_source") == "content_bbox"
    assert summary["comparable"] is True
    assert summary.get("skip_reason", "") == ""
    assert overlay is not None
    assert summary["added_px"] > 0
    assert summary["changed_fraction"] > 0.0


def test_diff_window_from_header_fallback(tmp_path):
    # Fallback path: no content_bbox in the reports (render_cli predating #392)
    # -> fall back to DXF header extents; window_source = "header".
    a = _dxf((0.0, 0.0), (100.0, 100.0))
    b = _dxf((0.0, 0.0), (200.0, 100.0))
    png_a = _box_png(tmp_path / "a.png", 40, 110, 160, 190)
    png_b = _box_png(tmp_path / "b.png", 40, 110, 380, 190)
    svc = _FakeSvc(png_a, by_content={a: png_a, b: png_b})  # no content_bbox

    diffsvc = DiffService(svc)
    params = RenderParams.parse("png", 800, 600, "dark", "extents")
    overlay, summary, key, hit = _run(diffsvc.diff_bytes(a, b, params))

    assert len(svc.received) == 4
    assert svc.received[2].window == (0.0, 0.0, 200.0, 100.0)  # union of headers
    assert summary.get("window_source") == "header"
    assert summary.get("common_window") == [0.0, 0.0, 200.0, 100.0]
    assert summary["comparable"] is True
    assert overlay is not None
    assert summary["added_px"] > 0


def test_diff_window_engaged_when_content_bbox_equal_but_headers_differ(tmp_path):
    # P1 regression: EQUAL content_bbox must STILL engage the common window when
    # the headers differ / one is stale-small. Here both real bboxes are
    # (0,0,200,100) but A's HEADER is stale-small (0,0,50,50) while B's is correct
    # (0,0,200,100) — A's per-extents base render would clip to the corner. The
    # window must still engage from content_bbox (not be skipped because the two
    # bboxes are equal), so both render in the same real-geometry window and the
    # identical geometry diffs as ~no change instead of being mis-diffed/skipped.
    a = _dxf((0.0, 0.0), (50.0, 50.0))     # stale-small header
    b = _dxf((0.0, 0.0), (200.0, 100.0))   # correct header
    png = _box_png(tmp_path / "same.png", 40, 110, 380, 190)  # identical render both sides
    svc = _FakeSvc(png, by_content={a: png, b: png},
                   content_bbox={a: (0.0, 0.0, 200.0, 100.0),
                                 b: (0.0, 0.0, 200.0, 100.0)})  # EQUAL real bbox
    diffsvc = DiffService(svc)
    params = RenderParams.parse("png", 800, 600, "dark", "extents")
    overlay, summary, key, hit = _run(diffsvc.diff_bytes(a, b, params))

    # Window engaged from content_bbox despite equal bboxes (2 extents + 2 windowed).
    assert len(svc.received) == 4
    assert svc.received[2].window == (0.0, 0.0, 200.0, 100.0)
    assert svc.received[3].window == (0.0, 0.0, 200.0, 100.0)
    assert summary.get("window_source") == "content_bbox"
    assert summary.get("common_window") == [0.0, 0.0, 200.0, 100.0]
    # Identical geometry in the shared window -> comparable, ~no change.
    assert summary["comparable"] is True
    assert summary["changed_fraction"] < 0.02


def test_diff_no_window_when_extents_equal(tmp_path):
    png = _inked_png(tmp_path / "r.png")
    svc = _FakeSvc(png)
    diffsvc = DiffService(svc)
    same = ((0.0, 0.0), (100.0, 100.0))
    params = RenderParams.parse("png", 800, 600, "dark", "extents")
    _run(diffsvc.diff_bytes(_dxf(*same), _dxf(*same), params))
    assert svc.received[0].window is None
    assert svc.received[1].window is None


def test_diff_no_window_when_extents_missing(tmp_path):
    png = _inked_png(tmp_path / "r.png")
    svc = _FakeSvc(png)
    diffsvc = DiffService(svc)
    no_ext = _dxf(None, None)
    has_ext = _dxf((0.0, 0.0), (200.0, 100.0))
    params = RenderParams.parse("png", 800, 600, "dark", "extents")
    _run(diffsvc.diff_bytes(no_ext, has_ext, params))
    # Either side lacking usable extents -> fall back to per-extents (no window).
    assert svc.received[0].window is None
    assert svc.received[1].window is None
