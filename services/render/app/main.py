"""FastAPI app for the render service (plan A2a/A3). Factory: create_app()."""

from contextlib import asynccontextmanager
from typing import Optional

import anyio
from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .config import Settings, load_settings
from .renderer import MEDIA_TYPES, BusyError, ParamError, RenderFailed, RenderParams, RenderService

_READ_CHUNK = 1 << 20


def _error(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "error_code": error_code, "error": message},
    )


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    cfg = settings or load_settings()
    svc = RenderService(cfg)
    state = {"smoke": {"ok": None, "detail": "not run"}}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state["smoke"] = await anyio.to_thread.run_sync(svc.smoke)
        yield

    app = FastAPI(title="vemcad-render", version="0.1.0", lifespan=lifespan)
    app.state.svc = svc

    @app.get("/healthz")
    async def healthz():
        smoke = state["smoke"]
        ok = svc.available and bool(smoke.get("ok"))
        body = {
            "status": "ok" if ok else "degraded",
            "render_cli": {
                "path": str(cfg.render_cli) if cfg.render_cli else None,
                "sha256": svc.cli_sha,
                "available": svc.available,
                "smoke": smoke,
            },
            "fonts": {
                "dir": str(cfg.font_dir) if cfg.font_dir else None,
                "count": svc.font_count(),
                "fingerprint": svc.font_fp,
            },
            "workers": {"max": cfg.workers, "active": svc.active},
        }
        return JSONResponse(status_code=200, content=body)

    @app.post("/render")
    async def render(
        request: Request,
        file: UploadFile = File(...),
        format: str = Query("png"),
        width: int = Query(2400),
        height: int = Query(1697),
        bg: str = Query("dark"),
        view: str = Query("extents"),
    ):
        try:
            params = RenderParams.parse(format, width, height, bg, view)
        except ParamError as e:
            return _error(422, e.error_code, str(e))

        # v0 accepts DXF only (plan A3); .dwg is rejected up front, anything
        # else is validated by render_cli itself inside the sandbox.
        name = (file.filename or "").lower()
        if name.endswith(".dwg"):
            return _error(415, "UNSUPPORTED_INPUT", "v0 accepts DXF only (send the twin-dxf)")

        chunks = []
        total = 0
        while True:
            chunk = await file.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > cfg.max_upload_bytes:
                return _error(
                    413, "PAYLOAD_TOO_LARGE",
                    "input exceeds %d bytes (/render direct-upload cap)" % cfg.max_upload_bytes,
                )
            chunks.append(chunk)
        if total == 0:
            return _error(422, "EMPTY_INPUT", "empty upload")
        content = b"".join(chunks)

        try:
            path, key, hit = await svc.render_bytes(content, params)
        except BusyError:
            return _error(429, "BUSY", "render workers saturated, retry later")
        except RenderFailed as e:
            detail = ("%s — %s" % (e, e.detail)).strip(" —")
            return _error(422, "RENDER_FAILED", detail)

        return FileResponse(
            path,
            media_type=MEDIA_TYPES[params.fmt],
            headers={"X-Render-Cache": "hit" if hit else "miss", "X-Render-Key": key},
        )

    return app


def app() -> FastAPI:  # uvicorn --factory entry point
    return create_app()
