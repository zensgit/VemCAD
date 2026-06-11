import json

from fastapi.testclient import TestClient

from app.cache import sha256_bytes
from app.main import create_app
from conftest import needs_render_cli
from test_validator import base_manifest, entry, good_ref_params, make_png


def post_package(client, manifest, payload_bytes_list):
    files = [("manifest", ("cad_package.json", json.dumps(manifest, ensure_ascii=False), "application/json"))]
    for i, data in enumerate(payload_bytes_list):
        files.append(("payload", ("p%d.bin" % i, data, "application/octet-stream")))
    return client.post("/package", files=files)


@needs_render_cli
def test_package_roundtrip_and_a2b_render(settings, fixture_dxf):
    png = make_png()
    manifest = base_manifest(
        [entry("twin-dxf", fixture_dxf, "twin.dxf"),
         entry("ref-render", png, "ref.png", good_ref_params())],
        package_id="pkg-rt-1",
    )
    with TestClient(create_app(settings)) as c:
        r = post_package(c, manifest, [fixture_dxf, png])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert body["validated_level"] == "standard"

        rep = c.get("/package/pkg-rt-1/report")
        assert rep.status_code == 200
        assert rep.json()["validated_level"] == "standard"

        # A2b: render the stored twin by reference.
        rr = c.post("/render?package_id=pkg-rt-1&role=twin-dxf&format=png&width=400&height=250")
        assert rr.status_code == 200, rr.text
        assert rr.headers["content-type"].startswith("image/png")
        assert len(rr.content) > 1000
        assert rr.headers["X-Render-Key"]

        # role restriction
        bad = c.post("/render?package_id=pkg-rt-1&role=ref-render")
        assert bad.status_code == 404
        assert bad.json()["error_code"] == "ROLE_NOT_RENDERABLE"

        # unknown package
        nf = c.post("/render?package_id=nope&role=twin-dxf")
        assert nf.status_code == 404
        assert nf.json()["error_code"] == "PACKAGE_NOT_FOUND"


def test_package_rejected_manifest(settings):
    with TestClient(create_app(settings)) as c:
        m = base_manifest([], level="minimal")
        m["schema_version"] = "9.9"
        r = post_package(c, m, [])
        assert r.status_code == 422
        assert r.json()["error_code"] == "PACKAGE_REJECTED"


def test_package_quality_never_blocks(settings):
    """A package full of problems still lands (validated at the floor)."""
    with TestClient(create_app(settings)) as c:
        m = base_manifest([entry("twin-dxf", b"junk-without-magic", "t.dxf")],
                          level="rich", metadata=["bad"], package_id="pkg-floor")
        r = post_package(c, m, [])  # payload not even delivered
        assert r.status_code == 200
        body = r.json()
        assert body["validated_level"] == "source-only"
        assert c.get("/package/pkg-floor/report").status_code == 200
