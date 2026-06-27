"""Render orchestration: params validation, four-tuple cache, sandboxed
render_cli invocation, saturation back-pressure (plan A2a/A3)."""

import asyncio
import json
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageOps

from .cache import RenderCache, cache_key, font_fingerprint, sha256_bytes, sha256_file
from .config import MAX_PIXELS, MAX_SIDE_PX, Settings
from .sandbox import SandboxRunner
from .sheet import detect_sheet_window
from .smoke import SMOKE_DXF

_BG_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_ALLOWED_FMT = ("png", "svg")
_ALLOWED_BG_NAMES = ("dark", "white")
_ALLOWED_STYLE = ("source", "acad-plot", "acad-display")
MEDIA_TYPES = {"png": "image/png", "svg": "image/svg+xml"}
ACAD_PLOT_TARGET_FILL_X = 0.8854
ACAD_PLOT_TARGET_FILL_Y = 0.9528


def _report_view(report: Optional[dict]) -> Optional[dict]:
    """Return render_cli's view mapping from a cached service report.

    The service report wraps render_cli's report under `render_cli_report`; older
    tests/stubs may still provide a top-level `view`. Keep both so tests and
    cached transitional reports fail open to the existing extents fallback only
    when neither shape carries view data.
    """
    if not isinstance(report, dict):
        return None
    view = report.get("view")
    if isinstance(view, dict):
        return view
    cli_report = report.get("render_cli_report")
    if isinstance(cli_report, dict) and isinstance(cli_report.get("view"), dict):
        return cli_report["view"]
    return None


class ParamError(ValueError):
    def __init__(self, message: str):
        super().__init__(message)
        self.error_code = "BAD_PARAMS"


class BusyError(RuntimeError):
    pass


class RenderFailed(RuntimeError):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.detail = detail


@dataclass(frozen=True)
class RenderParams:
    fmt: str
    width: int
    height: int
    bg: str
    view: str = "extents"
    # Output post-processing style. "source" preserves renderer colours.
    # "acad-plot" is a neutral grayscale plot-raster profile for AutoCAD
    # reference comparisons and white-sheet previews; it never changes geometry.
    # "acad-display" keeps source colours but maps low-saturation grey linework
    # to black, matching AutoCAD's common plot/display treatment for table/grid
    # strokes without applying a global lineweight or grayscale conversion.
    style: str = "source"
    # Optional explicit world window (xmin, ymin, xmax, ymax). When set, view is
    # "window" and render_cli is driven with --window instead of auto-extents.
    # Internal to the /diff common-window upgrade; the HTTP surface still only
    # parses view="extents" (a window is derived, never client-supplied in v0).
    window: Optional[Tuple[float, float, float, float]] = None

    @staticmethod
    def parse(fmt: str, width, height, bg: str, view: str, style: str = "source") -> "RenderParams":
        if fmt not in _ALLOWED_FMT:
            raise ParamError("format must be one of: " + ", ".join(_ALLOWED_FMT))
        try:
            w, h = int(width), int(height)
        except (TypeError, ValueError):
            raise ParamError("width/height must be integers")
        if not (16 <= w <= MAX_SIDE_PX and 16 <= h <= MAX_SIDE_PX):
            raise ParamError("width/height must be within 16..%d" % MAX_SIDE_PX)
        if w * h > MAX_PIXELS:
            raise ParamError("width*height must be <= %d pixels" % MAX_PIXELS)
        if bg not in _ALLOWED_BG_NAMES and not _BG_RE.match(bg or ""):
            raise ParamError("bg must be dark, white or #RRGGBB")
        if view not in ("extents", "sheet", "acad-plot"):
            raise ParamError("view must be 'extents', 'sheet' or 'acad-plot'")
        if view == "acad-plot" and fmt != "png":
            raise ParamError("view=acad-plot requires format=png")
        if style not in _ALLOWED_STYLE:
            raise ParamError("style must be one of: " + ", ".join(_ALLOWED_STYLE))
        if style != "source" and fmt != "png":
            raise ParamError("style=%s requires format=png" % style)
        return RenderParams(fmt=fmt, width=w, height=h, bg=bg, view=view, style=style)

    def windowed(self, window: Tuple[float, float, float, float]) -> "RenderParams":
        """Derive a copy that renders in an explicit world window. Validates the
        rect (finite, non-degenerate); raises ParamError otherwise."""
        if window is None or len(window) != 4:
            raise ParamError("window must be (xmin, ymin, xmax, ymax)")
        try:
            x1, y1, x2, y2 = (float(v) for v in window)
        except (TypeError, ValueError):
            raise ParamError("window coordinates must be numbers")
        for v in (x1, y1, x2, y2):
            if v != v or v in (float("inf"), float("-inf")):  # NaN / inf
                raise ParamError("window coordinates must be finite")
        if x2 <= x1 or y2 <= y1:
            raise ParamError("window must have xmax>xmin and ymax>ymin")
        return replace(self, view="window", window=(x1, y1, x2, y2))

    def as_dict(self) -> dict:
        d = {
            "format": self.fmt,
            "width": self.width,
            "height": self.height,
            "bg": self.bg,
            "view": self.view,
        }
        # Keep legacy/source cache keys unchanged. Non-source styles must enter
        # the key so a coloured render cannot satisfy an AutoCAD-plot request.
        if self.style != "source":
            d["style"] = self.style
        # Include the window only when set, so non-windowed renders keep their
        # existing four-tuple cache keys unchanged.
        if self.window is not None:
            d["window"] = list(self.window)
        return d


