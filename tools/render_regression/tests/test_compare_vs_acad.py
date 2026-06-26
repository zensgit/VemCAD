"""X3 compare CLI tests — synthetic PNG pairs, no renderer/AutoCAD needed."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
