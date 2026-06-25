"""FastAPI app for the render service (plan A2a/A3). Factory: create_app()."""

import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from typing import List, Optional

import anyio
from fastapi import FastAPI, File, Header, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from .config import Settings, load_settings
from .diffrunner import DIFF_MEDIA_TYPE, DiffService, DiffUnavailable
from .packagestore import PackageStore
from .renderer import MEDIA_TYPES, BusyError, ParamError, RenderFailed, RenderParams, RenderService
from .validator import validate_package

# A2b: only roles with cardinality ≤1 can serve as render inputs (a bare
# role cannot select a unique payload for 0..n roles).
_RENDERABLE_ROLES = ("twin-dxf", "twin-dxf-flattened")

_READ_CHUNK = 1 << 20
_MANIFEST_CAP = 16 * 1024 * 1024  # a manifest is JSON, not a payload
_PACKAGE_CAP = 1024 * 1024 * 1024  # contract §2.4 package total ceiling


def _error(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "error_code": error_code, "error": message},
    )


def _auth_failed(authorization: Optional[str], auth_token: Optional[str]):
    """Optional bearer-token gate for the data endpoints. `auth_token` falsy →
    no auth (Phase-1 trusted-internal status quo). Returns an error response on
    failure, else None.

    Compares as BYTES (constant-time) so a non-ASCII Authorization header fails
    closed with a clean 401 instead of raising in hmac.compare_digest (which
    rejects non-ASCII str) and becoming a 500. latin-1 round-trips Starlette's
    header decode losslessly; a non-ASCII configured token can't encode, so the
    `ignore`+guard make it fail closed rather than brick the service."""
    if not auth_token:
        return None
    ok = False
    if authorization:
        try:
            ok = hmac.compare_digest(
                authorization.encode("latin-1", "ignore"),
                ("Bearer %s" % auth_token).encode("latin-1", "ignore"),
            )
        except Exception:
            ok = False
    if not ok:
        return _error(401, "UNAUTHORIZED", "missing or invalid bearer token")
    return None


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
    diffsvc = DiffService(svc)
    app.state.diffsvc = diffsvc
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

    async def _read_capped(part: UploadFile, cap: int):
        chunks, total, hasher = [], 0, hashlib.sha256()
        while True:
            chunk = await part.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                return None, total
            hasher.update(chunk)
            chunks.append(chunk)
        return b"".join(chunks), total

    def _render_headers(params: RenderParams, key: str, hit: bool) -> dict:
        headers = {
            "X-Render-Cache": "hit" if hit else "miss",
            "X-Render-Key": key,
            "X-Render-Style": params.style,
        }
        report = svc.cache.get_report(key) or {}
        resolved = (report.get("params") or {}).get("view") if isinstance(report, dict) else None
        if resolved:
            headers["X-Render-Resolved-View"] = str(resolved)
        if params.view == "sheet":
            if resolved == "window":
                headers["X-Render-Sheet-Mode"] = "detected"
            elif resolved == "extents":
                headers["X-Render-Sheet-Mode"] = "fallback"
            else:
                headers["X-Render-Sheet-Mode"] = "unknown"
        return headers

    @app.post("/package")
    async def receive_package(
        manifest: UploadFile = File(...),
        payload: List[UploadFile] = File(default=[]),
        authorization: Optional[str] = Header(default=None),
    ):
        auth_err = _auth_failed(authorization, cfg.auth_token)
        if auth_err is not None:
            return auth_err
        manifest_bytes, _ = await _read_capped(manifest, _MANIFEST_CAP)
        if manifest_bytes is None:
            return _error(413, "PAYLOAD_TOO_LARGE", "manifest exceeds %d bytes" % _MANIFEST_CAP)
        try:
            mdata = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            return _error(422, "BAD_MANIFEST", "manifest is not valid JSON: %s" % e)

        # Stream payload parts, aborting the instant the cumulative package
        # ceiling is crossed (never buffer a part larger than the budget).
        payloads = {}
        budget = _PACKAGE_CAP
        for part in payload:
            data, _ = await _read_capped(part, budget)
            if data is None:
                return _error(413, "PAYLOAD_TOO_LARGE", "package exceeds 1 GiB ceiling")
            budget -= len(data)
            payloads[hashlib.sha256(data).hexdigest()] = data

        result = await anyio.to_thread.run_sync(validate_package, mdata, payloads)
        report = result.report()
        if not result.ok_manifest:
            # Contract §9: an unparseable / unknown-major / identity-broken
            # manifest is the only outright rejection — return the full report.
            body = dict(report)
            body["status"] = "error"
            body["error_code"] = "PACKAGE_REJECTED"
            body["error"] = report.get("error") or "manifest rejected"
            return JSONResponse(status_code=422, content=body)
        try:
            upsert = await anyio.to_thread.run_sync(store.save, mdata, payloads, report)
        except ValueError as e:
            return _error(409, "IDENTITY_CONFLICT", str(e))
        body = dict(report)
        body["status"] = "ok"
        body["upsert"] = upsert
        return JSONResponse(status_code=200, content=body)

    @app.get("/package/{package_id}/report")
    async def package_report(package_id: str, authorization: Optional[str] = Header(default=None)):
        auth_err = _auth_failed(authorization, cfg.auth_token)
        if auth_err is not None:
            return auth_err
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
        style: str = Query("source"),
        authorization: Optional[str] = Header(default=None),
    ):
        auth_err = _auth_failed(authorization, cfg.auth_token)
        if auth_err is not None:
            return auth_err
        try:
            params = RenderParams.parse(format, width, height, bg, view, style)
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
            # Never render a payload that validation quarantined (§9: quarantined
            # entries are dropped from the effective set, kept only for diagnosis).
            stored_report = store.get_report(package_id) or {}
            quarantined_shas = {
                str(q.get("sha256", "")).lower() for q in stored_report.get("quarantined", [])
            }
            sha = None
            for entry in mdata.get("files", []):
                if isinstance(entry, dict) and entry.get("role") == role:
                    cand = str(entry.get("sha256", "")).lower()
                    if cand in quarantined_shas:
                        continue
                    sha = cand
                    break
            content = store.get_payload(package_id, sha) if sha else None
            if content is None:
                return _error(404, "PAYLOAD_NOT_FOUND",
                              "package %s has no stored %s payload" % (package_id, role))
            try:
                path, key, hit = await svc.render_view_bytes(content, params, content_sha=sha)
            except BusyError:
                return _error(429, "BUSY", "render workers saturated, retry later")
            except RenderFailed as e:
                detail = ("%s — %s" % (e, e.detail)).strip(" —")
                return _error(422, "RENDER_FAILED", detail)
            return FileResponse(
                path,
                media_type=MEDIA_TYPES[params.fmt],
                headers=_render_headers(params, key, hit),
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
            path, key, hit = await svc.render_view_bytes(content, params, content_sha=hasher.hexdigest())
        except BusyError:
            return _error(429, "BUSY", "render workers saturated, retry later")
        except RenderFailed as e:
            detail = ("%s — %s" % (e, e.detail)).strip(" —")
            return _error(422, "RENDER_FAILED", detail)

        return FileResponse(
            path,
            media_type=MEDIA_TYPES[params.fmt],
            headers=_render_headers(params, key, hit),
        )

    async def _read_dxf_upload(part: UploadFile, label: str):
        """Read one DXF upload for /diff: reject .dwg, enforce the upload cap,
        reject empty. Returns (content, sha256, None) or (None, None, error)."""
        name = (part.filename or "").lower()
        if name.endswith(".dwg"):
            return None, None, _error(
                415, "UNSUPPORTED_INPUT", "v0 accepts DXF only (%s: send the twin-dxf)" % label)
        content, total = await _read_capped(part, cfg.max_upload_bytes)
        if content is None:
            return None, None, _error(
                413, "PAYLOAD_TOO_LARGE",
                "%s exceeds %d bytes (/diff upload cap)" % (label, cfg.max_upload_bytes))
        if total == 0:
            return None, None, _error(422, "EMPTY_INPUT", "%s is empty" % label)
        return content, hashlib.sha256(content).hexdigest(), None

    def _diff_headers(summary: dict, key: str, hit: bool) -> dict:
        h = {
            "X-Diff-Cache": "hit" if hit else "miss",
            "X-Diff-Key": key,
            "X-Diff-Comparable": "true" if summary.get("comparable") else "false",
            "X-Diff-Changed-Fraction": str(summary.get("changed_fraction", 0.0)),
            "X-Diff-Added-Px": str(summary.get("added_px", 0)),
            "X-Diff-Removed-Px": str(summary.get("removed_px", 0)),
            "X-Diff-Unchanged-Px": str(summary.get("unchanged_px", 0)),
        }
        if summary.get("skip_reason"):
            h["X-Diff-Skip-Reason"] = str(summary["skip_reason"])
        # Present when the common-window upgrade fired (both revisions rendered
        # in their union world rect so extents-changing revisions diff cleanly).
        if summary.get("common_window"):
            h["X-Diff-Common-Window"] = ",".join(repr(float(v)) for v in summary["common_window"])
        # Provenance for fast triage (full detail in summary.diagnostics): how the diff
        # was framed (real content_bbox vs header fallback) and whether the per-extents
        # base renders were reused. X-Diff-Cache above already shows the diff-overlay hit.
        diag = summary.get("diagnostics") or {}
        if diag.get("window_source"):
            h["X-Diff-Window-Source"] = str(diag["window_source"])
            h["X-Diff-Header-Fallback"] = "true" if diag.get("header_fallback") else "false"
            h["X-Diff-Base-Reuse"] = "true" if diag.get("base_render_reuse") else "false"
        return h

    @app.post("/diff")
    async def diff(
        file_a: Optional[UploadFile] = File(default=None),
        file_b: Optional[UploadFile] = File(default=None),
        width: int = Query(2400),
        height: int = Query(1697),
        bg: str = Query("dark"),
        view: str = Query("extents"),
        style: str = Query("source"),
        summary_only: bool = Query(False),
        authorization: Optional[str] = Header(default=None),
    ):
        auth_err = _auth_failed(authorization, cfg.auth_token)
        if auth_err is not None:
            return auth_err
        # Both revisions render at THESE params → §5 bg + colour-mapping shared
        # by construction. The overlay is always PNG (raster diff).
        try:
            params = RenderParams.parse("png", width, height, bg, view, style)
        except ParamError as e:
            return _error(422, e.error_code, str(e))

        if file_a is None or file_b is None:
            return _error(422, "EMPTY_INPUT",
                          "provide two DXF uploads: file_a (Rev A) and file_b (Rev B)")

        content_a, sha_a, err = await _read_dxf_upload(file_a, "file_a")
        if err is not None:
            return err
        content_b, sha_b, err = await _read_dxf_upload(file_b, "file_b")
        if err is not None:
            return err

        try:
            overlay_path, summary, key, hit = await diffsvc.diff_bytes(
                content_a, content_b, params, sha_a=sha_a, sha_b=sha_b)
        except DiffUnavailable as e:
            return _error(501, "DIFF_UNAVAILABLE", str(e))
        except BusyError:
            return _error(429, "BUSY", "render workers saturated, retry later")
        except RenderFailed as e:
            detail = ("%s — %s" % (e, e.detail)).strip(" —")
            return _error(422, "RENDER_FAILED", detail)

        headers = _diff_headers(summary, key, hit)
        # JSON when the caller wants only metrics, OR when there is no overlay
        # (not comparable / both-blank) — the summary carries the honest reason.
        if summary_only or overlay_path is None:
            return JSONResponse(status_code=200, content={"status": "ok", **summary},
                                headers=headers)
        return FileResponse(overlay_path, media_type=DIFF_MEDIA_TYPE, headers=headers)

    return app


def app() -> FastAPI:  # uvicorn --factory entry point
    return create_app()
