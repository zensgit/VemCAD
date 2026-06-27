from fastapi.testclient import TestClient
from PIL import Image

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


def test_bad_style_envelope(settings):
    with make_client(settings) as c:
        r = c.post(
            "/render?style=screen",
            files={"file": ("x.dxf", b"0", "text/plain")},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "BAD_PARAMS"

        r2 = c.post(
            "/render?format=svg&style=acad-plot",
            files={"file": ("x.dxf", b"0", "text/plain")},
        )
        assert r2.status_code == 422
        assert r2.json()["error_code"] == "BAD_PARAMS"

        r3 = c.post(
            "/render?format=svg&style=acad-display",
            files={"file": ("x.dxf", b"0", "text/plain")},
        )
        assert r3.status_code == 422
        assert r3.json()["error_code"] == "BAD_PARAMS"

        r4 = c.post(
            "/render?format=svg&view=acad-plot",
            files={"file": ("x.dxf", b"0", "text/plain")},
        )
        assert r4.status_code == 422
        assert r4.json()["error_code"] == "BAD_PARAMS"


def test_render_acad_display_style_reaches_service_and_response_header(settings, tmp_path):
    with make_client(settings) as c:
        out = tmp_path / "fake.png"
        Image.new("RGB", (10, 10), "white").save(out)
        seen = {}

        async def fake_render_view_bytes(content, params, content_sha=None):
            seen["params"] = params
            seen["content_sha"] = content_sha
            return out, "style-key", False

        c.app.state.svc.render_view_bytes = fake_render_view_bytes
        r = c.post(
            "/render?format=png&width=200&height=100&bg=white&view=sheet&style=acad-display",
            files={"file": ("x.dxf", b"0\nEOF\n", "text/plain")},
        )
        assert r.status_code == 200, r.text
        assert seen["params"].style == "acad-display"
        assert seen["params"].view == "sheet"
        assert r.headers["X-Render-Style"] == "acad-display"
        assert r.headers["X-Render-Key"] == "style-key"


def test_render_acad_plot_view_reaches_service_and_response_header(settings, tmp_path):
    with make_client(settings) as c:
        out = tmp_path / "fake.png"
        Image.new("RGB", (10, 10), "white").save(out)
        seen = {}

        async def fake_render_view_bytes(content, params, content_sha=None):
            seen["params"] = params
            return out, "plot-view-key", False

        c.app.state.svc.render_view_bytes = fake_render_view_bytes
        c.app.state.svc.cache.get_report = lambda key: {
            "params": {"view": "acad-plot"},
            "acad_plot_frame": {"mode": "framed"},
        }

        r = c.post(
            "/render?format=png&width=200&height=100&bg=white&view=acad-plot&style=acad-display",
            files={"file": ("x.dxf", b"0\nEOF\n", "text/plain")},
        )

        assert r.status_code == 200, r.text
        assert seen["params"].view == "acad-plot"
        assert seen["params"].style == "acad-display"
        assert r.headers["X-Render-Resolved-View"] == "acad-plot"
        assert r.headers["X-Render-Acad-Plot-Mode"] == "framed"
        assert r.headers["X-Render-Style"] == "acad-display"


def test_render_sheet_mode_header_comes_from_cached_report(settings, tmp_path):
    with make_client(settings) as c:
        out = tmp_path / "fake.png"
        Image.new("RGB", (10, 10), "white").save(out)

        async def fake_render_view_bytes(content, params, content_sha=None):
            return out, "sheet-key", False

        c.app.state.svc.render_view_bytes = fake_render_view_bytes
        c.app.state.svc.cache.get_report = lambda key: {"params": {"view": "window"}}

        r = c.post(
            "/render?format=png&width=200&height=100&bg=white&view=sheet",
            files={"file": ("x.dxf", b"0\nEOF\n", "text/plain")},
        )
        assert r.status_code == 200, r.text
        assert r.headers["X-Render-Resolved-View"] == "window"
        assert r.headers["X-Render-Sheet-Mode"] == "detected"


def test_render_sheet_mode_header_reports_fallback(settings, tmp_path):
    with make_client(settings) as c:
        out = tmp_path / "fake.png"
        Image.new("RGB", (10, 10), "white").save(out)

        async def fake_render_view_bytes(content, params, content_sha=None):
            return out, "sheet-key", False

        c.app.state.svc.render_view_bytes = fake_render_view_bytes
        c.app.state.svc.cache.get_report = lambda key: {"params": {"view": "extents"}}

        r = c.post(
            "/render?format=png&width=200&height=100&bg=white&view=sheet",
            files={"file": ("x.dxf", b"0\nEOF\n", "text/plain")},
        )
        assert r.status_code == 200, r.text
        assert r.headers["X-Render-Resolved-View"] == "extents"
        assert r.headers["X-Render-Sheet-Mode"] == "fallback"


@needs_render_cli
def test_acad_plot_style_does_not_affect_sheet_view_resolution(settings, fixture_dxf):
    """style=acad-plot (grayscale postprocess) and view=sheet (sheet detection) are
    orthogonal. The grayscale runs on the final PNG, AFTER view resolution, so a real
    render must produce identical sheet-detection / fallback headers whether or not the
    plot style is applied — only the pixels differ, never the view."""

    def render(c, style):
        r = c.post(
            f"/render?format=png&width=800&height=500&view=sheet&style={style}",
            files={"file": ("block_ellipse.dxf", fixture_dxf, "application/octet-stream")},
        )
        assert r.status_code == 200, r.text
        return r

    with make_client(settings) as c:
        plot = render(c, "acad-plot")
        src = render(c, "source")

    # The plot style is applied only to acad-plot (and reaches the response).
    assert plot.headers["X-Render-Style"] == "acad-plot"
    assert src.headers["X-Render-Style"] == "source"

    # Sheet detection / fallback is UNAFFECTED by the grayscale postprocess: the
    # view-resolution headers are identical across the two styles.
    for h in ("X-Render-Resolved-View", "X-Render-Sheet-Mode"):
        assert plot.headers.get(h) == src.headers.get(h), (
            f"{h} differs by style: acad-plot={plot.headers.get(h)!r} source={src.headers.get(h)!r}"
        )


def test_acad_plot_style_leaves_sheet_mode_headers_unchanged(settings, tmp_path):
    """Orthogonality, proven in CI (no render_cli): with style=acad-plot the sheet-mode /
    resolved-view headers are exactly what the source style yields — detected when the
    report carries a sheet view, fallback otherwise. The grayscale postprocess runs on the
    final PNG, after view resolution, so it cannot change these headers. Mirrors the
    source-style sheet-header tests above, with style=acad-plot added."""
    with make_client(settings) as c:
        out = tmp_path / "fake.png"
        Image.new("RGB", (10, 10), "white").save(out)

        async def fake_render_view_bytes(content, params, content_sha=None):
            return out, "k", False

        c.app.state.svc.render_view_bytes = fake_render_view_bytes

        c.app.state.svc.cache.get_report = lambda key: {"params": {"view": "window"}}
        r = c.post(
            "/render?format=png&width=200&height=100&bg=white&view=sheet&style=acad-plot",
            files={"file": ("x.dxf", b"0\nEOF\n", "text/plain")},
        )
        assert r.status_code == 200, r.text
        assert r.headers["X-Render-Style"] == "acad-plot"
        assert r.headers["X-Render-Resolved-View"] == "window"
        assert r.headers["X-Render-Sheet-Mode"] == "detected"

        c.app.state.svc.cache.get_report = lambda key: {"params": {"view": "extents"}}
        r2 = c.post(
            "/render?format=png&width=200&height=100&bg=white&view=sheet&style=acad-plot",
            files={"file": ("x.dxf", b"0\nEOF\n", "text/plain")},
        )
        assert r2.status_code == 200, r2.text
        assert r2.headers["X-Render-Resolved-View"] == "extents"
        assert r2.headers["X-Render-Sheet-Mode"] == "fallback"


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