def apply_acad_plot_style(path: Path) -> None:
    """Convert a PNG in-place to a neutral grayscale plot-raster style.

    AutoCAD plot references in the training corpus are often generated through
    plot/PDF-style colour tables rather than the saturated ACI screen palette.
    The renderer's geometry should stay untouched; only the output colours are
    neutralised so comparison metrics and human review are not dominated by
    bright cyan/green/yellow annotation ink.
    """
    img = Image.open(path)
    alpha = None
    if img.mode in ("RGBA", "LA"):
        alpha = img.getchannel("A")
    gray = ImageOps.grayscale(img.convert("RGB"))
    out = ImageOps.colorize(gray, black="#000000", white="#ffffff")
    if alpha is not None:
        out.putalpha(alpha)
    out.save(path)


def apply_acad_display_style(path: Path) -> None:
    """Darken neutral grey linework while preserving saturated CAD colours.

    AutoCAD PLOT/display references often render table/grid strokes as black
    even when the DXF source colour is a low-saturation grey. A full grayscale
    `acad-plot` pass is useful for neutral diagnostics, but it destroys source
    colour. This lighter-weight display profile only maps low-saturation,
    non-background greys to black; red/green/yellow/cyan annotation ink remains
    unchanged.
    """
    img = Image.open(path)
    alpha = img.getchannel("A") if img.mode in ("RGBA", "LA") else None
    arr = np.asarray(img.convert("RGB")).copy()
    max_channel = arr.max(axis=2).astype(np.int16)
    min_channel = arr.min(axis=2).astype(np.int16)
    saturation = max_channel - min_channel
    luminance = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    grey_linework = (saturation <= 35) & (luminance < 225) & (luminance > 20)
    arr[grey_linework] = (0, 0, 0)
    out = Image.fromarray(arr, mode="RGB")
    if alpha is not None:
        out.putalpha(alpha)
    out.save(path)


