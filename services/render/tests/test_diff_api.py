"""POST /diff tests. The endpoint wiring + comparability + caching + envelope
are exercised locally by STUBBING the renderer (the real diff engine still
runs — numpy/Pillow are present in dev), so no render_cli is needed. The full
DXF -> render -> overlay path runs render_cli-gated (skips locally, runs in the
CI image where render_cli AND numpy/Pillow exist — that E2E also fails loudly
if the diff deps are missing, rather than silently degrading to 501)."""

from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

import app.diffrunner as diffrunner
from app.main import create_app
from conftest import RENDER_CLI, needs_render_cli


def make_client(settings):
    return TestClient(create_app(settings))


def _png(path, *, lines, size=(420, 300)):
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, size[0] - 20, size[1] - 20], outline=(0, 0, 0), width=3)
    for (x0, y0, x1, y1) in lines:
        d.line([x0, y0, x1, y1], fill=(0, 0, 0), width=3)
    im.save(path)
    return Path(path)


def _box_png(path, *, x0, y0, x1, y1, size=(420, 300)):
    im = Image.new("RGB", size, (255, 255, 255))
    ImageDraw.Draw(im).rectangle([x0, y0, x1, y1], outline=(0, 0, 0), width=3)
    im.save(path)
    return Path(path)


def _stub_renderer(client, mapping):
    """Patch svc.render_bytes to return pre-baked PNG paths by upload bytes."""
    async def fake_render(content, params, content_sha=None):
        return mapping[content], "stub-key", False
    client.app.state.svc.render_bytes = fake_render


DXF_A = b"DXF-REV-A-BYTES"
DXF_B = b"DXF-REV-B-BYTES"


# ---- envelope / validation (no renderer needed) ----

def test_diff_missing_second_file_is_envelope(settings):
    with make_client(settings) as c:
        r = c.post("/diff", files={"file_a": ("a.dxf", DXF_A, "application/octet-stream")})
        assert r.status_code == 422
        assert r.json()["error_code"] == "EMPTY_INPUT"


def test_diff_dwg_rejected(settings):
    with make_client(settings) as c:
        r = c.post("/diff", files={
            "file_a": ("a.dwg", b"AC1032", "application/octet-stream"),
            "file_b": ("b.dxf", DXF_B, "application/octet-stream"),
        })
        assert r.status_code == 415
        assert r.json()["error_code"] == "UNSUPPORTED_INPUT"


def test_diff_bad_params_envelope(settings):
    with make_client(settings) as c:
        r = c.post("/diff?width=abc", files={
            "file_a": ("a.dxf", DXF_A, "application/octet-stream"),
            "file_b": ("b.dxf", DXF_B, "application/octet-stream"),
        })
        assert r.status_code == 422
        assert r.json()["error_code"] == "BAD_PARAMS"


# ---- diff path with the real engine, stubbed renderer ----

def test_diff_overlay_and_cache(settings, tmp_path):
    ref = _png(tmp_path / "ref.png", lines=[(40, 150, 380, 150)])              # 1 line
    cand = _png(tmp_path / "cand.png", lines=[(40, 150, 380, 150), (40, 90, 380, 90)])  # +1
    with make_client(settings) as c:
        _stub_renderer(c, {DXF_A: ref, DXF_B: cand})
        r = c.post("/diff?width=420&height=300&bg=white", files={
            "file_a": ("a.dxf", DXF_A, "application/octet-stream"),
            "file_b": ("b.dxf", DXF_B, "application/octet-stream"),
        })
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("image/png")
        assert r.headers["X-Diff-Comparable"] == "true"
        assert int(r.headers["X-Diff-Added-Px"]) > 0          # the new line
        assert float(r.headers["X-Diff-Changed-Fraction"]) > 0.0
        assert r.headers["X-Diff-Cache"] == "miss"
        key = r.headers["X-Diff-Key"]

        r2 = c.post("/diff?width=420&height=300&bg=white", files={
            "file_a": ("a.dxf", DXF_A, "application/octet-stream"),
            "file_b": ("b.dxf", DXF_B, "application/octet-stream"),
        })
        assert r2.status_code == 200
        assert r2.headers["X-Diff-Cache"] == "hit"
        assert r2.headers["X-Diff-Key"] == key
        assert r2.content == r.content


