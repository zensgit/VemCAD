"""Unit tests for sheet-window detection (P-sheet) — synthetic images, no render_cli."""

import numpy as np
from PIL import Image, ImageDraw

from app.sheet import detect_sheet_rect_px, detect_sheet_window, px_rect_to_world


def _img(tmp_path, name, W, H, frames, strays=()):
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)
    for box in frames:
        d.rectangle(box, outline=0, width=3)
    for box in strays:
        d.rectangle(box, fill=0)
    p = str(tmp_path / name)
    im.save(p)
    return p


def test_detects_frame_excludes_stray(tmp_path):
    # one 图框 + a stray blob OUTSIDE it (right of the frame) — the #020 class.
    p = _img(tmp_path, "frame_stray.png", 1000, 700, frames=[(100, 80, 720, 620)],
             strays=[(820, 300, 880, 360)])
    r = detect_sheet_rect_px(p)
    assert r is not None
    x0, y0, x1, y1 = r
    # the frame edges, NOT the stray at x≈820
    assert abs(x0 - 100) < 6 and abs(x1 - 720) < 6
    assert abs(y0 - 80) < 6 and abs(y1 - 620) < 6


def test_detects_light_outer_frame_not_dark_inner_frame(tmp_path):
    # Some corpus title blocks draw the outer sheet border in light green and the
    # printable margin in darker ink. The preview should prefer the printable
    # inner frame, so the outer sheet marker does not remain as "ink outside the
    # 图框" in the final image.
    im = Image.new("L", (1000, 700), 255)
    d = ImageDraw.Draw(im)
    d.rectangle((100, 80, 900, 640), outline=205, width=3)  # faint outer frame
    d.rectangle((150, 120, 850, 600), outline=0, width=3)   # dark inner margin
    p = str(tmp_path / "light_outer_frame.png")
    im.save(p)

    r = detect_sheet_rect_px(p)
    assert r is not None
    x0, y0, x1, y1 = r
    assert abs(x0 - 150) < 6 and abs(x1 - 850) < 6
    assert abs(y0 - 120) < 6 and abs(y1 - 600) < 6


def test_two_aligned_frames_union(tmp_path):
    # multi_frame: two side-by-side 图框 with aligned top/bottom -> union (correct
    # preview: both frames, no strays to exclude).
    p = _img(tmp_path, "multi.png", 1400, 700, frames=[(80, 80, 640, 620), (760, 80, 1320, 620)])
    r = detect_sheet_rect_px(p)
    assert r is not None
    x0, _, x1, _ = r
    assert abs(x0 - 80) < 8 and abs(x1 - 1320) < 8


def test_blank_returns_none(tmp_path):
    # no frame -> fail-safe (caller keeps extents).
    assert detect_sheet_rect_px(_img(tmp_path, "blank.png", 800, 600, frames=[])) is None


def test_tiny_frame_returns_none(tmp_path):
    # a frame far below min_frac of the canvas -> low confidence -> None.
    assert detect_sheet_rect_px(_img(tmp_path, "tiny.png", 1000, 700, frames=[(460, 320, 540, 390)])) is None


def test_px_rect_to_world_uses_report_mapping():
    # render_cli: screenX = worldX*scale + pan_x ; screenY = -worldY*scale + pan_y
    view = {"scale": 2.0, "pan_x": 100.0, "pan_y": 500.0}
    w = px_rect_to_world((100, 100, 300, 400), view)
    assert abs(w[0] - 0.0) < 1e-6 and abs(w[2] - 100.0) < 1e-6      # x: (100-100)/2, (300-100)/2
    assert abs(w[1] - 50.0) < 1e-6 and abs(w[3] - 200.0) < 1e-6     # y: (500-400)/2, (500-100)/2


def test_detect_sheet_window_endtoend(tmp_path):
    p = _img(tmp_path, "e2e.png", 1000, 700, frames=[(100, 80, 720, 620)], strays=[(820, 300, 880, 360)])
    view = {"scale": 2.0, "pan_x": 0.0, "pan_y": 700.0}
    w = detect_sheet_window(p, view)
    assert w is not None and w[2] < 800 / 2.0  # right edge maps to the frame (~360), not the stray
    # blank -> None passthrough
    assert detect_sheet_window(_img(tmp_path, "blank2.png", 800, 600, frames=[]), view) is None


# --- render_sheet_bytes two-pass orchestration (stubbed render_bytes + report) ---
import asyncio  # noqa: E402

from app.renderer import RenderParams, RenderService  # noqa: E402


class _StubSvc(RenderService):
    def __init__(self, probe_png, view_dict, *, nested_report=False):
        self._probe = probe_png
        self.windowed = []
        report = (
            {"render_cli_report": {"view": view_dict}}
            if nested_report
            else {"view": view_dict}
        )

        class _Cache:
            def get_report(_self, key):
                return report

        self.cache = _Cache()

    async def render_bytes(self, content, params, content_sha=None):
        from pathlib import Path
        if params.window is not None:
            self.windowed.append(params.window)
            return Path("/tmp/_sheet_win.png"), "wkey", False
        return Path(self._probe), "pkey", False


def _sheet_params():
    return RenderParams(fmt="png", width=1000, height=700, bg="white", view="sheet")


def test_render_sheet_detects_and_rewindows(tmp_path):
    p = _img(tmp_path, "probe.png", 1000, 700, frames=[(100, 80, 720, 620)], strays=[(820, 300, 880, 360)])
    svc = _StubSvc(p, {"scale": 2.0, "pan_x": 0.0, "pan_y": 700.0})
    asyncio.run(svc.render_sheet_bytes(b"x", _sheet_params(), content_sha="s"))
    assert svc.windowed, "expected a windowed re-render"
    assert svc.windowed[0][2] < 800 / 2.0  # framed to the 图框 right edge, not the stray


def test_render_sheet_reads_nested_render_cli_report_view(tmp_path):
    # Real cache reports wrap render_cli's view under render_cli_report.view. A
    # regression here makes every sheet render silently fall back to extents.
    p = _img(tmp_path, "probe_nested.png", 1000, 700, frames=[(100, 80, 720, 620)],
             strays=[(820, 300, 880, 360)])
    svc = _StubSvc(p, {"scale": 2.0, "pan_x": 0.0, "pan_y": 700.0}, nested_report=True)
    asyncio.run(svc.render_sheet_bytes(b"x", _sheet_params(), content_sha="s"))
    assert svc.windowed, "expected nested render_cli_report.view to drive sheet detection"


def test_render_sheet_failsafe_keeps_extents(tmp_path):
    p = _img(tmp_path, "blank3.png", 800, 600, frames=[])
    svc = _StubSvc(p, {"scale": 1.0, "pan_x": 0.0, "pan_y": 600.0})
    path, key, hit = asyncio.run(svc.render_sheet_bytes(b"x", _sheet_params(), content_sha="s"))
    assert not svc.windowed and str(path) == p  # no frame -> extents probe returned
