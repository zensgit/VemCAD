"""D2 regression comparator — align two renders of the same drawing and score
their similarity, following the May fidelity-workflow method (binarize → ink
bbox crop → common canvas → small translation search) and the Phase-1 plan §5
scoring semantics.

The gate metric is a dilation-tolerant ink IoU. Two regression classes the ink
metric is BLIND to are detected separately and routed to `review` rather than
silently passing: wrong ink color (grayscale IoU can't see it — a B4/layer
regression) and uniform scale / aspect change (the bbox-crop normalizes it
away). Both-blank is treated as a failure for a gated drawing, not a match.

NOT done in v0 (honest gap vs §5's "文字区/几何区分开打分"): a true
text/geometry SPLIT — that needs a renderer-supplied text mask (a B-line
follow-up). Until then the combined metric is `ink_iou` (NOT named
"geometry_*", which would imply a split that does not exist), and text-dense
golden drawings are not gated on it (golden.json gate=false), so a font
substitution does not false-fail the gate.

Pure image-in / score-out: no rendering here. Unit-tested with synthetic PIL
image pairs so alignment + scoring are verified without a live renderer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image

CANVAS = (1200, 850)
DILATE_TOL = 2
ASPECT_TOL = 0.06          # |1 - cand_aspect/ref_aspect| beyond this → review
COLOR_TOL = 60.0           # mean ink-RGB distance beyond this → review
INK_FLOOR = 1e-4           # below this ink fraction a render counts as blank

# §5 capture-method trust: only offscreen-render / plot-raster scores may gate
# CI; viewport-capture is advisory, dwg-thumbnail is record-only.
TRUST = {
    "offscreen-render": "gate",
    "plot-raster": "gate",
    "viewport-capture": "advisory",
    "dwg-thumbnail": "record",
}

BANDS = [
    (0.97, float("inf"), "pass"),   # open-ended high side
    (0.90, 0.97, "review"),
    (0.00, 0.90, "fallback"),
]

COLOR_CLASS_ORDER = ("dark", "green", "red", "yellow", "cyan", "magenta", "other")
COLOR_CLASS_NOTE = (
    "Display-color ink diagnostics only. These masks are not semantic text/"
    "dimension/hatch classes; they split CAD ink by rendered RGB after the same "
    "crop/resize/shift alignment as the gate metric."
)
SEMANTIC_CLASS_NOTE = (
    "Candidate-renderer semantic class diagnostics. The class buffer comes from "
    "render_cli and shares the candidate render view-space; AutoCAD reference "
    "semantics are unknown, so rows report how each candidate class overlaps the "
    "AutoCAD ink, not a true reference-vs-candidate semantic IoU."
)


def band_for(score: float) -> str:
    for lo, hi, action in BANDS:
        if lo <= score < hi:
            return action
    return "fallback"


def _dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    """4-connected binary dilation, `iterations` steps. Pure numpy."""
    m = mask
    for _ in range(max(0, iterations)):
        d = m.copy()
        d[1:, :] |= m[:-1, :]
        d[:-1, :] |= m[1:, :]
        d[:, 1:] |= m[:, :-1]
        d[:, :-1] |= m[:, 1:]
        m = d
    return m


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Non-wrapping integer shift (vacated cells filled with 0/False) — unlike
    np.roll, edge ink shifted out of frame does not reappear on the far side."""
    out = np.zeros_like(a)
    ys0, ys1 = max(0, dy), min(a.shape[0], a.shape[0] + dy)
    xs0, xs1 = max(0, dx), min(a.shape[1], a.shape[1] + dx)
    yt0, yt1 = max(0, -dy), min(a.shape[0], a.shape[0] - dy)
    xt0, xt1 = max(0, -dx), min(a.shape[1], a.shape[1] - dx)
    out[ys0:ys1, xs0:xs1] = a[yt0:yt1, xt0:xt1]
    return out


@dataclass
class CompareResult:
    aligned: bool
    dx: int
    dy: int
    ink_iou: float               # gate metric (dilation-tolerant ink overlap)
    ssim: float                  # informational
    ink_a: float
    ink_b: float
    aspect_delta: float          # |1 - cand_aspect/ref_aspect|; >ASPECT_TOL → review
    color_dist: float            # mean ink-RGB distance; >COLOR_TOL → review
    canvas: Tuple[int, int]
    comparable: bool
    skip_reason: str
    trust: str
    band: str

    def to_dict(self) -> dict:
        d = asdict(self); d["canvas"] = list(self.canvas); return d