def test_diff_cache_lost_artifact_rerenders(settings, tmp_path):
    # Report survives but the overlay PNG is evicted/truncated: a comparable
    # diff must re-render (miss) and return the image — never a 200-JSON-no-PNG.
    ref = _png(tmp_path / "ref.png", lines=[(40, 150, 380, 150)])
    cand = _png(tmp_path / "cand.png", lines=[(40, 150, 380, 150), (40, 90, 380, 90)])
    with make_client(settings) as c:
        _stub_renderer(c, {DXF_A: ref, DXF_B: cand})
        files = {
            "file_a": ("a.dxf", DXF_A, "application/octet-stream"),
            "file_b": ("b.dxf", DXF_B, "application/octet-stream"),
        }
        r = c.post("/diff?width=420&height=300&bg=white", files=files)
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/png")
        key = r.headers["X-Diff-Key"]
        artifact = Path(settings.cache_dir) / key[:2] / (key + ".png")
        assert artifact.is_file()
        artifact.unlink()                       # lose the overlay, keep the report
        r2 = c.post("/diff?width=420&height=300&bg=white", files=files)
        assert r2.status_code == 200
        assert r2.headers["content-type"].startswith("image/png")  # re-rendered, not JSON
        assert r2.headers["X-Diff-Cache"] == "miss"


def test_diff_summary_only_json(settings, tmp_path):
    ref = _png(tmp_path / "ref.png", lines=[(40, 150, 380, 150)])
    cand = _png(tmp_path / "cand.png", lines=[(40, 150, 380, 150), (40, 90, 380, 90)])
    with make_client(settings) as c:
        _stub_renderer(c, {DXF_A: ref, DXF_B: cand})
        r = c.post("/diff?summary_only=true&width=420&height=300&bg=white", files={
            "file_a": ("a.dxf", DXF_A, "application/octet-stream"),
            "file_b": ("b.dxf", DXF_B, "application/octet-stream"),
        })
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")
        body = r.json()
        assert body["status"] == "ok"
        assert body["comparable"] is True
        assert body["added_px"] > 0
        assert "source_sha256" in body
        assert "overlay_path" not in body   # no internal/ephemeral server path leaks


# ---- common-window provenance must reach the client (HTTP layer) ----

def _dxf_bytes(extmin, extmax):
    """Minimal DXF HEADER carrying $EXTMIN/$EXTMAX so DiffService's extents
    parse engages the common-window path on a real upload."""
    lines = ["0", "SECTION", "2", "HEADER",
             "9", "$EXTMIN", "10", str(extmin[0]), "20", str(extmin[1]),
             "9", "$EXTMAX", "10", str(extmax[0]), "20", str(extmax[1]),
             "0", "ENDSEC", "0", "EOF", ""]
    return "\n".join(lines).encode("ascii")


def test_diff_common_window_passthrough(settings, tmp_path):
    # Differing HEADER extents → union window engages; the new provenance must
    # reach the client on BOTH the image response (header) and JSON summary, so
    # a future header-trim can't silently drop X-Diff-Common-Window/common_window.
    a = _dxf_bytes((0.0, 0.0), (100.0, 100.0))
    b = _dxf_bytes((0.0, 0.0), (200.0, 100.0))                 # grew in X
    ref = _box_png(tmp_path / "ref.png", x0=40, y0=110, x1=160, y1=190)
    cand = _box_png(tmp_path / "cand.png", x0=40, y0=110, x1=380, y1=190)
    with make_client(settings) as c:
        _stub_renderer(c, {a: ref, b: cand})
        r = c.post("/diff?width=420&height=300&bg=white", files={
            "file_a": ("a.dxf", a, "application/octet-stream"),
            "file_b": ("b.dxf", b, "application/octet-stream"),
        })
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("image/png")
        assert r.headers["X-Diff-Comparable"] == "true"
        assert r.headers["X-Diff-Common-Window"] == "0.0,0.0,200.0,100.0"
        assert int(r.headers["X-Diff-Added-Px"]) > 0

        rj = c.post("/diff?summary_only=true&width=420&height=300&bg=white", files={
            "file_a": ("a.dxf", a, "application/octet-stream"),
            "file_b": ("b.dxf", b, "application/octet-stream"),
        })
        assert rj.status_code == 200
        body = rj.json()
        assert body["common_window"] == [0.0, 0.0, 200.0, 100.0]
        assert body["comparable"] is True


