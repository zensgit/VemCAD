"""X3 compare CLI tests — synthetic PNG pairs, no renderer/AutoCAD needed."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import compare as cmp  # noqa: E402
import compare_vs_acad as cva  # noqa: E402


def _draw(path, lines, size=(420, 300), colored_lines=()):
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, size[0] - 20, size[1] - 20], outline=(0, 0, 0), width=3)
    for (x0, y0, x1, y1) in lines:
        d.line([x0, y0, x1, y1], fill=(0, 0, 0), width=3)
    for (x0, y0, x1, y1, color) in colored_lines:
        d.line([x0, y0, x1, y1], fill=color, width=3)
    im.save(path)
    return str(path)


def test_identical_renders_score_excellent(tmp_path, capsys):
    a = _draw(tmp_path / "acad.png", [(40, 150, 380, 150)])
    o = _draw(tmp_path / "ours.png", [(40, 150, 380, 150)])
    out = tmp_path / "ov.png"
    rc = cva.main([a, o, "--out", str(out)])
    assert rc == 0
    txt = capsys.readouterr().out
    assert "ink IoU" in txt and "band" in txt and "verdict:" in txt
    assert "EXCELLENT" in txt          # identical → pass band
    assert out.is_file()               # difference overlay written


def test_missing_ink_not_excellent(tmp_path, capsys):
    # ours is missing interior lines AutoCAD has → clearly not a pass.
    a = _draw(tmp_path / "acad.png", [(40, 90, 380, 90), (40, 150, 380, 150), (40, 210, 380, 210)])
    o = _draw(tmp_path / "ours.png", [])   # frame only
    rc = cva.main([a, o])
    assert rc == 0
    txt = capsys.readouterr().out
    assert "verdict:" in txt
    assert "EXCELLENT" not in txt


def test_class_report_json_and_stdout(tmp_path, capsys):
    a = _draw(tmp_path / "acad.png", [(40, 150, 380, 150)],
              colored_lines=[(40, 90, 380, 90, (255, 0, 0))])
    o = _draw(tmp_path / "ours.png", [(40, 150, 380, 150)])
    report = tmp_path / "classes.json"
    rc = cva.main([a, o, "--class-report", str(report), "--print-classes"])
    assert rc == 0
    txt = capsys.readouterr().out
    assert "class scores" in txt
    assert "red" in txt

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["diagnostic_kind"] == "display-color-ink-classes"
    assert payload["semantic"] is False
    rows = {row["name"]: row for row in payload["classes"]}
    assert rows["dark"]["ink_iou"] >= 0.97
    assert rows["red"]["ref_present"] is True
    assert rows["red"]["cand_present"] is False
    assert rows["red"]["ink_iou"] == 0.0


def _semantic_inputs(tmp_path):
    mask = tmp_path / "semantic_mask.png"
    report = tmp_path / "render_report.json"

    im = Image.new("RGB", (420, 300), (0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, 400, 280], outline=(31, 119, 180), width=3)
    d.line([40, 150, 380, 150], fill=(31, 119, 180), width=3)
    d.line([70, 60, 150, 92], fill=(255, 127, 14), width=3)
    im.save(mask)

    report.write_text(json.dumps({
        "semantic_classes": {
            "schema": "vemcad.render_semantic_classes",
            "schema_version": "0.1",
            "mask_kind": "candidate-renderer-semantic-class-buffer",
            "reference_semantics": "unknown",
            "palette": [
                {"name": "geometry", "rgb": "#1F77B4"},
                {"name": "text", "rgb": "#FF7F0E"},
            ],
        }
    }), encoding="utf-8")
    return mask, report


def _framed(path, size, box):
    """A single black outline rectangle on white — image size + box are explicit
    so page-fill (ink-bbox ÷ image) and aspect are controllable per render."""
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle(box, outline=(0, 0, 0), width=3)
    im.save(path)
    return str(path)


# ── X3 framing / capture view-space mismatch detection ──

def test_framing_divergence_flags_paperspace_vs_extents(tmp_path):
    # SAME outline aspect (1.333), very different page-fill: the AutoCAD plot is
    # inset by page margins (fill ~0.45) while render_cli fills the frame to
    # extents (fill ~0.95). This is the exact G11 mechanism — the page-fill axis
    # trips while aspect_delta stays UNDER ASPECT_TOL, so the existing aspect
    # guard is silent.
    ref = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])   # 360x270
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])    # 720x540
    fr = cmp.framing_divergence(ref, ours)
    assert fr["framing_mismatch"] is True
    assert fr["fill_divergence_x"] > cmp.FRAMING_TOL          # page-fill axis trips
    assert fr["aspect_delta"] < cmp.ASPECT_TOL               # aspect guard would NOT have fired


def test_framing_divergence_flags_aspect_only(tmp_path):
    # The OR's second operand: page-fill matches (~0.5 both axes) but the ink
    # bbox aspect differs beyond ASPECT_TOL → still a framing mismatch.
    ref = _framed(tmp_path / "acad.png", (800, 600), [200, 150, 600, 450])   # 400x300, asp 1.333
    ours = _framed(tmp_path / "ours.png", (870, 600), [217, 150, 652, 450])  # 435x300, asp 1.45
    fr = cmp.framing_divergence(ref, ours)
    assert fr["framing_mismatch"] is True
    assert fr["aspect_delta"] > cmp.ASPECT_TOL
    assert fr["fill_divergence_x"] <= cmp.FRAMING_TOL
    assert fr["fill_divergence_y"] <= cmp.FRAMING_TOL


def test_framing_divergence_clean_pair_not_flagged(tmp_path):
    # Same view-space: identical image size + identical outer extents → NOT a
    # framing mismatch (no false flag). The genuine content-differs/same-frame
    # no-false-flag case is covered through the CLI by
    # test_missing_ink_not_excellent (acad has interior lines, ours frame-only,
    # same outer bbox → normal verdict, not the framing one).
    ref = _framed(tmp_path / "acad.png", (760, 570), [20, 15, 740, 555])
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])
    fr = cmp.framing_divergence(ref, ours)
    assert fr["framing_mismatch"] is False
    assert fr["comparable"] is True


def test_framing_divergence_blank_side_not_flagged(tmp_path):
    # A blank render is a different failure (compare()'s blank path) — framing
    # must not hijack it.
    ref = _framed(tmp_path / "acad.png", (760, 570), [20, 15, 740, 555])
    blank = tmp_path / "blank.png"
    Image.new("RGB", (760, 570), (255, 255, 255)).save(blank)
    fr = cmp.framing_divergence(ref, str(blank))
    assert fr["framing_mismatch"] is False
    assert fr["comparable"] is False
    assert fr["reason"] == "blank-side"


def test_cli_emits_not_comparable_framing_verdict(tmp_path, capsys):
    # POSITIVE: the CLI replaces the ink-IoU verdict with the framing verdict so
    # a view-space mismatch is not mis-reported as renderer infidelity. No --out
    # (an overlay across view-spaces is meaningless).
    ref = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])
    rc = cva.main([ref, ours])
    assert rc == 0
    txt = capsys.readouterr().out
    assert "framing/capture mismatch" in txt
    assert "page-fill" in txt and "framing div" in txt
    assert "DIVERGENT" not in txt          # the misleading infidelity verdict is suppressed


def test_cli_writes_viewspace_contract_report_for_framing_mismatch(tmp_path, capsys):
    ref = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])
    report = tmp_path / "viewspace.json"

    rc = cva.main([ref, ours, "--viewspace-report", str(report)])

    assert rc == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["schema"] == "vemcad.x3_viewspace_contract/v1"
    assert payload["status"] == "mismatch"
    assert payload["reason"] == "page-fill/aspect divergence exceeds tolerance"
    assert "explicit matching --window" in payload["recommended_action"]
    assert payload["framing"]["framing_mismatch"] is True
    assert payload["thresholds"]["framing_tol"] == cmp.FRAMING_TOL
    assert payload["x3_summary"]["comparable"] is True  # X3 alone still has a numeric score
    assert "framing/capture mismatch" in capsys.readouterr().out


def test_cli_require_viewspace_match_fails_on_mismatch(tmp_path):
    ref = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])

    rc = cva.main([ref, ours, "--require-viewspace-match"])

    assert rc == 2


def test_cli_clean_pair_keeps_normal_verdict(tmp_path, capsys):
    # NEGATIVE/guard: a same-fit same-aspect self-compare is unaffected — the
    # normal EXCELLENT verdict stands, proving no false-flag (no gate/golden
    # impact for genuinely comparable renders).
    ref = _framed(tmp_path / "acad.png", (760, 570), [20, 15, 740, 555])
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])
    rc = cva.main([ref, ours])
    assert rc == 0
    txt = capsys.readouterr().out
    assert "framing/capture mismatch" not in txt
    assert "EXCELLENT" in txt


def test_cli_viewspace_contract_report_for_clean_pair(tmp_path):
    ref = _framed(tmp_path / "acad.png", (760, 570), [20, 15, 740, 555])
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])
    report = tmp_path / "viewspace.json"

    rc = cva.main([ref, ours, "--viewspace-report", str(report), "--require-viewspace-match"])

    assert rc == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "match"
    assert payload["recommended_action"] == "score-render-fidelity"
    assert payload["framing"]["framing_mismatch"] is False


def test_semantic_class_report_json_and_stdout(tmp_path, capsys):
    a = _draw(tmp_path / "acad.png", [(40, 150, 380, 150)],
              colored_lines=[(70, 60, 150, 92, (0, 0, 0))])
    o = _draw(tmp_path / "ours.png", [(40, 150, 380, 150)],
              colored_lines=[(70, 60, 150, 92, (0, 0, 0))])
    mask, render_report = _semantic_inputs(tmp_path)
    out_report = tmp_path / "semantic_classes.json"

    rc = cva.main([
        a, o,
        "--semantic-mask", str(mask),
        "--semantic-render-report", str(render_report),
        "--semantic-class-report", str(out_report),
        "--print-semantic-classes",
    ])
    assert rc == 0
    txt = capsys.readouterr().out
    assert "semantic classes" in txt
    assert "geometry" in txt
    assert "AutoCAD semantics unknown" in txt

    payload = json.loads(out_report.read_text(encoding="utf-8"))
    assert payload["diagnostic_kind"] == "candidate-semantic-class-ink"
    assert payload["semantic"] is True
    assert payload["reference_semantics"] == "unknown"
    rows = {row["name"]: row for row in payload["classes"]}
    assert rows["geometry"]["candidate_precision"] >= 0.97
    assert rows["text"]["candidate_precision"] >= 0.97
