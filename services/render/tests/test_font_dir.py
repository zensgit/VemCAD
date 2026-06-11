"""A5: the service forwards --font-dir to render_cli (B1) and embeds the
render_cli report. Requires a render_cli that supports --font-dir/--report
(post-B1); auto-skips otherwise."""
import json

from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from conftest import RENDER_CLI, needs_render_cli

CJK_DXF = (
    "0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1027\n"
    "9\n$EXTMIN\n10\n0\n20\n0\n30\n0\n9\n$EXTMAX\n10\n200\n20\n100\n30\n0\n"
    "0\nENDSEC\n0\nSECTION\n2\nENTITIES\n"
    "0\nTEXT\n8\n0\n62\n2\n10\n10\n20\n50\n30\n0\n40\n12\n1\n渲染字体测试ABC\n"
    "0\nLINE\n8\n0\n10\n0\n20\n0\n11\n200\n21\n100\n0\nENDSEC\n0\nEOF\n"
).encode("utf-8")


def _cli_supports_font_dir():
    import subprocess
    if RENDER_CLI is None:
        return False
    out = subprocess.run([str(RENDER_CLI), "--help"], capture_output=True, text=True)
    return "--font-dir" in (out.stdout + out.stderr)


@needs_render_cli
def test_font_dir_forwarded_and_report_embedded(settings, tmp_path):
    import pytest
    if not _cli_supports_font_dir():
        pytest.skip("render_cli predates B1 (--font-dir)")

    # A font dir with a real font file → non-empty fingerprint + loaded families.
    fontdir = tmp_path / "fonts"
    fontdir.mkdir()
    import shutil, os
    src = "/System/Library/Fonts/Supplemental/Songti.ttc"
    if not os.path.exists(src):
        pytest.skip("no system CJK font to bundle")
    shutil.copy(src, fontdir / "Songti.ttc")

    cfg = load_settings(
        render_cli=str(settings.render_cli), cache_dir=str(tmp_path / "c"),
        font_dir=str(fontdir), workers=2,
    )
    with TestClient(create_app(cfg)) as c:
        h = c.get("/healthz").json()
        assert h["fonts"]["count"] == 1
        assert h["fonts"]["fingerprint"] != "no-fonts"

        r = c.post("/render?format=png&width=400&height=200",
                   files={"file": ("cjk.dxf", CJK_DXF, "application/octet-stream")})
        assert r.status_code == 200, r.text
        key = r.headers["X-Render-Key"]
        # The cache sidecar carries the embedded render_cli report with font records.
        report = cfg.cache_dir.joinpath(key[:2], key + ".report.json")
        # find report via store layout
        import glob
        matches = glob.glob(str(cfg.cache_dir / "**" / (key + ".report.json")), recursive=True)
        assert matches, "render report sidecar missing"
        rep = json.loads(open(matches[0]).read())
        assert rep["font_dir"] == str(fontdir)
        cli = rep["render_cli_report"]
        assert cli and cli["schema"] == "vemcad.render_report"
        assert "Songti SC" in cli["fonts"]["loaded_families"]
        assert cli["counts"]["text_entities"] == 1
