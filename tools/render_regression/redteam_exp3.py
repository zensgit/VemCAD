"""Diagnostic through regress.run(): keep the wrong-color baseline probe current.

This intentionally exercises the full report row shape rather than acting as a
pass/fail gate for render fidelity.
"""
import sys, tempfile, json
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regress
from baseline import BaselineStore

TMP = Path(tempfile.mkdtemp(prefix="redteam3_"))

def frame(path, ink=(0,0,0), bg=(255,255,255)):
    im = Image.new("RGB",(1200,850),bg); d=ImageDraw.Draw(im)
    d.rectangle([100,100,1100,750], outline=ink, width=3)
    d.line([100,425,1100,425], fill=ink, width=2)
    im.save(path); return path

# Golden with one gated drawing.
golden = {"drawings":[{"name":"d1","category":"x","gate":True,"render":{}}]}

# Baseline image = black-ink frame. Candidate render = RED-ink frame (B4 color bug).
base_img = frame(TMP/"_baseline_d1.png", ink=(0,0,0))
store = BaselineStore(TMP/"baselines.json")
# Pretend the recorded baseline was a viewport-capture (advisory per spec/§7).
store.record("d1","self",base_img, approver="qa", note="viewport-capture source")
store.save()

def render_red(drawing, out):
    frame(out, ink=(220,0,0)); return True   # candidate has WRONG color

# Place baseline where run() expects it.
out_dir = TMP/"out"; out_dir.mkdir()
import shutil; shutil.copy(base_img, out_dir/"_baseline_d1.png")

rep = regress.run(golden, store, render_red, out_dir)
row = rep["rows"][0]
print("=== wrong-color candidate vs black baseline, through regress.run() ===")
print(json.dumps(row, indent=1))
print("gated_failures:", rep["gated_failures"], "(0 => the color bug PASSED CI)")
print("trust in row:", row.get("trust"), "(spec wanted advisory for viewport-capture baseline)")
print("comparable in row:", row.get("comparable"), "(orchestrator never sets False)")
print("\ntmp:", TMP)