@dataclass
class ColorClassResult:
    name: str
    ink_iou: float
    ref_pixels: int
    cand_pixels: int
    ref_fraction: float
    cand_fraction: float
    ref_present: bool
    cand_present: bool
    band: str


@dataclass
class ColorClassReport:
    diagnostic_kind: str
    semantic: bool
    note: str
    aligned: bool
    dx: int
    dy: int
    canvas: Tuple[int, int]
    comparable: bool
    skip_reason: str
    trust: str
    classes: Tuple[ColorClassResult, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["canvas"] = list(self.canvas)
        return d


@dataclass
class SemanticClassResult:
    name: str
    rgb: str
    candidate_pixels: int
    candidate_fraction: float
    candidate_precision: float
    reference_coverage: float
    candidate_present: bool
    band: str


@dataclass
class SemanticClassReport:
    diagnostic_kind: str
    semantic: bool
    reference_semantics: str
    candidate_semantics: str
    note: str
    aligned: bool
    dx: int
    dy: int
    canvas: Tuple[int, int]
    comparable: bool
    skip_reason: str
    trust: str
    classes: Tuple[SemanticClassResult, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["canvas"] = list(self.canvas)
        return d


def _load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)


def _bg_level(gray: np.ndarray) -> float:
    """Background = mean of the frame border (the canvas edge is bg in a CAD
    render). Robust to dominant-ink drawings, unlike a global histogram mode."""
    b = 3
    edge = np.concatenate([gray[:b, :].ravel(), gray[-b:, :].ravel(),
                           gray[:, :b].ravel(), gray[:, -b:].ravel()])
    return float(np.median(edge))


def _ink_mask(gray: np.ndarray) -> np.ndarray:
    bg = _bg_level(gray)
    return np.abs(gray - bg) > 32.0


def _ink_bbox(mask: np.ndarray):
    rows = np.any(mask, axis=1); cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return None
    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]
    return int(r0), int(r1) + 1, int(c0), int(c1) + 1


def _crop_resize(mask: np.ndarray, canvas: Tuple[int, int]):
    """Crop to ink bbox and resize to the common canvas. Returns
    (resized_mask, aspect) or (None, None) if blank. NEAREST is fine because
    the dilation-tolerant IoU + zero-preferring shift absorb the ≤tol aliasing
    (a no-resize fast path keeps identical-size inputs exact)."""
    bb = _ink_bbox(mask)
    if bb is None:
        return None, None
    r0, r1, c0, c1 = bb
    h, w = r1 - r0, c1 - c0
    aspect = w / h if h else 0.0
    return _crop_resize_to_bbox(mask, bb, canvas), aspect


def _crop_resize_to_bbox(mask: np.ndarray, bbox, canvas: Tuple[int, int]) -> np.ndarray:
    r0, r1, c0, c1 = bbox
    h, w = r1 - r0, c1 - c0
    sub = mask[r0:r1, c0:c1]
    if (w, h) == canvas:
        return sub
    img = Image.fromarray((sub * 255).astype(np.uint8)).resize(canvas, Image.NEAREST)
    return np.asarray(img) > 127


def _best_shift(a: np.ndarray, b: np.ndarray, search: int = 3):
    """Translation search maximizing symmetric tolerant overlap; prefers the
    smallest-magnitude shift on ties (so identical inputs choose (0,0))."""
    a_d = _dilate(a, DILATE_TOL)
    best, bdx, bdy, bmag = -1.0, 0, 0, 10 ** 9
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            bb = _shift(b, dy, dx)
            inter = np.logical_and(a_d, bb).sum()
            denom = bb.sum() + a.sum()  # symmetric-ish: penalize uncovered A too
            score = (2.0 * inter) / denom if denom else 0.0
            mag = dx * dx + dy * dy
            if score > best + 1e-9 or (abs(score - best) <= 1e-9 and mag < bmag):
                best, bdx, bdy, bmag = score, dx, dy, mag
    return bdx, bdy


