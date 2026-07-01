"""Version visual diff (L1 flagship engine). Given two renders of a drawing
(Rev A = reference, Rev B = candidate), align them (reusing the D2 comparator's
binarize → ink-bbox crop → common-canvas → small-shift alignment) and classify
every ink pixel as unchanged / added / removed, emitting a 3-colour highlight
overlay PNG + a change summary.

This is the engine behind the billable "图纸版本可视化对比" module:审图 sees
exactly what changed between revisions. Pure image-in / overlay-out — no
rendering here (the render service produces the two inputs). Verified with
synthetic PIL pairs (deterministic, no live renderer).

Classes (dilation-tolerant, so ≤tol-px AA/hinting jitter is NOT flagged):
  unchanged = ref ink with a candidate ink pixel within tol  → grey
  removed   = ref ink with NO candidate ink within tol       → red   (in A, gone in B)
  added     = candidate ink with NO ref ink within tol       → green (new in B)

Orientation is fixed (A = old, B = new), so the summary is deliberately NOT
swap-symmetric: `changed_fraction` normalises by (unchanged+added+removed) —
i.e. ref ink plus genuinely-new cand ink — not a true pixel union. One tolerance
consequence to keep in mind when reading overlays: a within-tol line *thickening*
reads as no-change, while *thinning* reads as a small removal. That matches the
tolerant philosophy (we suppress sub-tol jitter), and is fine for revision review.

§5 view-space: the two renders must share view-space, not just bg/colour. The
legacy per-extents image path does NOT assume that — when the two ink bboxes
disagree in aspect beyond ASPECT_TOL, it returns comparable=False with
skip_reason="view-space-mismatch" instead of stretching one render onto the
other. The service-level /diff common-window path renders both revisions in a
shared world window and calls this engine with shared_view=True; that mode keeps
the common pixel grid and supports extents-changing revisions without silently
re-centering them.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image

from compare import (  # reuse the D2 alignment + ink extraction
    ASPECT_TOL,
    CANVAS,
    DILATE_TOL,
    _best_shift,
    _crop_resize,
    _dilate,
    _ink_bbox,
    _ink_mask,
    _load_rgb,
    _shift,
)

# Overlay colours (RGB) on a white background.
COL_BG = (255, 255, 255)
COL_UNCHANGED = (170, 170, 170)   # grey
COL_REMOVED = (220, 30, 30)       # red  — in ref (A), absent in candidate (B)
COL_ADDED = (30, 160, 30)         # green — new in candidate (B)


@dataclass
class DiffResult:
    aligned: bool
    dx: int
    dy: int
    unchanged_px: int
    added_px: int
    removed_px: int
    changed_fraction: float       # (added+removed) / (unchanged+added+removed) ∈ [0,1]
    canvas: Tuple[int, int]
    overlay_path: Optional[str]
    comparable: bool
    skip_reason: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["canvas"] = list(self.canvas)
        return d


def _classify(ref: np.ndarray, cand: np.ndarray, tol: int):
    """Return (unchanged, removed, added) boolean masks on aligned inputs.
    Named for the ink whose *reach* (dilation) each test consults: a ref pixel
    is unchanged/removed by whether the CANDIDATE reaches it; a cand pixel is
    added by whether the REFERENCE never reached it."""
    cand_reach = _dilate(cand, tol)   # where candidate ink reaches (± tol)
    ref_reach = _dilate(ref, tol)     # where reference ink reaches (± tol)
    unchanged = np.logical_and(ref, cand_reach)                # ref ink the candidate still covers
    removed = np.logical_and(ref, np.logical_not(cand_reach))  # ref ink the candidate no longer reaches
    added = np.logical_and(cand, np.logical_not(ref_reach))    # cand ink the reference never reached
    return unchanged, removed, added


def _render_overlay(unchanged, removed, added, canvas: Tuple[int, int]) -> Image.Image:
    h, w = canvas[1], canvas[0]
    img = np.full((h, w, 3), COL_BG, dtype=np.uint8)
    # Paint unchanged first, then changes on top so a changed pixel always wins.
    img[unchanged] = COL_UNCHANGED
    img[removed] = COL_REMOVED
    img[added] = COL_ADDED
    return Image.fromarray(img, mode="RGB")


def _union_bbox(*masks):
    """Smallest (r0, r1, c0, c1) covering the ink bbox of every given mask, or
    None if all masks are blank."""
    boxes = [bb for bb in (_ink_bbox(m) for m in masks) if bb is not None]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), max(b[1] for b in boxes),
            min(b[2] for b in boxes), max(b[3] for b in boxes))


def _diff_shared_view(ma, mb, tol: int, out_path: Optional[Path]) -> DiffResult:
    """Diff two renders KNOWN to share view-space (same world window + pixel
    size — the /diff common-window path). Crucially, unlike the per-extents
    path, this does NOT crop each render to its OWN ink bbox (which discards
    absolute frame position and would defeat the shared window) and does NOT
    apply the aspect guard. Both masks are cropped to the SAME union bbox, so a
    revision that *moved* or *grew* geometry within the shared window is scored
    as a real change instead of being re-centred into a false 'no change'."""
    if ma.shape != mb.shape:
        # A shared window at identical width/height must yield identical pixel
        # dims. If not, the caller's shared-view claim is broken — flag, don't guess.
        canvas = (mb.shape[1], mb.shape[0])
        return DiffResult(False, 0, 0, 0, 0, 0, 0.0, canvas, None,
                          False, "shared-view-shape-mismatch")
    ub = _union_bbox(ma, mb)
    if ub is None:
        canvas = (ma.shape[1], ma.shape[0])
        return DiffResult(False, 0, 0, 0, 0, 0, 0.0, canvas, None, True, "both-blank")
    r0, r1, c0, c1 = ub
    ca = ma[r0:r1, c0:c1]
    cb = mb[r0:r1, c0:c1]
    canvas = (c1 - c0, r1 - r0)  # (w, h)

    dx, dy = _best_shift(ca, cb)   # absorb ≤tol AA/hinting jitter only
    cb = _shift(cb, dy, dx)

    unchanged, removed, added = _classify(ca, cb, tol)
    u, r, a = int(unchanged.sum()), int(removed.sum()), int(added.sum())
    union = u + r + a
    changed_fraction = (r + a) / union if union else 0.0

    written: Optional[str] = None
    if out_path is not None:
        _render_overlay(unchanged, removed, added, canvas).save(str(out_path))
        written = str(out_path)
    return DiffResult(True, dx, dy, u, a, r, round(changed_fraction, 4),
                      canvas, written, True, "")


def diff_overlay(
    ref_path: Path,
    cand_path: Path,
    *,
    canvas: Tuple[int, int] = CANVAS,
    tol: int = DILATE_TOL,
    out_path: Optional[Path] = None,
    comparable: bool = True,
    skip_reason: str = "",
    shared_view: bool = False,
) -> DiffResult:
    """Produce a version-diff overlay + summary. `comparable` is set False by
    the caller when bg / color_mapping differ (the two renders must share them
    — same §5 rule as compare()).

    `shared_view=True` means the caller guaranteed both renders share view-space
    (the /diff common-window upgrade: both rendered in the union world window).
    Then the per-extents independent bbox crop + aspect guard are bypassed and
    both renders are diffed in their common pixel grid, so extents-changing /
    geometry-moving revisions diff cleanly instead of being skipped or
    re-centred into a false match."""
    if not comparable:
        return DiffResult(False, 0, 0, 0, 0, 0, 0.0, canvas, None,
                          False, skip_reason or "not-comparable")

    ma = _ink_mask(_load_rgb(Path(ref_path)).mean(axis=2))
    mb = _ink_mask(_load_rgb(Path(cand_path)).mean(axis=2))
    if shared_view:
        return _diff_shared_view(ma, mb, tol, out_path)
    ca, aspa = _crop_resize(ma, canvas)
    cb, aspb = _crop_resize(mb, canvas)
    if ca is None and cb is None:
        return DiffResult(False, 0, 0, 0, 0, 0, 0.0, canvas, None, True, "both-blank")
    # §5 view-space guard. Both renders are produced at identical params, which
    # secures bg + colour-mapping — but each is fit to its OWN extents, so a
    # revision that grows/shrinks the drawing's outer extents yields mismatched
    # ink bboxes. Stretching one onto the other would paint unchanged geometry
    # as spurious add/remove, so flag it (skip-and-flag) rather than lie. A
    # fully-blank side is a real all-added / all-removed revision, NOT a
    # mismatch (aspa/aspb is None there), so it is excluded from this check.
    if aspa and aspb and abs(1.0 - (aspb / aspa)) > ASPECT_TOL:
        return DiffResult(False, 0, 0, 0, 0, 0, 0.0, canvas, None,
                          False, "view-space-mismatch")
    if ca is None:
        ca = np.zeros((canvas[1], canvas[0]), dtype=bool)
    if cb is None:
        cb = np.zeros((canvas[1], canvas[0]), dtype=bool)

    dx, dy = _best_shift(ca, cb)
    cb = _shift(cb, dy, dx)

    unchanged, removed, added = _classify(ca, cb, tol)
    u, r, a = int(unchanged.sum()), int(removed.sum()), int(added.sum())
    union = u + r + a
    changed_fraction = (r + a) / union if union else 0.0

    written: Optional[str] = None
    if out_path is not None:
        _render_overlay(unchanged, removed, added, canvas).save(str(out_path))
        written = str(out_path)

    return DiffResult(True, dx, dy, u, a, r, round(changed_fraction, 4),
                      canvas, written, True, "")


def main(argv=None) -> int:
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(prog="diff", description="Render version visual diff overlay.")
    ap.add_argument("ref", type=Path, help="Rev A (reference) render")
    ap.add_argument("cand", type=Path, help="Rev B (candidate) render")
    ap.add_argument("--out", type=Path, help="overlay PNG output path")
    ap.add_argument("--tol", type=int, default=DILATE_TOL)
    args = ap.parse_args(argv)
    res = diff_overlay(args.ref, args.cand, tol=args.tol, out_path=args.out)
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
