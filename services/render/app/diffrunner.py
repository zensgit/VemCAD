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

        key = _diff_key(sha_a, sha_b, params, tol, self.svc.cli_sha, self.svc.font_fp)
        cached_report = self.cache.get_report(key)
        if cached_report is not None and cached_report.get("summary"):
            # Overlay present → serve it; report-only (not-comparable/blank) → None.
            return self.cache.get(key, DIFF_FMT), cached_report["summary"], key, True

        # Render BOTH revisions at the SAME params → shared bg + colour-mapping.
        # render_bytes caches each individually and enforces the busy gate.
        path_a, _, _ = await self.svc.render_bytes(content_a, params, content_sha=sha_a)
        path_b, _, _ = await self.svc.render_bytes(content_b, params, content_sha=sha_b)

        overlay_path, summary = await anyio.to_thread.run_sync(
            self._overlay_sync, engine, path_a, path_b, params, sha_a, sha_b, tol, key
        )
        return overlay_path, summary, key, False

    def _overlay_sync(self, engine, path_a, path_b, params, sha_a, sha_b, tol, key):
        # The engine decides comparability (its §5 view-space guard) — we never
        # force comparable=True. Write the overlay to a temp file first, then
        # publish through the cache (report-before-artifact atomicity).
        with tempfile.TemporaryDirectory(prefix="vemcad_diff_") as td:
            tmp_overlay = Path(td) / "overlay.png"
            res = engine.diff_overlay(
                Path(path_a), Path(path_b), tol=tol, out_path=tmp_overlay
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