def _ink_iou_tol(a: np.ndarray, b: np.ndarray, tol: int = DILATE_TOL) -> float:
    a_d = _dilate(a, tol); b_d = _dilate(b, tol)
    a_tot, b_tot = a.sum(), b.sum()
    if a_tot == 0 and b_tot == 0:
        return 1.0
    if a_tot == 0 or b_tot == 0:
        return 0.0
    recall = np.logical_and(a, b_d).sum() / a_tot
    precision = np.logical_and(b, a_d).sum() / b_tot
    return 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision)


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    af = a.astype(np.float64); bf = b.astype(np.float64)
    mu_a, mu_b = af.mean(), bf.mean()
    cov = ((af - mu_a) * (bf - mu_b)).mean()
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    return float(((2 * mu_a * mu_b + c1) * (2 * cov + c2)) /
                 ((mu_a ** 2 + mu_b ** 2 + c1) * (af.var() + bf.var() + c2)))


def _mean_ink_color(rgb: np.ndarray, mask: np.ndarray) -> Optional[np.ndarray]:
    if mask.sum() == 0:
        return None
    return rgb[mask].mean(axis=0)


def _display_color_masks(rgb: np.ndarray, ink: np.ndarray) -> dict[str, np.ndarray]:
    """Best-effort CAD display-color buckets for diagnostics.

    These intentionally stay display-color based. They do not infer CAD entity
    semantics; their purpose is to say which rendered color family accounts for
    a bad X3 comparison after the same global alignment as `compare()`.
    """
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]
    masks = {
        "dark": ink & (r < 100) & (g < 100) & (b < 100),
        "green": ink & (g > 120) & (r < 140) & (b < 170) & ((g - r) > 30) & ((g - b) > 20),
        "red": ink & (r > 140) & (g < 140) & (b < 160) & ((r - g) > 20),
        "yellow": ink & (r > 150) & (g > 120) & (b < 150),
        "cyan": ink & (g > 120) & (b > 120) & (r < 140),
        "magenta": ink & (r > 140) & (b > 120) & (g < 140),
    }
    covered = np.zeros_like(ink, dtype=bool)
    for mask in masks.values():
        covered |= mask
    masks["other"] = ink & ~covered
    return masks


def compare_color_classes(
    ref_path: Path, cand_path: Path, *,
    canvas: Tuple[int, int] = CANVAS, tol: int = DILATE_TOL,
    capture_method: str = "offscreen-render",
) -> ColorClassReport:
    """Diagnostic per-display-color scores after the same alignment as compare().

    The returned scores are not a pass/fail gate. They are a triage view for X3
    AutoCAD comparisons where one combined ink-IoU hides whether the misses are
    mostly dark geometry, dimensions in a color layer, or one-sided extra ink.
    """
    trust = TRUST.get(capture_method, "record")
    ra, rb = _load_rgb(Path(ref_path)), _load_rgb(Path(cand_path))
    ga, gb = ra.mean(axis=2), rb.mean(axis=2)
    ma, mb = _ink_mask(ga), _ink_mask(gb)
    bbox_a, bbox_b = _ink_bbox(ma), _ink_bbox(mb)

    if bbox_a is None or bbox_b is None:
        both_blank = bbox_a is None and bbox_b is None
        return ColorClassReport(
            "display-color-ink-classes", False, COLOR_CLASS_NOTE,
            False, 0, 0, canvas, True,
            "both-blank" if both_blank else "blank-side", trust, tuple(),
        )

    ca = _crop_resize_to_bbox(ma, bbox_a, canvas)
    cb = _crop_resize_to_bbox(mb, bbox_b, canvas)
    dx, dy = _best_shift(ca, cb)

    ref_classes = _display_color_masks(ra, ma)
    cand_classes = _display_color_masks(rb, mb)
    canvas_pixels = float(canvas[0] * canvas[1])
    rows = []
    for name in COLOR_CLASS_ORDER:
        ref_mask = _crop_resize_to_bbox(ref_classes[name], bbox_a, canvas)
        cand_mask = _crop_resize_to_bbox(cand_classes[name], bbox_b, canvas)
        cand_shift = _shift(cand_mask, dy, dx)
        ref_pixels = int(ref_mask.sum())
        cand_pixels = int(cand_mask.sum())
        score = _ink_iou_tol(ref_mask, cand_shift, tol=tol)
        ref_present = ref_pixels > 0
        cand_present = cand_pixels > 0
        rows.append(ColorClassResult(
            name=name,
            ink_iou=round(score, 4),
            ref_pixels=ref_pixels,
            cand_pixels=cand_pixels,
            ref_fraction=round(ref_pixels / canvas_pixels, 6),
            cand_fraction=round(cand_pixels / canvas_pixels, 6),
            ref_present=ref_present,
            cand_present=cand_present,
            band="absent" if not ref_present and not cand_present else band_for(score),
        ))

    return ColorClassReport(
        "display-color-ink-classes", False, COLOR_CLASS_NOTE,
        True, dx, dy, canvas, True, "", trust, tuple(rows),
    )


