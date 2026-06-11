import io
import json
import struct
import zlib

import pytest

from app.cache import sha256_bytes
from app.cli import main as cli_main
from app.packagestore import PackageStore, identity_key
from app.validator import validate_package


def make_png(width=1600, height=1000):
    """Minimal valid PNG (1 black pixel row replicated is unnecessary —
    header correctness is what the validator sniffs; we still emit a real
    IHDR so width/height are honest)."""
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"\x00" + b"\x00"  # one row, one grayscale pixel (we don't claim consistency)
    idat = zlib.compress(raw)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


TWIN = b"0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n10\n0\nENDSEC\n0\nEOF\n"


def base_manifest(files, level="standard", discipline="2d-drawing", metadata=None,
                  plugin_version="1.0.0", package_id="pkg-0001"):
    return {
        "schema": "vemcad.cad_package",
        "schema_version": "0.2",
        "package_id": package_id,
        "created_at": "2026-06-11T00:00:00Z",
        "level": level,
        "discipline": discipline,
        "producer": {
            "kind": "plugin",
            "host_app": "gstarcad",
            "host_version": "2026",
            "plugin_name": "pilot",
            "plugin_version": plugin_version,
        },
        "source": {
            "file_name": "图纸（测试）v1.dwg",
            "format": "dwg",
            "format_version": "AC1032",
            "sha256": "a" * 64,
            "size_bytes": 1,
        },
        "files": files,
        "metadata": metadata if metadata is not None else {"sheets": []},
        "notes": [],
    }


def entry(role, data, fname, params=None):
    return {
        "role": role,
        "file_name": fname,
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
        "content_type": "application/octet-stream",
        "produced_by": "plugin-api",
        "params": params or {},
    }


def good_ref_params():
    return {
        "view": "extents", "width_px": 1600, "height_px": 1000,
        "background": "#FFFFFF", "color_mapping": "display",
        "capture_method": "plot-raster", "captured_at_event": "checkin",
    }


def test_standard_package_validates_standard():
    png = make_png()
    files = [entry("twin-dxf", TWIN, "t.dxf"), entry("ref-render", png, "r.png", good_ref_params())]
    m = base_manifest(files)
    res = validate_package(m, {sha256_bytes(TWIN): TWIN, sha256_bytes(png): png})
    assert res.ok_manifest and res.validated_level == "standard"
    assert not res.quarantined


def test_corrupt_payload_quarantined_falls_to_minimal():
    png = make_png()
    files = [entry("twin-dxf", TWIN, "t.dxf"), entry("ref-render", png, "r.png", good_ref_params())]
    m = base_manifest(files)
    # Corrupt delivery: receiver keys payloads by the hash of the bytes it
    # actually got, so the manifest's ref-render sha is simply absent.
    corrupted = b"not the png"
    res = validate_package(
        m, {sha256_bytes(TWIN): TWIN, sha256_bytes(corrupted): corrupted}
    )
    assert res.validated_level == "minimal"
    assert any(q["reason"] == "payload-missing" for q in res.quarantined)


def test_size_lie_quarantined():
    files = [entry("twin-dxf", TWIN, "t.dxf")]
    files[0]["size_bytes"] = len(TWIN) + 5  # manifest lies about size
    m = base_manifest(files, level="minimal")
    res = validate_package(m, {sha256_bytes(TWIN): TWIN})
    assert any(q["reason"] == "size-mismatch" for q in res.quarantined)
    assert res.validated_level == "minimal"


def test_rich_never_granted():
    png = make_png()
    files = [entry("twin-dxf", TWIN, "t.dxf"), entry("ref-render", png, "r.png", good_ref_params())]
    m = base_manifest(files, level="rich")
    res = validate_package(m, {sha256_bytes(TWIN): TWIN, sha256_bytes(png): png})
    assert res.validated_level == "standard"
    assert any(w["code"] == "rich-not-granted-v0" for w in res.warnings)


def test_malformed_metadata_source_only():
    m = base_manifest([entry("twin-dxf", TWIN, "t.dxf")], metadata=["not", "a", "dict"])
    res = validate_package(m, {sha256_bytes(TWIN): TWIN})
    assert res.validated_level == "source-only"


def test_binary_dxf_twin_quarantined():
    bad = b"AutoCAD Binary DXF\r\n\x1a\x00" + b"\x00" * 32
    m = base_manifest([entry("twin-dxf", bad, "t.dxf")], level="minimal")
    res = validate_package(m, {sha256_bytes(bad): bad})
    assert res.validated_level == "minimal"  # metadata fine, twin quarantined
    assert any(q["reason"] == "binary-dxf-not-accepted" for q in res.quarantined)


def test_small_ref_render_not_conforming():
    png = make_png(800, 500)
    p = good_ref_params()
    p.update({"width_px": 800, "height_px": 500})
    files = [entry("twin-dxf", TWIN, "t.dxf"), entry("ref-render", png, "r.png", p)]
    m = base_manifest(files)
    res = validate_package(m, {sha256_bytes(TWIN): TWIN, sha256_bytes(png): png})
    assert res.validated_level == "minimal"
    assert any(w["code"] == "ref-render-nonconforming" for w in res.warnings)
    assert any(w["code"] == "level-downgraded" for w in res.warnings)


def test_unknown_major_rejected():
    m = base_manifest([entry("twin-dxf", TWIN, "t.dxf")])
    m["schema_version"] = "1.0"
    res = validate_package(m, {sha256_bytes(TWIN): TWIN})
    assert not res.ok_manifest and res.validated_level == "rejected"


