"""Version visual diff orchestration (L1 flagship). Renders two DXF revisions
at IDENTICAL params (so §5's bg + colour-mapping are shared by construction),
then runs the shared `tools/render_regression/diff.py` engine to classify each
ink pixel as unchanged / added / removed and emit a 3-colour overlay.

The diff algorithm is NOT duplicated here — it is the same code the D2
regression harness uses. numpy + Pillow are imported lazily so the service
still boots (and /render keeps working) on an install that lacks them; /diff
then degrades with a structured 501 instead of failing at import time.

The two underlying renders ride the existing four-tuple render cache. The
overlay is cached too (deterministic given the two source shas + params + tol),
which also gives the HTTP layer a stable file path to stream back.
"""

import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import anyio

from .cache import cache_key, sha256_bytes
from .dxfextents import extents_differ, parse_dxf_extents, union_window
from .renderer import RenderParams, RenderService

# Overlay output is always PNG raster (a vector overlay is meaningless — the
# diff works on rasterised ink masks).
DIFF_FMT = "png"
DIFF_MEDIA_TYPE = "image/png"


class DiffUnavailable(RuntimeError):
    """numpy / Pillow / the diff engine could not be imported."""


def _find_regression_dir() -> Optional[Path]:
    """Walk up from this file to the in-repo tools/render_regression/."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "tools" / "render_regression" / "diff.py"
        if cand.is_file():
            return cand.parent
    return None


_engine = None


def _load_engine():
    """Import the shared diff engine lazily. Adds tools/render_regression to
    sys.path (diff.py does `from compare import ...`). Raises DiffUnavailable
    with a clear reason if the dir or numpy/Pillow are missing."""
    global _engine
    if _engine is not None:
        return _engine
    reg = _find_regression_dir()
    if reg is None:
        raise DiffUnavailable("tools/render_regression not found alongside the service")
    if str(reg) not in sys.path:
        sys.path.insert(0, str(reg))
    try:
        import diff as diff_engine  # noqa: E402  (needs the sys.path insert above)
    except ImportError as e:  # numpy / Pillow / compare missing
        raise DiffUnavailable("diff engine import failed (numpy/Pillow?): %s" % e)
    _engine = diff_engine
    return _engine


def _diff_key(sha_a: str, sha_b: str, params: RenderParams, tol: int,
              cli_sha: str, font_fp: str) -> str:
    # Orientation matters (A=old, B=new) so the pair sha is order-sensitive.
    pair_sha = sha256_bytes(("%s:%s" % (sha_a, sha_b)).encode("utf-8"))
    diff_params = dict(params.as_dict())
    diff_params["op"] = "diff"
    diff_params["tol"] = tol
    return cache_key(pair_sha, diff_params, cli_sha, font_fp)


def _view_rect(report, field: str):
    """Read a render report's view rect (`content_bbox` or `clip`) as a
    (xmin, ymin, xmax, ymax) tuple, or None when absent/malformed."""
    if not report:
        return None
    view = (report.get("render_cli_report") or {}).get("view") or {}
    r = view.get(field)
    if not isinstance(r, dict):
        return None
    try:
        return (float(r["min_x"]), float(r["min_y"]),
                float(r["max_x"]), float(r["max_y"]))
    except (KeyError, TypeError, ValueError):
        return None


def _rect_close(a, b, rtol: float = 1e-5, atol: float = 1e-6) -> bool:
    """True if two (xmin,ymin,xmax,ymax) rects agree on every edge within tol."""
    return all(abs(a[i] - b[i]) <= atol + rtol * max(abs(a[i]), abs(b[i]))
               for i in range(4))


def _frames_tightly(clip, cb, rtol: float = 1e-5, atol: float = 1e-6) -> bool:
    """True if a render's per-extents `clip` frame already frames its real
    geometry `cb` tightly — i.e. it CONTAINS cb (no clipping) AND is ~equal to it
    (so the reused frame matches the content_bbox window). The containment test is
    one-sided so a clip even slightly SMALLER than cb (which would clip real
    geometry) is never treated as tight. Used by follow-up B to decide reuse."""
    if clip is None or cb is None:
        return False
    contains = (clip[0] <= cb[0] + atol and clip[1] <= cb[1] + atol
                and clip[2] >= cb[2] - atol and clip[3] >= cb[3] - atol)
    return contains and _rect_close(clip, cb, rtol, atol)


class DiffService:
    """Thin orchestrator over a RenderService — renders both revisions and
    diffs them. Shares the render service's cache + saturation gate."""

    def __init__(self, render_svc: RenderService):
        self.svc = render_svc
        self.cache = render_svc.cache

    async def diff_bytes(
        self,
        content_a: bytes,
        content_b: bytes,
        params: RenderParams,
        *,
        sha_a: Optional[str] = None,
        sha_b: Optional[str] = None,
        tol: int = 2,
    ) -> Tuple[Optional[Path], dict, str, bool]:
        """Returns (overlay_path | None, summary_dict, diff_cache_key, hit).

        overlay_path is None when the pair is not comparable (view-space
        mismatch) or both renders are blank — the summary then carries the
        skip_reason. Raises DiffUnavailable / BusyError / RenderFailed upward.
        """
        engine = _load_engine()  # raises DiffUnavailable before any render work
        if sha_a is None:
            sha_a = sha256_bytes(content_a)
        if sha_b is None:
            sha_b = sha256_bytes(content_b)

        # §5 common-window v2: frame both revisions to REAL geometry so the pair
        # shares view-space and nothing clips. The shared window is the union of
        # the two content_bboxes (real geometry from render_cli). content_bbox is
        # frame-independent, so it is cached by content_sha (perf follow-up A): a
        # repeat diff of a file skips the extents "probe" render and goes straight
        # to the windowed diff render.
        cb_a, clip_a = await self._content_geom(content_a, sha_a, params)
        cb_b, clip_b = await self._content_geom(content_b, sha_b, params)
        # render_params = the images actually fed to the diff; key_params = the
        # LOGICAL frame the diff is keyed + reported under. They differ only in the
        # follow-up-B reuse case, where we feed per-extents renders that are
        # equivalent to the union-window renders — keeping key_params canonical so
        # the diff cache key is STABLE regardless of how the pixels were produced
        # (a later diff of the same pair still hits the cache).
        render_params = params
        key_params = params
        shared_view = False
        if cb_a is not None and cb_b is not None:
            # Real geometry known for both → the diff is LOGICALLY framed to the
            # content_bbox union window: shared view-space, nothing clips. Do NOT
            # gate on the two bboxes differing — equal content_bboxes do not make
            # per-extents renders safe to reuse (a stale-small header clips internal
            # geometry beyond it; differing headers → mismatched view-space).
            window_source = "content_bbox"
            shared_view = True
            key_params = params.windowed(union_window(cb_a, cb_b))
            if (_frames_tightly(clip_a, cb_a) and _frames_tightly(clip_b, cb_b)
                    and _rect_close(clip_a, clip_b)):
                # Follow-up B: both per-extents renders already frame their real
                # geometry tightly and in the SAME frame, so they are equivalent to
                # the union-window renders — REUSE them (render at extents) and skip
                # the windowed re-render. Pure render-time optimization; the cache
                # key stays canonical (key_params). clip is known only on a
                # content_bbox cache miss — exactly when the probe render exists.
                render_params = params
            else:
                render_params = key_params  # render in the union window
        else:
            # Fallback: real geometry unknown (render_cli predating content_bbox).
            # The DXF HEADER is the only view-space signal, so window only when the
            # two headers differ — header can be stale-small and clip.
            window_source = "header"
            h_a = parse_dxf_extents(content_a)
            h_b = parse_dxf_extents(content_b)
            if h_a is not None and h_b is not None and extents_differ(h_a, h_b):
                render_params = params.windowed(union_window(h_a, h_b))
            key_params = render_params
            shared_view = render_params.window is not None

        key = _diff_key(sha_a, sha_b, key_params, tol, self.svc.cli_sha, self.svc.font_fp)
        cached_report = self.cache.get_report(key)
        cached_summary = cached_report.get("summary") if cached_report else None
        if cached_summary:
            artifact = self.cache.get(key, DIFF_FMT)  # None if missing or zero-byte
            # A comparable diff MUST have an overlay; a skip verdict
            # (view-space-mismatch / both-blank) is legitimately report-only.
            # Only trust the hit when the artifact state matches the verdict —
            # otherwise the overlay was lost/truncated, so fall through and
            # re-render rather than serve a comparable result with no image.
            expects_overlay = bool(cached_summary.get("comparable")) and not cached_summary.get("skip_reason")
            if not (expects_overlay and artifact is None):
                return artifact, cached_summary, key, True

        # Render BOTH revisions at render_params for the diff. render_bytes caches
        # by (content_sha, params): with no window this hits the extents probe
        # render; with a window it renders/​hits the common-window render.
        path_a, _, _ = await self.svc.render_bytes(content_a, render_params, content_sha=sha_a)
        path_b, _, _ = await self.svc.render_bytes(content_b, render_params, content_sha=sha_b)

        # Report under key_params (the canonical logical frame), not render_params:
        # in the reuse case the pixels came from the per-extents renders but the
        # diff is logically the union-window diff, so common_window reflects that.
        overlay_path, summary = await anyio.to_thread.run_sync(
            self._overlay_sync, engine, path_a, path_b, key_params, sha_a, sha_b, tol, key,
            window_source, shared_view,
        )
        return overlay_path, summary, key, False

    async def _content_geom(self, content: bytes, content_sha: str, params):
        """Returns (content_bbox, clip) for a drawing.

        content_bbox = real geometry extent (render_cli #392), cached by
        content_sha (follow-up A). clip = the per-extents frame render_cli used
        (`view.clip` = the DXF header rect), read from the PROBE report — so it is
        available only on a content_bbox cache MISS (when we render the probe),
        and None on a cache hit. Follow-up B uses clip to detect when the
        per-extents render already frames real geometry (clip == content_bbox) and
        can be reused instead of re-rendering windowed.

        content_bbox is None when the render_cli predates the field (caller then
        uses the header fallback)."""
        cli_sha = self.svc.cli_sha
        cached = self.cache.get_content_bbox(content_sha, cli_sha)
        if cached is not None:
            return cached, None  # cache hit: no probe report, so no clip
        _, key, _ = await self.svc.render_bytes(content, params, content_sha=content_sha)
        report = self.cache.get_report(key)
        cb = _view_rect(report, "content_bbox")
        clip = _view_rect(report, "clip")
        if cb is not None:
            self.cache.put_content_bbox(content_sha, cli_sha, cb)
        return cb, clip

    def _overlay_sync(self, engine, path_a, path_b, params, sha_a, sha_b, tol, key,
                      window_source="content_bbox", shared_view=False):
        # The engine decides comparability (its §5 view-space guard) — we never
        # force comparable=True. `shared_view` (decided by the caller) tells the
        # engine the two renders share view-space so it diffs them in the common
        # pixel grid instead of cropping each to its own bbox (which would defeat
        # the shared window / re-centre a moved revision into a false match). It is
        # True whenever real geometry framed the pair — both the union-window path
        # AND follow-up B's reuse path (per-extents renders with agreeing tight
        # clips share view-space without an explicit window). Write the overlay to
        # a temp file first, then publish through the cache (report-before-artifact).
        with tempfile.TemporaryDirectory(prefix="vemcad_diff_") as td:
            tmp_overlay = Path(td) / "overlay.png"
            res = engine.diff_overlay(
                Path(path_a), Path(path_b), tol=tol, out_path=tmp_overlay,
                shared_view=shared_view,
            )
            summary = res.to_dict()
            # overlay_path is an internal temp path — the HTTP layer streams the
            # image itself / reports via headers, never a server filesystem path.
            summary.pop("overlay_path", None)
            summary.update({
                "source_sha256": {"ref": sha_a, "cand": sha_b},
                "params": params.as_dict(),
                "tol": tol,
            })
            # Honest provenance: when the pair shared view-space, record its source
            # (real geometry content_bbox, or the stale-prone header fallback); and
            # when an explicit union window was rendered, record it. Follow-up B's
            # reuse path shares view-space WITHOUT an explicit window, so it records
            # window_source but no common_window.
            if shared_view:
                summary["window_source"] = window_source
            if params.window is not None:
                summary["common_window"] = list(params.window)
            report = {
                "schema": "vemcad.render_diff_report",
                "schema_version": "0.1",
                "summary": summary,
            }
            if res.overlay_path is not None and tmp_overlay.is_file():
                final = self.cache.put(key, DIFF_FMT, tmp_overlay, report)
                return final, summary
            # Not comparable / both-blank: cache the verdict (report only).
            self.cache.put_report_only(key, report)
            return None, summary
