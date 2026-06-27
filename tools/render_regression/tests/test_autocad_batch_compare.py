"""Batch AutoCAD comparison helper tests — synthetic PNG pairs, no renderer."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import autocad_batch_compare as batch  # noqa: E402


def _framed(path: Path, size: tuple[int, int], box: list[int]) -> str:
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle(box, outline=(0, 0, 0), width=3)
    im.save(path)
    return str(path)


def test_batch_summary_records_framing_mismatch(tmp_path):
    # Same outline aspect, different page-fill: exactly the X3 capture mismatch
    # class that compare_vs_acad flags before interpreting a low IoU as renderer
    # divergence. The batch helper must carry that attribution too.
    acad = _framed(tmp_path / "acad.png", (800, 600), [220, 165, 580, 435])
    ours = _framed(tmp_path / "ours.png", (760, 570), [20, 15, 740, 555])
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "Gx", "acad": acad, "ours": ours}]), encoding="utf-8")
    out = tmp_path / "out"

    assert batch.main(["--cases", str(cases), "--out-dir", str(out)]) == 0

    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]
    assert row["framing_mismatch"] is True
    assert row["framing"]["fill_divergence_x"] > 0.05
    assert "framing_mismatch" in (out / "summary.tsv").read_text(encoding="utf-8").splitlines()[0]