def test_diff_no_common_window_header_when_extents_equal(settings, tmp_path):
    # Equal extents → no window → header/field absent (legacy path untouched).
    a = _dxf_bytes((0.0, 0.0), (100.0, 100.0))
    b = _dxf_bytes((0.0, 0.0), (100.0, 100.0)) + b"999\ncomment\n"  # same extents, diff bytes
    ref = _box_png(tmp_path / "ref.png", x0=60, y0=110, x1=360, y1=190)
    cand = _box_png(tmp_path / "cand.png", x0=60, y0=110, x1=360, y1=190)
    with make_client(settings) as c:
        _stub_renderer(c, {a: ref, b: cand})
        r = c.post("/diff?summary_only=true&width=420&height=300&bg=white", files={
            "file_a": ("a.dxf", a, "application/octet-stream"),
            "file_b": ("b.dxf", b, "application/octet-stream"),
        })
        assert r.status_code == 200
        assert "X-Diff-Common-Window" not in r.headers
        assert "common_window" not in r.json()


def test_diff_view_space_mismatch_is_flagged(settings, tmp_path):
    # Different ink-bbox aspects → not a shared view-space → flagged, no overlay.
    ref = _box_png(tmp_path / "ref.png", x0=40, y0=100, x1=340, y1=200)   # wide
    cand = _box_png(tmp_path / "cand.png", x0=110, y0=50, x1=310, y1=250)  # square
    with make_client(settings) as c:
        _stub_renderer(c, {DXF_A: ref, DXF_B: cand})
        r = c.post("/diff?width=420&height=300&bg=white", files={
            "file_a": ("a.dxf", DXF_A, "application/octet-stream"),
            "file_b": ("b.dxf", DXF_B, "application/octet-stream"),
        })
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")
        assert r.headers["X-Diff-Comparable"] == "false"
        assert r.headers["X-Diff-Skip-Reason"] == "view-space-mismatch"
        assert r.json()["comparable"] is False


def test_diff_engine_unavailable_returns_501(settings, monkeypatch):
    def boom():
        raise diffrunner.DiffUnavailable("numpy not installed (simulated)")
    monkeypatch.setattr(diffrunner, "_load_engine", boom)
    with make_client(settings) as c:
        r = c.post("/diff", files={
            "file_a": ("a.dxf", DXF_A, "application/octet-stream"),
            "file_b": ("b.dxf", DXF_B, "application/octet-stream"),
        })
        assert r.status_code == 501
        assert r.json()["error_code"] == "DIFF_UNAVAILABLE"


# ---- full pipeline through the real renderer (CI image) ----

@needs_render_cli
def test_diff_e2e_self_is_comparable(settings, fixture_dxf):
    """Diff the fixture against itself through the real render_cli: proves
    render x2 -> overlay -> cache end-to-end. Identical input -> comparable,
    near-zero change. (Also fails loudly if numpy/Pillow are absent in CI.)"""
    with make_client(settings) as c:
        r = c.post("/diff?width=600&height=400&bg=white", files={
            "file_a": ("rev_a.dxf", fixture_dxf, "application/octet-stream"),
            "file_b": ("rev_b.dxf", fixture_dxf, "application/octet-stream"),
        })
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("image/png")
        assert r.headers["X-Diff-Comparable"] == "true"
        assert float(r.headers["X-Diff-Changed-Fraction"]) < 0.02   # same drawing
        assert len(r.content) > 1000

        r2 = c.post("/diff?width=600&height=400&bg=white", files={
            "file_a": ("rev_a.dxf", fixture_dxf, "application/octet-stream"),
            "file_b": ("rev_b.dxf", fixture_dxf, "application/octet-stream"),
        })
        assert r2.headers["X-Diff-Cache"] == "hit"
