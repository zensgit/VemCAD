from fastapi.testclient import TestClient

from app.main import create_app
from conftest import needs_render_cli


def make_client(settings):
    return TestClient(create_app(settings))


@needs_render_cli
def test_healthz_ok(settings):
    with make_client(settings) as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["render_cli"]["available"] is True
        assert body["render_cli"]["smoke"]["ok"] is True
        assert body["fonts"]["fingerprint"] == "no-fonts"
        assert body["workers"]["max"] == 2


@needs_render_cli
def test_render_png_then_cache_hit(settings, fixture_dxf):
    with make_client(settings) as c:
        r = c.post(
            "/render?format=png&width=800&height=500",
            files={"file": ("block_ellipse.dxf", fixture_dxf, "application/octet-stream")},
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("image/png")
        assert r.headers["X-Render-Cache"] == "miss"
        assert len(r.content) > 1000
        key = r.headers["X-Render-Key"]

        r2 = c.post(
            "/render?format=png&width=800&height=500",
            files={"file": ("block_ellipse.dxf", fixture_dxf, "application/octet-stream")},
        )
        assert r2.status_code == 200
        assert r2.headers["X-Render-Cache"] == "hit"
        assert r2.headers["X-Render-Key"] == key
        assert r2.content == r.content


@needs_render_cli
def test_render_svg(settings, fixture_dxf):
    with make_client(settings) as c:
        r = c.post(
            "/render?format=svg&width=400&height=250&bg=white",
            files={"file": ("x.dxf", fixture_dxf, "application/octet-stream")},
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("image/svg")
        assert b"<svg" in r.content[:2000]


@needs_render_cli
def test_render_garbage_is_structured_error(settings):
    with make_client(settings) as c:
        r = c.post(
            "/render",
            files={"file": ("junk.dxf", b"this is not a dxf at all", "text/plain")},
        )
        assert r.status_code == 422
        body = r.json()
        assert body["status"] == "error"
        assert body["error_code"] == "RENDER_FAILED"


def test_bad_params_envelope(settings):
    with make_client(settings) as c:
        r = c.post(
            "/render?format=pdf",
            files={"file": ("x.dxf", b"0", "text/plain")},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "BAD_PARAMS"


def test_dwg_rejected(settings):
    with make_client(settings) as c:
        r = c.post(
            "/render",
            files={"file": ("a.dwg", b"AC1032", "application/octet-stream")},
        )
        assert r.status_code == 415
        assert r.json()["error_code"] == "UNSUPPORTED_INPUT"


def test_upload_cap(settings, tmp_path):
    from app.config import load_settings

    small = load_settings(
        render_cli=str(settings.render_cli) if settings.render_cli else None,
        cache_dir=str(tmp_path / "cache2"),
        max_upload_bytes=10,
        workers=1,
    )
    with make_client(small) as c:
        r = c.post(
            "/render",
            files={"file": ("x.dxf", b"0123456789ABCDEF", "text/plain")},
        )
        assert r.status_code == 413
        assert r.json()["error_code"] == "PAYLOAD_TOO_LARGE"


@needs_render_cli
def test_width_abc_gets_envelope(settings):
    with make_client(settings) as c:
        r = c.post(
            "/render?width=abc",
            files={"file": ("x.dxf", b"0", "text/plain")},
        )
        assert r.status_code == 422
        body = r.json()
        assert body["status"] == "error"
        assert body["error_code"] == "BAD_PARAMS"


def test_busy_429_and_cache_precedes_busy(settings, fixture_dxf, tmp_path):
    from app.config import load_settings
    from conftest import RENDER_CLI

    if RENDER_CLI is None:
        import pytest

        pytest.skip("render_cli binary not found")

    with make_client(settings) as c:
        # Warm the cache with a real render.
        r = c.post(
            "/render?format=png&width=400&height=250",
            files={"file": ("a.dxf", fixture_dxf, "application/octet-stream")},
        )
        assert r.status_code == 200

        # Saturate the workers artificially: cache hits must still be served
        # (cache check precedes the busy gate)...
        svc = c.app.state.svc
        svc.active = settings.workers
        try:
            r2 = c.post(
                "/render?format=png&width=400&height=250",
                files={"file": ("a.dxf", fixture_dxf, "application/octet-stream")},
            )
            assert r2.status_code == 200
            assert r2.headers["X-Render-Cache"] == "hit"

            # ...while a never-rendered input gets 429.
            r3 = c.post(
                "/render?format=png&width=401&height=250",
                files={"file": ("a.dxf", fixture_dxf, "application/octet-stream")},
            )
            assert r3.status_code == 429
            assert r3.json()["error_code"] == "BUSY"
        finally:
            svc.active = 0


def test_healthz_degraded_503(tmp_path):
    from app.config import load_settings

    cfg = load_settings(render_cli=None, cache_dir=str(tmp_path / "c"), workers=1)
    with make_client(cfg) as c:
        r = c.get("/healthz")
        assert r.status_code == 503
        assert r.json()["status"] == "degraded"
