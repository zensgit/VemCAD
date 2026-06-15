"""Optional bearer-token auth on the data endpoints. No render_cli needed: the
auth gate runs before any rendering, and a correct token simply falls through to
normal request validation."""

from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import _auth_failed, create_app


# --- module-level _auth_failed (covers cases httpx blocks end-to-end) ---

def test_auth_helper_disabled_returns_none():
    assert _auth_failed(None, None) is None
    assert _auth_failed("anything", "") is None      # empty token = disabled


def test_auth_helper_correct_wrong_missing():
    assert _auth_failed("Bearer s3cret", "s3cret") is None
    assert _auth_failed("Bearer nope", "s3cret").status_code == 401
    assert _auth_failed(None, "s3cret").status_code == 401
    assert _auth_failed("", "s3cret").status_code == 401
    assert _auth_failed("s3cret", "s3cret").status_code == 401          # no "Bearer "
    assert _auth_failed("Bearer s3cret ", "s3cret").status_code == 401  # trailing space


def test_auth_helper_non_ascii_header_fails_closed():
    # P1 regression: a non-ASCII Authorization byte must yield a clean 401,
    # NOT raise (hmac.compare_digest rejects non-ASCII str → would be a 500).
    resp = _auth_failed("Bearer \xe9", "s3cret")
    assert resp is not None and resp.status_code == 401


def test_auth_helper_non_ascii_token_fails_closed():
    # P3a regression: a non-ASCII configured token must not 500 — clean 401.
    resp = _auth_failed("Bearer x", "令牌")
    assert resp is not None and resp.status_code == 401


def _client(tmp_path, *, token=None):
    cfg = load_settings(render_cli=None, cache_dir=str(tmp_path / "c"), workers=1, auth_token=token)
    return TestClient(create_app(cfg))


def test_auth_disabled_is_status_quo(tmp_path):
    # No RENDER_AUTH_TOKEN → no auth: /diff with one file reaches validation, not 401.
    with _client(tmp_path) as c:
        r = c.post("/diff", files={"file_a": ("a.dxf", b"0", "application/octet-stream")})
        assert r.status_code == 422
        assert r.json()["error_code"] == "EMPTY_INPUT"


def test_missing_token_rejected_when_enabled(tmp_path):
    with _client(tmp_path, token="s3cret") as c:
        r = c.post("/diff", files={
            "file_a": ("a.dxf", b"0", "application/octet-stream"),
            "file_b": ("b.dxf", b"0", "application/octet-stream"),
        })
        assert r.status_code == 401
        assert r.json()["error_code"] == "UNAUTHORIZED"


def test_wrong_token_rejected(tmp_path):
    with _client(tmp_path, token="s3cret") as c:
        r = c.post("/render", headers={"Authorization": "Bearer nope"},
                   files={"file": ("a.dxf", b"0", "application/octet-stream")})
        assert r.status_code == 401
        assert r.json()["error_code"] == "UNAUTHORIZED"


def test_correct_token_passes_auth(tmp_path):
    # Correct token → past auth → normal validation (only file_a → EMPTY_INPUT, not 401).
    with _client(tmp_path, token="s3cret") as c:
        r = c.post("/diff", headers={"Authorization": "Bearer s3cret"},
                   files={"file_a": ("a.dxf", b"0", "application/octet-stream")})
        assert r.status_code == 422
        assert r.json()["error_code"] == "EMPTY_INPUT"


def test_package_endpoint_requires_auth(tmp_path):
    with _client(tmp_path, token="s3cret") as c:
        r = c.post("/package", files={"manifest": ("m.json", b"{}", "application/json")})
        assert r.status_code == 401
        assert r.json()["error_code"] == "UNAUTHORIZED"


def test_healthz_stays_open_with_auth(tmp_path):
    # Probes/LBs must reach /healthz without a token even when auth is enabled.
    with _client(tmp_path, token="s3cret") as c:
        r = c.get("/healthz")
        assert r.status_code in (200, 503)   # degraded locally (no render_cli), never 401
        assert r.json()["status"] in ("ok", "degraded")