def _background_rgb(arr: np.ndarray) -> tuple[int, int, int]:
    """Estimate the render background from the canvas border."""
    edge = np.concatenate(
        [
            arr[:3, :, :].reshape(-1, 3),
            arr[-3:, :, :].reshape(-1, 3),
            arr[:, :3, :].reshape(-1, 3),
            arr[:, -3:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    return tuple(int(round(v)) for v in np.median(edge, axis=0))


def _ink_bbox(arr: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    """Return (top, bottom, left, right) ink bounds using border-relative ink.

    This mirrors the render-regression comparator's framing detector: CAD
    renders can be white or dark, so fixed black/white thresholds are fragile.
    """
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    edge = np.concatenate(
        [gray[:3, :].ravel(), gray[-3:, :].ravel(), gray[:, :3].ravel(), gray[:, -3:].ravel()]
    )
    bg = float(np.median(edge))
    mask = np.abs(gray - bg) > 32.0
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return None
    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]
    return int(r0), int(r1) + 1, int(c0), int(c1) + 1


def apply_acad_plot_view_frame(path: Path) -> dict:
    """Reframe a render into AutoCAD PLOT-like paper fill, in-place.

    AutoCAD's training references are A4 landscape PLOT rasters using
    Extents/Fit/Center. The renderer's raw model-extents view has a larger fixed
    viewport margin, so otherwise comparable drawings can fail the view-space
    framing check before any real fidelity issue is measured. This postprocess
    keeps the rendered ink unchanged except for a uniform scale onto the observed
    AutoCAD plot paper fill envelope.
    """
    img = Image.open(path)
    arr = np.asarray(img.convert("RGB"))
    bbox = _ink_bbox(arr)
    if bbox is None:
        return {"mode": "fallback", "reason": "blank"}

    r0, r1, c0, c1 = bbox
    ink_w = c1 - c0
    ink_h = r1 - r0
    if ink_w <= 0 or ink_h <= 0:
        return {"mode": "fallback", "reason": "degenerate-ink-bbox"}

    width, height = img.size
    target_w_max = max(1, int(round(width * ACAD_PLOT_TARGET_FILL_X)))
    target_h_max = max(1, int(round(height * ACAD_PLOT_TARGET_FILL_Y)))
    ink_aspect = ink_w / ink_h
    target_aspect = target_w_max / target_h_max
    if ink_aspect >= target_aspect:
        target_w = target_w_max
        target_h = max(1, int(round(target_w / ink_aspect)))
    else:
        target_h = target_h_max
        target_w = max(1, int(round(target_h * ink_aspect)))

    crop = img.convert("RGB").crop((c0, r0, c1, r1))
    resized = crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
    out = Image.new("RGB", (width, height), _background_rgb(arr))
    x = (width - target_w) // 2
    y = (height - target_h) // 2
    out.paste(resized, (x, y))
    out.save(path)
    return {
        "mode": "framed",
        "source_bbox_px": [c0, r0, c1, r1],
        "target_bbox_px": [x, y, x + target_w, y + target_h],
        "target_fill_x": round(target_w / width, 4),
        "target_fill_y": round(target_h / height, 4),
    }


SMOKE_TIMEOUT_S = 30.0
SMOKE_MIN_BYTES = 1000  # blank/background-only PNG sits well below this


class RenderService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache = RenderCache(settings.cache_dir)
        xdg_cache = settings.cache_dir / "xdg-cache"
        xdg_cache.mkdir(parents=True, exist_ok=True)
        self.sandbox = SandboxRunner(
            timeout_s=settings.timeout_s,
            mem_limit_mb=settings.mem_limit_mb,
            allow_sandbox_exec=settings.allow_sandbox_exec,
            cache_home=xdg_cache,
        )
        self.cli_sha: Optional[str] = (
            sha256_file(settings.render_cli) if settings.render_cli else None
        )
        self.font_fp = font_fingerprint(settings.font_dir)
        self.active = 0  # mutated only on the event loop thread

    @property
    def available(self) -> bool:
        return self.cli_sha is not None

    def font_count(self) -> int:
        d = self.settings.font_dir
        if not d or not d.is_dir():
            return 0
        return sum(1 for p in d.iterdir() if p.is_file())

    async def render_bytes(
        self, content: bytes, params: RenderParams, content_sha: Optional[str] = None
    ) -> Tuple[Path, str, bool]:
        """Returns (artifact path, cache key, was_cache_hit).

        `content_sha` may be precomputed (the HTTP layer hashes incrementally
        while reading the upload, keeping the event loop free of large hashes).
        """
        if not self.available:
            raise RenderFailed("render_cli unavailable", "no binary configured")
        if content_sha is None:
            content_sha = sha256_bytes(content)
        key = cache_key(content_sha, params.as_dict(), self.cli_sha, self.font_fp)
        hit = self.cache.get(key, params.fmt)
        if hit is not None:
            return hit, key, True
        if self.active >= self.settings.workers:
            raise BusyError()
        self.active += 1
        try:
            path = await asyncio.to_thread(self._render_sync, content, content_sha, params, key)
        finally:
            self.active -= 1
        return path, key, False

    async def render_sheet_bytes(
        self, content: bytes, params: RenderParams, content_sha: Optional[str] = None
    ) -> Tuple[Path, str, bool]:
        """view=sheet (plot preview): render at extents, detect the 图框 window from
        that image, then re-render framed to it so strays OUTSIDE the border are
        clipped (corpus #020 class). Fail-safe: no confident frame -> the extents
        render (today's behaviour). Both passes ride the normal render cache, so a
        repeat sheet request is two cache hits."""
        if content_sha is None:
            content_sha = sha256_bytes(content)
        probe = replace(params, view="extents", window=None)
        ppath, pkey, phit = await self.render_bytes(content, probe, content_sha)
        view = _report_view(self.cache.get_report(pkey))
        rect = detect_sheet_window(str(ppath), view) if isinstance(view, dict) else None
        if rect is None:
            return ppath, pkey, phit  # no confident 图框 -> keep extents framing
        try:
            windowed = probe.windowed(rect)
        except ParamError:
            return ppath, pkey, phit  # degenerate detected rect -> extents
        return await self.render_bytes(content, windowed, content_sha)

    async def render_view_bytes(
        self, content: bytes, params: RenderParams, content_sha: Optional[str] = None
    ) -> Tuple[Path, str, bool]:
        """Single entry the HTTP layer calls: dispatch by view ('sheet' -> the
        two-pass sheet-window producer; else the plain extents/window render)."""
        if params.view == "sheet":
            return await self.render_sheet_bytes(content, params, content_sha)
        return await self.render_bytes(content, params, content_sha)

    @staticmethod
    def _build_argv(render_cli, src, out, params: RenderParams, report_path, font_dir):
        """Construct the render_cli argv. Pure (no I/O) so it is unit-testable.
        Appends --window only when an explicit world window is set (the /diff
        common-window upgrade); otherwise render_cli auto-fits to extents."""
        argv = [
            str(render_cli),
            "--input", str(src),
            "--out", str(out),
            "--width", str(params.width),
            "--height", str(params.height),
            "--bg", params.bg,
            "--report", str(report_path),
        ]
        # B5: explicit world rectangle so both /diff revisions share view-space.
        # Use repr (shortest round-trippable form) rather than %g — %g caps at 6
        # significant figures, which on a HARD world rect would round the window
        # inward and clip real edge geometry for large CAD coordinates.
        if params.window is not None:
            argv += ["--window", ",".join(repr(float(v)) for v in params.window)]
        # A5: feed the per-tenant font directory to render_cli (B1 --font-dir),
        # so drawing fonts the host OS lacks resolve from our store. The dir's
        # fingerprint is already in the cache key, so changing fonts re-renders.
        if font_dir:
            argv += ["--font-dir", str(font_dir)]
        return argv

    def _render_sync(
        self,
        content: bytes,
        content_sha: str,
        params: RenderParams,
        key: str,
        timeout_s: Optional[float] = None,
    ) -> Path:
        # Double-check after winning the slot: another worker may have produced it.
        hit = self.cache.get(key, params.fmt)
        if hit is not None:
            return hit
        with tempfile.TemporaryDirectory(prefix="vemcad_render_") as td:
            workdir = Path(td)
            src = workdir / "input.dxf"
            src.write_bytes(content)
            out = workdir / ("out." + params.fmt)
            cli_report_path = workdir / "render_report.json"
            argv = self._build_argv(
                self.settings.render_cli, src, out, params, cli_report_path,
                self.settings.font_dir,
            )
            res = self.sandbox.run(argv, workdir, timeout_s=timeout_s)
            if res.timed_out:
                raise RenderFailed("render timed out", "timeout after %.0fs" % self.settings.timeout_s)
            if res.exit_code != 0:
                raise RenderFailed(
                    "render_cli failed (exit %d)" % res.exit_code,
                    (res.stderr or res.stdout).strip(),
                )
            if not out.is_file() or out.stat().st_size == 0:
                raise RenderFailed("render produced no output", res.stderr.strip())
            acad_plot_frame = None
            if params.view == "acad-plot":
                try:
                    acad_plot_frame = apply_acad_plot_view_frame(out)
                except OSError as e:
                    raise RenderFailed("acad-plot view postprocess failed", str(e))
            if params.style == "acad-plot":
                try:
                    apply_acad_plot_style(out)
                except OSError as e:
                    raise RenderFailed("plot-style postprocess failed", str(e))
            elif params.style == "acad-display":
                try:
                    apply_acad_display_style(out)
                except OSError as e:
                    raise RenderFailed("display-style postprocess failed", str(e))
            cli_report = None
            if cli_report_path.is_file():
                try:
                    cli_report = json.loads(cli_report_path.read_text("utf-8"))
                except (OSError, ValueError):
                    cli_report = None
            report = {
                # Service-side audit record; B1's renderer-emitted
                # "vemcad.render_report" (view rect/scale, counts, font records)
                # is embedded under "render_cli_report".
                "schema": "vemcad.render_service_report",
                "schema_version": "0.1",
                "params": params.as_dict(),
                "content_sha256": content_sha,
                "render_cli_sha256": self.cli_sha,
                "font_dir": str(self.settings.font_dir) if self.settings.font_dir else None,
                "font_fingerprint": self.font_fp,
                "duration_s": round(res.duration_s, 3),
                "network_isolated": res.network_isolated,
                "render_cli_stdout": res.stdout.strip(),
                "render_cli_report": cli_report,
            }
            if acad_plot_frame is not None:
                report["acad_plot_frame"] = acad_plot_frame
            return self.cache.put(key, params.fmt, out, report)

    def smoke(self) -> dict:
        """Startup/health smoke: render the built-in synthetic drawing
        (geometry + a TEXT entity, so silent font breakage shows up as a
        size collapse). Bounded by its own short timeout so startup never
        blocks for the full render timeout."""
        if not self.available:
            return {"ok": False, "detail": "render_cli unavailable"}
        params = RenderParams.parse("png", 400, 250, "dark", "extents")
        try:
            content = SMOKE_DXF.encode("ascii")
            content_sha = sha256_bytes(content)
            key = cache_key(content_sha, params.as_dict(), self.cli_sha, self.font_fp)
            path = self._render_sync(
                content, content_sha, params, key,
                timeout_s=min(SMOKE_TIMEOUT_S, self.settings.timeout_s),
            )
            size = path.stat().st_size
            if size < SMOKE_MIN_BYTES:
                return {"ok": False, "detail": "suspiciously small output (%d B)" % size,
                        "bytes": size}
            return {"ok": True, "bytes": size}
        except RenderFailed as e:
            return {"ok": False, "detail": "%s: %s" % (e, e.detail)}
