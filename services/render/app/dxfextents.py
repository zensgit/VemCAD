"""DXF HEADER extents parsing — the FALLBACK source for the /diff common-window.

The version-diff §5 guard skips revisions whose *outer extents* differ: rendered
to their own extents they land in different world->pixel mappings, so the engine
refuses to diff them (skip_reason="view-space-mismatch"). The common-window
upgrade renders BOTH in a shared world window (their union) so even
extents-changing revisions diff cleanly.

PRIMARY source = render_cli's real-geometry `content_bbox` (CADGameFusion #392,
core::contentBounds), consumed in diffrunner. This module is the FALLBACK only,
used when content_bbox is unavailable (a render_cli predating #392). It parses
$EXTMIN/$EXTMAX (group codes 10=x, 20=y) in pure Python — no render_cli needed.

Returns None when the header lacks usable extents (caller then renders per-
extents, no window).

KNOWN LIMITATION (fallback path only): $EXTMIN/$EXTMAX are author-app-maintained
and can be STALE — present but smaller than the actual geometry. Used as a HARD
window they would clip out-of-extent geometry. We only detect *missing* extents
(fall back to per-extents); we do NOT detect *stale-present* ones. This risk
applies ONLY to this fallback — the primary content_bbox path is real geometry
and does not clip (it is unioned from render_cli's content_bbox, which exceeds a
stale header; proven by the stale_small_header golden e2e).
"""

from typing import Optional, Tuple

# (xmin, ymin, xmax, ymax) in DXF world coordinates.
Rect = Tuple[float, float, float, float]


def _read_point(lines, start: int) -> Optional[Tuple[float, float]]:
    """Given the index of an $EXTMIN/$EXTMAX *value* line, read the immediately
    following group-code/value pairs (10=x, 20=y, optional 30=z) and return
    (x, y). Stops at the first non-coordinate group code (e.g. the next `9`
    HEADER var or a `0` section marker)."""
    x = y = None
    k = start + 1
    while k + 1 < len(lines):
        code = lines[k].strip()
        if code in ("10", "20", "30"):
            try:
                val = float(lines[k + 1].strip())
            except ValueError:
                return None
            if code == "10":
                x = val
            elif code == "20":
                y = val
            k += 2
            continue
        break
    if x is None or y is None:
        return None
    return (x, y)


def parse_dxf_extents(content: bytes) -> Optional[Rect]:
    """Parse $EXTMIN/$EXTMAX from a DXF byte stream. Returns the world rect
    (xmin, ymin, xmax, ymax) or None if either var is absent/unparseable or the
    rect is degenerate (xmax<=xmin or ymax<=ymin). Never raises."""
    try:
        lines = content.decode("latin-1").splitlines()
    except Exception:
        return None
    emin = emax = None
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if s == "$EXTMIN":
            emin = _read_point(lines, idx)
        elif s == "$EXTMAX":
            emax = _read_point(lines, idx)
        if emin is not None and emax is not None:
            break
    if emin is None or emax is None:
        return None
    xmin, ymin = emin
    xmax, ymax = emax
    if xmax <= xmin or ymax <= ymin:
        return None
    return (xmin, ymin, xmax, ymax)


def union_window(a: Rect, b: Rect) -> Rect:
    """The smallest world rect containing both a and b (each xmin,ymin,xmax,ymax)."""
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def extents_differ(a: Rect, b: Rect, eps: float = 1e-6) -> bool:
    """True if the two extent rects differ by more than eps on any edge -- i.e.
    the pair would otherwise render in mismatched view-space."""
    return any(abs(a[i] - b[i]) > eps for i in range(4))