def test_unknown_role_ignored_with_warning():
    files = [entry("twin-dxf", TWIN, "t.dxf"), entry("hologram", b"x", "h.bin")]
    m = base_manifest(files, level="minimal")
    res = validate_package(m, {sha256_bytes(TWIN): TWIN, sha256_bytes(b"x"): b"x"})
    assert res.ok_manifest
    assert any(w["code"] == "unknown-role" for w in res.warnings)


def test_3d_discipline_unsupported_note():
    m = base_manifest([], discipline="3d-assembly", level="minimal")
    res = validate_package(m, {})
    assert res.validated_level == "source-only"
    assert any(w["code"] == "3d-not-supported-v0" for w in res.warnings)


def test_incomplete_preview_resolved_true_without_xref_payload():
    meta = {
        "sheets": [],
        "external_refs": [
            {"kind": "dwg-xref", "name": "FRAME", "path": "x.dwg",
             "resolved": True, "sha256": "b" * 64}
        ],
    }
    m = base_manifest([entry("twin-dxf", TWIN, "t.dxf")], level="minimal", metadata=meta)
    res = validate_package(m, {sha256_bytes(TWIN): TWIN})
    assert res.incomplete_preview is True


def test_store_upsert_lower_version_does_not_move_pointer(tmp_path):
    store = PackageStore(tmp_path)
    m1 = base_manifest([], level="minimal", plugin_version="1.4.0", package_id="p-A")
    m2 = base_manifest([], level="minimal", plugin_version="1.2.0", package_id="p-B")
    assert identity_key(m1) == identity_key(m2)
    store.save(m1, {}, {"validated_level": "minimal"})
    info = store.save(m2, {}, {"validated_level": "minimal"})
    assert info["superseded_by_existing"] is True
    latest = json.loads(
        (tmp_path / identity_key(m1)[:2] / identity_key(m1) / "latest.json").read_text()
    )
    assert latest["package_id"] == "p-A"
    # both packages retained
    assert store.get_report("p-A") and store.get_report("p-B")


def test_cli_validate_and_expect_level(tmp_path):
    png = make_png()
    pdir = tmp_path / "pkg"
    pdir.mkdir()
    files = [entry("twin-dxf", TWIN, "t.dxf"), entry("ref-render", png, "r.png", good_ref_params())]
    (pdir / "cad_package.json").write_text(
        json.dumps(base_manifest(files), ensure_ascii=False), "utf-8"
    )
    (pdir / "twin.dxf").write_bytes(TWIN)
    (pdir / "ref.png").write_bytes(png)
    assert cli_main(["validate", str(pdir), "--quiet", "--expect-level", "standard"]) == 0
    assert cli_main(["validate", str(pdir), "--quiet", "--expect-level", "rich"]) == 3
    # violating package: drop the twin payload file
    (pdir / "twin.dxf").unlink()
    assert cli_main(["validate", str(pdir), "--quiet", "--expect-level", "standard"]) == 3
    assert cli_main(["validate", str(pdir), "--quiet", "--expect-level", "minimal"]) == 0


def test_package_id_traversal_rejected():
    m = base_manifest([], level="minimal", package_id="../../etc/evil")
    res = validate_package(m, {})
    assert not res.ok_manifest and res.validated_level == "rejected"


def test_missing_recommended_fields_warn_not_reject():
    # discipline/created_at/level missing must NOT reject (check-in always wins)
    m = base_manifest([entry("twin-dxf", TWIN, "t.dxf")], level="minimal")
    del m["discipline"]
    del m["created_at"]
    res = validate_package(m, {sha256_bytes(TWIN): TWIN})
    assert res.ok_manifest
    # no discipline → cannot validate as 2d → source-only, but NOT rejected
    assert res.validated_level == "source-only"
    assert any(w["code"] == "missing-field" for w in res.warnings)


def test_cardinality_extras_quarantined():
    a = b"0\nSECTION\n2\nENTITIES\n0\nEOF\nAAA"
    b = b"0\nSECTION\n2\nENTITIES\n0\nEOF\nBBB"
    files = [entry("twin-dxf", a, "a.dxf"), entry("twin-dxf", b, "b.dxf")]
    m = base_manifest(files, level="minimal")
    res = validate_package(m, {sha256_bytes(a): a, sha256_bytes(b): b})
    assert any(q["reason"] == "cardinality-exceeded" for q in res.quarantined)


def test_declaration_only_font_not_quarantined():
    files = [entry("twin-dxf", TWIN, "t.dxf")]
    files.append({
        "role": "font-shx", "file_name": "gbcbig.shx", "sha256": "c" * 64,
        "params": {"font_file_name": "gbcbig.shx", "bytes_omitted_reason": "license"},
    })
    m = base_manifest(files, level="minimal")
    res = validate_package(m, {sha256_bytes(TWIN): TWIN})  # font bytes NOT delivered
    assert not any(q["sha256"] == "c" * 64 for q in res.quarantined)


def test_a2b_does_not_render_quarantined_twin(tmp_path):
    from app.packagestore import PackageStore
    store = PackageStore(tmp_path)
    bad = b"AutoCAD Binary DXF\r\n\x1a\x00" + b"\x00" * 32  # quarantined: binary dxf
    m = base_manifest([entry("twin-dxf", bad, "t.dxf")], level="minimal", package_id="pkg-q")
    res = validate_package(m, {sha256_bytes(bad): bad})
    store.save(m, {sha256_bytes(bad): bad}, res.report())
    report = store.get_report("pkg-q")
    assert any(q["reason"] == "binary-dxf-not-accepted" for q in report["quarantined"])
