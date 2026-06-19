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
        cb_a = await self._content_bbox(content_a, sha_a, params)
        cb_b = await self._content_bbox(content_b, sha_b, params)
        render_params = params
        if cb_a is not None and cb_b is not None:
            # When real geometry is known for both, ALWAYS render in the
            # content_bbox union window — do NOT gate on the two bboxes differing.
            # EQUAL content_bboxes do NOT imply the per-extents renders are safe to
            # reuse: two revisions can share an outer bbox yet sit behind a
            # stale-small header that clips internal geometry differing beyond it,
            # or carry mismatched per-extents view-space. The union window fixes
            # both. (Perf follow-up B: reuse the per-extents renders when both
            # reports show clip == content_bbox and the clips agree, to skip the
            # windowed re-render.)
            window_source = "content_bbox"
            render_params = params.windowed(union_window(cb_a, cb_b))
        else:
            # Fallback: real geometry unknown (render_cli predating content_bbox).
            # The DXF HEADER is the only view-space signal, so window only when the
            # two headers differ — header can be stale-small and clip.
            window_source = "header"
            h_a = parse_dxf_extents(content_a)
            h_b = parse_dxf_extents(content_b)
            if h_a is not None and h_b is not None and extents_differ(h_a, h_b):
                render_params = params.windowed(union_window(h_a, h_b))

        key = _diff_key(sha_a, sha_b, render_params, tol, self.svc.cli_sha, self.svc.font_fp)
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

        overlay_path, summary = await anyio.to_thread.run_sync(
            self._overlay_sync, engine, path_a, path_b, render_params, sha_a, sha_b, tol, key,
            window_source,
        )
        return overlay_path, summary, key, False

    async def _content_bbox(self, content: bytes, content_sha: str, params):
        """Real geometry extent (render_cli content_bbox) for a drawing, cached by
        content_sha (perf follow-up A). Returns (xmin, ymin, xmax, ymax), or None
        when the render_cli predates content_bbox (caller then uses the header
        fallback). On a cache miss, renders once at `params` (the extents probe)
        to read it from the report, then caches it. content_bbox is
        frame-independent, so the cache key is (content_sha, cli_sha) only — a
        later diff at any params/window/bg reuses it."""
        cli_sha = self.svc.cli_sha
        cached = self.cache.get_content_bbox(content_sha, cli_sha)
        if cached is not None:
            return cached
        _, key, _ = await self.svc.render_bytes(content, params, content_sha=content_sha)
        cb = self._report_content_bbox(key)
        if cb is not None:
            self.cache.put_content_bbox(content_sha, cli_sha, cb)
        return cb

    def _report_content_bbox(self, render_key: str):
        """Real geometry extent of a render, from its render_cli report
        `view.content_bbox` (added in CADGameFusion #392) — returns
        (xmin, ymin, xmax, ymax) or None when absent (older render_cli)."""
        report = self.cache.get_report(render_key)
        if not report:
            return None
        view = (report.get("render_cli_report") or {}).get("view") or {}
        cb = view.get("content_bbox")
        if not isinstance(cb, dict):
            return None
        try:
            return (float(cb["min_x"]), float(cb["min_y"]),
                    float(cb["max_x"]), float(cb["max_y"]))
        except (KeyError, TypeError, ValueError):
            return None

    def _overlay_sync(self, engine, path_a, path_b, params, sha_a, sha_b, tol, key,
                      window_source="content_bbox"):
        # The engine decides comparability (its §5 view-space guard) — we never
        # force comparable=True. When we rendered both revisions in a common
        # window (params.window set), tell the engine they share view-space so it
        # diffs them in the common pixel grid instead of cropping each to its own
        # bbox (which would defeat the shared window / re-centre a moved revision
        # into a false match). Write the overlay to a temp file first, then
        # publish through the cache (report-before-artifact atomicity).
        with tempfile.TemporaryDirectory(prefix="vemcad_diff_") as td:
            tmp_overlay = Path(td) / "overlay.png"
            res = engine.diff_overlay(
                Path(path_a), Path(path_b), tol=tol, out_path=tmp_overlay,
                shared_view=(params.window is not None),
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
            # Honest provenance: record the shared window when the common-window
            # upgrade fired (extents-changing revisions rendered in a union rect),
            # plus whether it came from real geometry (content_bbox) or the
            # stale-prone header fallback.
            if params.window is not None:
                summary["common_window"] = list(params.window)
                summary["window_source"] = window_source
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
