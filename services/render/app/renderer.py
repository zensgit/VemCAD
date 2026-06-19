"""Render orchestration: params validation, four-tuple cache, sandboxed
render_cli invocation, saturation back-pressure (plan A2a/A3)."""

import asyncio
import json
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Tuple

from .cache import RenderCache, cache_key, font_fingerprint, sha256_bytes, sha256_file
from .config import MAX_PIXELS, MAX_SIDE_PX, Settings
from .sandbox import SandboxRunner
from .smoke import SMOKE_DXF

_BG_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_ALLOWED_FMT = ("png", "svg")
_ALLOWED_BG_NAMES = ("dark", "white")
MEDIA_TYPES = {"png": "image/png", "svg": "image/svg+xml"}


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
    # Optional explicit world window (xmin, ymin, xmax, ymax). When set, view is
    # "window" and render_cli is driven with --window instead of auto-extents.
    # Internal to the /diff common-window upgrade; the HTTP surface still only
    # parses view="extents" (a window is derived, never client-supplied in v0).
    window: Optional[Tuple[float, float, float, float]] = None

    @staticmethod
    def parse(fmt: str, width, height, bg: str, view: str) -> "RenderParams":
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
        if view != "extents":
            raise ParamError("view supports only 'extents' in v0")
        return RenderParams(fmt=fmt, width=w, height=h, bg=bg, view=view)

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
        # Include the window only when set, so non-windowed renders keep their
        # existing four-tuple cache keys unchanged.
        if self.window is not None:
            d["window"] = list(self.window)
        return d


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
        if params.window is not None:
            argv += ["--window", "%g,%g,%g,%g" % tuple(params.window)]
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