def _hex_rgb(value: str) -> Tuple[int, int, int]:
    s = (value or "").strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        raise ValueError("semantic palette rgb must be #RRGGBB")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _semantic_classes_from_report(report_path: Path):
    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    classes = payload.get("semantic_classes")
    if not isinstance(classes, dict):
        wrapped = payload.get("render_cli_report")
        if isinstance(wrapped, dict):
            classes = wrapped.get("semantic_classes")
    if not isinstance(classes, dict):
        raise ValueError("render report missing semantic_classes")
    palette = classes.get("palette")
    if not isinstance(palette, list) or not palette:
        raise ValueError("semantic_classes.palette must be a non-empty list")
    rows = []
    for row in palette:
        if not isinstance(row, dict):
            raise ValueError("semantic palette rows must be objects")
        name = str(row.get("name") or "")
        rgb = str(row.get("rgb") or "")
        if not name:
            raise ValueError("semantic palette row missing name")
        rows.append((name, rgb.upper(), _hex_rgb(rgb)))
    return classes, tuple(rows)


def _semantic_palette_masks(rgb: np.ndarray, palette) -> dict[str, np.ndarray]:
    """Classify a render_cli semantic class-buffer by nearest reserved colour.

    The buffer background is black and the foreground is anti-aliased, so exact
    RGB equality would drop edge pixels. Nearest palette colour over non-black
    pixels preserves the class buffer as a raster mask while still ignoring the
    black background.
    """
    non_bg = rgb.max(axis=2) > 8.0
    if not non_bg.any():
        return {name: np.zeros(rgb.shape[:2], dtype=bool) for name, _, _ in palette}
    pal = np.asarray([row[2] for row in palette], dtype=np.float64)
    flat = rgb.reshape((-1, 3))
    dist = ((flat[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
    nearest = dist.argmin(axis=1).reshape(rgb.shape[:2])
    return {
        name: non_bg & (nearest == idx)
        for idx, (name, _, _) in enumerate(palette)
    }


def compare_semantic_classes(
    ref_path: Path, cand_path: Path, *,
    candidate_mask_path: Path,
    render_report_path: Path,
    canvas: Tuple[int, int] = CANVAS, tol: int = DILATE_TOL,
    capture_method: str = "offscreen-render",
) -> SemanticClassReport:
    """Candidate semantic-class diagnostics after the same alignment as X3.

    This consumes render_cli's `--class-mask-out` PNG plus its report palette.
    The mask is candidate-side only: AutoCAD reference semantics are unknown, so
    rows report how each candidate class overlaps AutoCAD's total ink.
    """
    trust = TRUST.get(capture_method, "record")
    classes_meta, palette = _semantic_classes_from_report(render_report_path)
    ra, rb = _load_rgb(Path(ref_path)), _load_rgb(Path(cand_path))
    sem = _load_rgb(Path(candidate_mask_path))
    if sem.shape[:2] != rb.shape[:2]:
        return SemanticClassReport(
            "candidate-semantic-class-ink", True,
            str(classes_meta.get("reference_semantics", "unknown")),
            str(classes_meta.get("mask_kind", "candidate-renderer-semantic-class-buffer")),
            SEMANTIC_CLASS_NOTE, False, 0, 0, canvas, False,
            "semantic-mask-size-mismatch", trust, tuple(),
        )

    ga, gb = ra.mean(axis=2), rb.mean(axis=2)
    ma, mb = _ink_mask(ga), _ink_mask(gb)
    bbox_a, bbox_b = _ink_bbox(ma), _ink_bbox(mb)
    if bbox_a is None or bbox_b is None:
        both_blank = bbox_a is None and bbox_b is None
        return SemanticClassReport(
            "candidate-semantic-class-ink", True,
            str(classes_meta.get("reference_semantics", "unknown")),
            str(classes_meta.get("mask_kind", "candidate-renderer-semantic-class-buffer")),
            SEMANTIC_CLASS_NOTE, False, 0, 0, canvas, True,
            "both-blank" if both_blank else "blank-side", trust, tuple(),
        )

    ref_mask = _crop_resize_to_bbox(ma, bbox_a, canvas)
    cand_mask = _crop_resize_to_bbox(mb, bbox_b, canvas)
    dx, dy = _best_shift(ref_mask, cand_mask)
    class_masks = _semantic_palette_masks(sem, palette)
    ref_d = _dilate(ref_mask, tol)
    ref_total = float(ref_mask.sum())
    canvas_pixels = float(canvas[0] * canvas[1])

    rows = []
    for name, rgb, _ in palette:
        class_mask = _crop_resize_to_bbox(class_masks[name], bbox_b, canvas)
        shifted = _shift(class_mask, dy, dx)
        cand_pixels = int(shifted.sum())
        if cand_pixels:
            overlap = int(np.logical_and(shifted, ref_d).sum())
            precision = overlap / float(cand_pixels)
            coverage = (np.logical_and(ref_mask, _dilate(shifted, tol)).sum() / ref_total
                        if ref_total else 0.0)
        else:
            precision = 0.0
            coverage = 0.0
        rows.append(SemanticClassResult(
            name=name,
            rgb=rgb,
            candidate_pixels=cand_pixels,
            candidate_fraction=round(cand_pixels / canvas_pixels, 6),
            candidate_precision=round(float(precision), 4),
            reference_coverage=round(float(coverage), 4),
            candidate_present=cand_pixels > 0,
            band="absent" if not cand_pixels else band_for(float(precision)),
        ))

    return SemanticClassReport(
        "candidate-semantic-class-ink", True,
        str(classes_meta.get("reference_semantics", "unknown")),
        str(classes_meta.get("mask_kind", "candidate-renderer-semantic-class-buffer")),
        SEMANTIC_CLASS_NOTE, True, dx, dy, canvas, True, "", trust, tuple(rows),
    )


def compare(
    ref_path: Path, cand_path: Path, *,
    canvas: Tuple[int, int] = CANVAS, tol: int = DILATE_TOL,
    comparable: bool = True, skip_reason: str = "",
    capture_method: str = "offscreen-render",
    check_color: bool = True,
) -> CompareResult:
    trust = TRUST.get(capture_method, "record")
    ra, rb = _load_rgb(Path(ref_path)), _load_rgb(Path(cand_path))
    ga, gb = ra.mean(axis=2), rb.mean(axis=2)
    ma, mb = _ink_mask(ga), _ink_mask(gb)
    ink_a, ink_b = float(ma.mean()), float(mb.mean())

    # color divergence (the grayscale IoU is blind to it) — gated drawings with
    # a wrong-color render must not pass; route to review.
    color_dist = 0.0
    if check_color:
        ca_, cb_ = _mean_ink_color(ra, ma), _mean_ink_color(rb, mb)
        if ca_ is not None and cb_ is not None:
            color_dist = float(np.linalg.norm(ca_ - cb_))

    if not comparable:
        return CompareResult(False, 0, 0, 0.0, 0.0, ink_a, ink_b, 0.0, color_dist,
                             canvas, False, skip_reason or "not-comparable", trust, "review")

    ca, aspa = _crop_resize(ma, canvas)
    cb, aspb = _crop_resize(mb, canvas)
    if ca is None or cb is None:
        both_blank = ca is None and cb is None
        score = 1.0 if both_blank else 0.0
        # both-blank is a match number-wise but a gated drawing being blank is a
        # failure — surface via band=fallback so run()'s non-blank guard fires.
        return CompareResult(False, 0, 0, score, 0.0, ink_a, ink_b, 0.0, color_dist,
                             canvas, True, "both-blank" if both_blank else "blank-side",
                             trust, "fallback" if (both_blank or score == 0.0) else "pass")

    aspect_delta = abs(1.0 - (aspb / aspa)) if aspa else 0.0
    dx, dy = _best_shift(ca, cb)
    cb_shift = _shift(cb, dy, dx)
    iou = _ink_iou_tol(ca, cb_shift, tol=tol)
    ssim = _ssim(ca, cb_shift)

    band = band_for(iou)
    # shape (aspect) or color divergence cannot reach 'pass' — demote to review.
    if band == "pass" and (aspect_delta > ASPECT_TOL or color_dist > COLOR_TOL):
        band = "review"
    return CompareResult(True, dx, dy, round(iou, 4), round(ssim, 4), ink_a, ink_b,
                         round(aspect_delta, 4), round(color_dist, 1), canvas,
                         True, "", trust, band)
