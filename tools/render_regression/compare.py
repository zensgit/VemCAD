"""D2 regression comparator — align two renders of the same drawing and score
their similarity, following the May fidelity-workflow method (binarize → ink
bbox crop → common canvas → small translation search) and the Phase-1 plan §5
scoring semantics (pixel-class gate with dilation tolerance + SSIM as an
informational metric).

Pure image-in / score-out: no rendering here (render_batch / the service /
CI invoke render_cli). Unit-tested with synthetic PIL image pairs so the
alignment + scoring are verified deterministically without a live renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image


def _dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    """4-connected binary dilation, `iterations` steps (Manhattan radius).
    Pure numpy — avoids a scipy.ndimage dependency."""
    m = mask
    for _ in range(max(0, iterations)):
        d = m.copy()
        d[1:, :] |= m[:-1, :]
        d[:-1, :] |= m[1:, :]
        d[:, 1:] |= m[:, :-1]
        d[:, :-1] |= m[:, 1:]
        m = d
    return m

# §5 capture-method trust: only offscreen-render / plot-raster scores may gate
# CI; viewport-capture is advisory, dwg-thumbnail is record-only.
TRUST = {
    "offscreen-render": "gate",
    "plot-raster": "gate",
    "viewport-capture": "advisory",
    "dwg-thumbnail": "record",
}

# Score bands → action (thresholds calibrated from the golden set; v0 defaults).
# Keyed on the gate metric (geometry ink-IoU). Bands are [low, high).
BANDS = [
    (0.97, 1.01, "pass"),
    (0.90, 0.97, "review"),       # human-review queue
    (0.00, 0.90, "fallback"),     # serve ref-render fallback / flag regression
]


def band_for(score: float) -> str:
    for lo, hi, action in BANDS:
        if lo <= score < hi:
            return action
    return "fallback"


@dataclass
class CompareResult:
    aligned: bool
    dx: int
    dy: int
    geometry_ink_iou: float      # gate metric (dilation-tolerant ink overlap)
    ssim: float                  # informational
    ink_a: float                 # ink fraction of image A (reference)
    ink_b: float                 # ink fraction of image B (candidate)
    canvas: Tuple[int, int]
    comparable: bool             # §5: bg/color_mapping/view-space aligned
    skip_reason: str
    trust: str                   # gate | advisory | record
    band: str                    # pass | review | fallback

    def to_dict(self) -> dict:
        d = asdict(self)
        d["canvas"] = list(self.canvas)
        return d


def _to_gray(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L"), dtype=np.float64)


def _ink_mask(gray: np.ndarray) -> np.ndarray:
    """Ink = pixels far from the dominant (background) level. Works for both
    dark-bg (light ink) and light-bg (dark ink) by measuring |deviation| from
    the modal background value."""
    hist = np.bincount(gray.astype(np.uint8).ravel(), minlength=256)
    bg = float(np.argmax(hist))
    return np.abs(gray - bg) > 32.0  # 1/8 of full range — robust to AA fringes


def _ink_bbox(mask: np.ndarray):
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return None
    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]
    return int(r0), int(r1) + 1, int(c0), int(c1) + 1


def _crop_resize(mask: np.ndarray, canvas: Tuple[int, int]) -> Optional[np.ndarray]:
    bb = _ink_bbox(mask)
    if bb is None:
        return None
    r0, r1, c0, c1 = bb
    sub = Image.fromarray((mask[r0:r1, c0:c1] * 255).astype(np.uint8))
    sub = sub.resize((canvas[0], canvas[1]), Image.NEAREST)
    return np.asarray(sub) > 127


def _best_shift(a: np.ndarray, b: np.ndarray, search: int = 3):
    """Small integer translation search maximizing dilation-tolerant overlap."""
    best, bdx, bdy = -1.0, 0, 0
    a_dil = _dilate(a, 2)
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            bb = np.roll(np.roll(b, dy, axis=0), dx, axis=1)
            inter = np.logical_and(a_dil, bb).sum()
            denom = bb.sum()
            score = inter / denom if denom else 0.0
            if score > best:
                best, bdx, bdy = score, dx, dy
    return bdx, bdy


def _ink_iou_tol(a: np.ndarray, b: np.ndarray, tol: int = 2) -> float:
    """Symmetric dilation-tolerant IoU: ink in A counts as matched if a B ink
    pixel is within `tol`, and vice versa. Absorbs ≤tol-px AA/hinting jitter
    (the dominant noise between two correct renders / vs an AutoCAD ref)."""
    a_d = _dilate(a, tol)
    b_d = _dilate(b, tol)
    a_matched = np.logical_and(a, b_d).sum()
    b_matched = np.logical_and(b, a_d).sum()
    a_tot, b_tot = a.sum(), b.sum()
    if a_tot == 0 and b_tot == 0:
        return 1.0
    if a_tot == 0 or b_tot == 0:
        return 0.0
    # F1-like: harmonic mean of recall (A matched) and precision (B matched).
    recall = a_matched / a_tot
    precision = b_matched / b_tot
    if recall + precision == 0:
        return 0.0
    return 2 * recall * precision / (recall + precision)


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Global SSIM (single-window) on the aligned ink masks as float images —
    informational only (the plan: SSIM weakly informative on 1-px line art)."""
    af = a.astype(np.float64); bf = b.astype(np.float64)
    mu_a, mu_b = af.mean(), bf.mean()
    va, vb = af.var(), bf.var()
    cov = ((af - mu_a) * (bf - mu_b)).mean()
    c1, c2 = (0.01) ** 2, (0.03) ** 2
    return float(((2 * mu_a * mu_b + c1) * (2 * cov + c2)) /
                 ((mu_a ** 2 + mu_b ** 2 + c1) * (va + vb + c2)))


def compare(
    ref_path: Path,
    cand_path: Path,
    *,
    canvas: Tuple[int, int] = (1200, 850),
    tol: int = 2,
    comparable: bool = True,
    skip_reason: str = "",
    capture_method: str = "offscreen-render",
) -> CompareResult:
    """Compare a candidate render against a reference. `comparable` must be set
    False by the caller when bg / color_mapping / view-space differ (§5:
    skip-and-flag); `capture_method` sets the trust weight."""
    trust = TRUST.get(capture_method, "record")
    ga, gb = _to_gray(Path(ref_path)), _to_gray(Path(cand_path))
    ma, mb = _ink_mask(ga), _ink_mask(gb)
    ink_a = float(ma.mean()); ink_b = float(mb.mean())

    if not comparable:
        return CompareResult(False, 0, 0, 0.0, 0.0, ink_a, ink_b, canvas,
                             False, skip_reason or "not-comparable", trust, "review")

    ca, cb = _crop_resize(ma, canvas), _crop_resize(mb, canvas)
    if ca is None or cb is None:
        # One side has no ink → only a match if both are blank.
        score = 1.0 if (ca is None and cb is None) else 0.0
        return CompareResult(False, 0, 0, score, 0.0, ink_a, ink_b, canvas,
                             True, "blank-side" if score == 0.0 else "", trust,
                             band_for(score))

    dx, dy = _best_shift(ca, cb)
    cb_shift = np.roll(np.roll(cb, dy, axis=0), dx, axis=1)
    geom = _ink_iou_tol(ca, cb_shift, tol=tol)
    ssim = _ssim(ca, cb_shift)
    return CompareResult(True, dx, dy, round(geom, 4), round(ssim, 4),
                         ink_a, ink_b, canvas, True, "", trust, band_for(geom))
