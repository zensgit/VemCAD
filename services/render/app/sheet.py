"""Sheet-window detection for plot-preview framing (P-sheet).

A drawing's raw extents (DXF $EXTMIN/$EXTMAX) include stray geometry OUTSIDE the
图框 (drawing border) — leftover construction marks, a far-away point, a detached
view. Rendering to extents/content_bbox then shows that junk and shrinks the real
sheet (see corpus #020 拖轮组件: strays on the right pushed the frame left).

This detects the 图框 rect from the RENDERED extents image, by projecting full-span
ink: the border is long lines spanning most of the canvas; strays are not full-span.
Projection (vs geometry inspection) is deliberate — the corpus 图框 is often a block
INSERT, which closed-LWPOLYLINE/long-line geometry detectors miss, and the in-repo
libdxfrw goldens are unreadable by ezdxf. The detector consumes render_cli's own
output, so it works on anything render_cli can render.

Policy: content_bbox/extents stays the diff/debug framing; this is the PREVIEW path.
Fail-safe: ambiguous / low-confidence / no-frame → return None (caller keeps extents),
because this becomes the default preview and a mis-fire is worse than today's extents.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from PIL import Image

WorldRect = Tuple[float, float, float, float]
PixelRect = Tuple[int, int, int, int]


def _ink_mask(gray: np.ndarray, thr: int) -> np.ndarray:
    """Ink = pixels far from the background (read from the frame border, so a dark
    or light render both work)."""
    bg = float(np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]]).mean())
    return (gray < bg - thr) if bg > 128 else (gray > bg + thr)


def detect_sheet_rect_px(
    png_path: str, span_frac: float = 0.4, ink_thr: int = 60, min_frac: float = 0.25
) -> Optional[PixelRect]:
    """Pixel rect (x0,y0,x1,y1) of the 图框 via full-span-ink projection, or None.

    A column/row is a frame edge when its ink spans >= span_frac of the canvas
    height/width; the outermost such columns/rows bound the sheet. Strays are
    isolated (not full-span) and fall outside. Returns None (fail-safe) when there
    is no confident frame: fewer than two spanning columns/rows, or the bounding
    rect covers < min_frac of the canvas (a sliver/inner box, not the sheet)."""
    gray = np.asarray(Image.open(png_path).convert("L"), dtype=float)
    H, W = gray.shape
    ink = _ink_mask(gray, ink_thr)
    vcols = np.where(ink.sum(axis=0) > span_frac * H)[0]
    hrows = np.where(ink.sum(axis=1) > span_frac * W)[0]
    if len(vcols) < 2 or len(hrows) < 2:
        return None
    x0, x1 = int(vcols.min()), int(vcols.max())
    y0, y1 = int(hrows.min()), int(hrows.max())
    if (x1 - x0) < min_frac * W or (y1 - y0) < min_frac * H:
        return None
    return (x0, y0, x1, y1)


def px_rect_to_world(rect: PixelRect, view: dict) -> WorldRect:
    """Invert pixels -> world using render_cli's ACTUAL mapping (report `view`:
    scale + pan + y_axis), never a reconstructed margin formula — drift there would
    re-admit strays at the edge or clip real content.

    render_cli: screenX = worldX*scale + pan_x ; screenY = -worldY*scale + pan_y."""
    s = float(view["scale"])
    px, py = float(view["pan_x"]), float(view["pan_y"])
    x_a = (rect[0] - px) / s
    x_b = (rect[2] - px) / s
    y_a = (py - rect[1]) / s  # y_axis "down": invert the negated-scale Y
    y_b = (py - rect[3]) / s
    return (min(x_a, x_b), min(y_a, y_b), max(x_a, x_b), max(y_a, y_b))


def detect_sheet_window(
    png_path: str, view: dict, span_frac: float = 0.4, ink_thr: int = 60, min_frac: float = 0.25
) -> Optional[WorldRect]:
    """World window (xmin,ymin,xmax,ymax) framing the 图框 for a clean preview, or
    None when no confident frame is found (caller keeps the extents framing)."""
    rect = detect_sheet_rect_px(png_path, span_frac=span_frac, ink_thr=ink_thr, min_frac=min_frac)
    if rect is None:
        return None
    return px_rect_to_world(rect, view)
