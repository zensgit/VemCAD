"""FastAPI app for the render service (plan A2a/A3). Factory: create_app()."""

import hashlib
import json
from contextlib import asynccontextmanager
from typing import List, Optional

import anyio
from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from .config import Settings, load_settings
from .packagestore import PackageStore
from .renderer import MEDIA_TYPES, BusyError, ParamError, RenderFailed, RenderParams, RenderService
from .validator import validate_package

# A2b: only roles with cardinality ≤1 can serve as render inputs (a bare
# role cannot select a unique payload for 0..n roles).
_RENDERABLE_ROLES = ("twin-dxf", "twin-dxf-flattened")

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
    store = PackageStore(cfg.cache_dir / "packages")
    app.state.store = store

    # Every error leaves through the same structured envelope — including
    # FastAPI's own request validation (e.g. width=abc), which would
    # otherwise return its {"detail": [...]} shape.
    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = ".".join(str(p) for p in first.get("loc", ()))
        return _error(422, "BAD_PARAMS", ("%s: %s" % (loc, first.get("msg", "invalid request"))).strip(": "))

    @app.exception_handler(Exception)
    async def _internal_error(_: Request, exc: Exception):
        return _error(500, "INTERNAL", "%s: %s" % (type(exc).__name__, exc))

    @app.get("/healthz")
    async def healthz():
        smoke = state["smoke"]
        ok = svc.available and bool(smoke.get("ok"))
        # 503 when degraded so probes/LBs can key on the status code.
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
        return JSONResponse(status_code=200 if ok else 503, content=body)

    @app.post("/package")
    async def receive_package(
        manifest: UploadFile = File(...),
        payload: List[UploadFile] = File(default=[]),
    ):
        try:
            mdata = json.loads((await manifest.read()).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            return _error(422, "BAD_MANIFEST", "manifest is not valid JSON: %s" % e)

        payloads = {}
        total = 0
        for part in payload:
            data = await part.read()
            total += len(data)
            if total > 1024 * 1024 * 1024:  # contract §2.4 default package ceiling
                return _error(413, "PAYLOAD_TOO_LARGE", "package exceeds 1 GiB ceiling")
            payloads[hashlib.sha256(data).hexdigest()] = data

        result = await anyio.to_thread.run_sync(validate_package, mdata, payloads)
        report = result.report()
        if not result.ok_manifest:
            # Contract §9: an unparseable/unknown-major manifest is the only
            # outright rejection.
            return _error(422, "PACKAGE_REJECTED", report.get("error") or "manifest rejected")
        upsert = await anyio.to_thread.run_sync(store.save, mdata, payloads, report)
        body = dict(report)
        body["status"] = "ok"
        body["upsert"] = upsert
        return JSONResponse(status_code=200, content=body)

    @app.get("/package/{package_id}/report")
    async def package_report(package_id: str):
        report = store.get_report(package_id)
        if report is None:
            return _error(404, "PACKAGE_NOT_FOUND", "no package %s" % package_id)
        return JSONResponse(status_code=200, content=report)

    @app.post("/render")
    async def render(
        request: Request,
        file: Optional[UploadFile] = File(default=None),
        package_id: Optional[str] = Query(default=None),
        role: str = Query("twin-dxf"),
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

        # A2b: render a stored package payload referenced by (package_id, role).
        if package_id is not None:
            if role not in _RENDERABLE_ROLES:
                return _error(
                    404, "ROLE_NOT_RENDERABLE",
                    "role must be one of: %s" % ", ".join(_RENDERABLE_ROLES),
                )
            mdata = store.get_manifest(package_id)
            if mdata is None:
                return _error(404, "PACKAGE_NOT_FOUND", "no package %s" % package_id)
            sha = None
            for entry in mdata.get("files", []):
                if isinstance(entry, dict) and entry.get("role") == role:
                    sha = str(entry.get("sha256", "")).lower()
                    break
            content = store.get_payload(package_id, sha) if sha else None
            if content is None:
                return _error(404, "PAYLOAD_NOT_FOUND",
                              "package %s has no stored %s payload" % (package_id, role))
            try:
                path, key, hit = await svc.render_bytes(content, params, content_sha=sha)
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

        if file is None:
            return _error(422, "EMPTY_INPUT", "provide a DXF upload or a package_id")

        # v0 accepts DXF only (plan A3); .dwg is rejected up front, anything
        # else is validated by render_cli itself inside the sandbox.
        name = (file.filename or "").lower()
        if name.endswith(".dwg"):
            return _error(415, "UNSUPPORTED_INPUT", "v0 accepts DXF only (send the twin-dxf)")

        # Early reject when the client declares an oversized body.
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > cfg.max_upload_bytes + 64 * 1024:
            return _error(
                413, "PAYLOAD_TOO_LARGE",
                "input exceeds %d bytes (/render direct-upload cap)" % cfg.max_upload_bytes,
            )

        chunks = []
        total = 0
        hasher = hashlib.sha256()  # hash incrementally — keeps big hashes off the loop later
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
            hasher.update(chunk)
            chunks.append(chunk)
        if total == 0:
            return _error(422, "EMPTY_INPUT", "empty upload")
        content = b"".join(chunks)

        try:
            path, key, hit = await svc.render_bytes(content, params, content_sha=hasher.hexdigest())
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
