"""RED-TEAM experiments: construct image pairs that SHOULD be flagged as
regressions but score >= 0.97 (false pass), or that are fine but score low
(false fail). numpy+PIL only (matches harness constraint; no scipy)."""
import sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare, _ink_iou_tol, _ink_mask, _dilate  # noqa

TMP = Path(tempfile.mkdtemp(prefix="redteam_"))

def draw_frame(path, *, bg=(255,255,255), ink=(0,0,0), size=(1200,850),
               box=None, extra=None, line_w=3, title=True):
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    if box is None:
        box = [60, 60, size[0]-60, size[1]-60]
    d.rectangle(box, outline=ink, width=line_w)
    # inner divider + a title-block-ish region
    midx = (box[0]+box[2])//2
    d.line([box[0], (box[1]+box[3])//2, box[2], (box[1]+box[3])//2], fill=ink, width=2)
    if title:
        d.rectangle([box[2]-300, box[3]-120, box[2], box[3]], outline=ink, width=2)
        d.line([box[2]-300, box[3]-60, box[2], box[3]-60], fill=ink, width=1)
    if extra:
        for seg in extra:
            d.line(seg, fill=ink, width=2)
    im.save(path)
    return path

def report(name, r, expect):
    band = r.band; s = r.ink_iou
    verdict = "FALSE-PASS" if (expect=="fail" and band=="pass") else \
              ("FALSE-FAIL" if (expect=="pass" and band=="fallback") else "ok")
    print(f"[{verdict:11}] {name:38} iou={s:.4f} band={band:9} "
          f"ssim={r.ssim:.3f} dx={r.dx} dy={r.dy} comparable={r.comparable}")
    return verdict, s

results = []

# ─────────────────────────────────────────────────────────────────────────
# E1. WRONG SCALE: candidate drawing rendered 50% smaller (real scale bug).
# bbox-crop+resize normalizes scale away → should still score ~1.0.
a = draw_frame(TMP/"e1a.png")
b = draw_frame(TMP/"e1b.png", box=[300,300,900,650], line_w=2)  # much smaller, centered
results.append(("E1 wrong-scale (50% smaller)", report("E1 wrong-scale (50% smaller)", compare(a,b), "fail")))

# ─────────────────────────────────────────────────────────────────────────
# E2. GLOBAL TRANSLATION: candidate shifted 200px (off-origin / window bug).
# bbox-crop removes it entirely.
a = draw_frame(TMP/"e2a.png")
b = draw_frame(TMP/"e2b.png", box=[260, 200, 1060, 800])  # shifted+resized by bbox
results.append(("E2 wrong-position (shift)", report("E2 wrong-position (shift)", compare(a,b), "fail")))

# ─────────────────────────────────────────────────────────────────────────
# E3. WRONG COLOR (B4 regression): identical geometry, candidate ink is RED
# instead of black; bg white both. grayscale ink mask → invisible.
a = draw_frame(TMP/"e3a.png", ink=(0,0,0))
b = draw_frame(TMP/"e3b.png", ink=(220,0,0))  # red ink, same geometry
results.append(("E3 wrong-color (black->red)", report("E3 wrong-color (black->red)", compare(a,b), "fail")))

# E3b. Color INVERSION: white-on-black vs black-on-white. bg-relative mask.
a = draw_frame(TMP/"e3ba.png", bg=(255,255,255), ink=(0,0,0))
b = draw_frame(TMP/"e3bb.png", bg=(0,0,0), ink=(255,255,255))
results.append(("E3b color inversion", report("E3b color inversion", compare(a,b), "fail")))

# ─────────────────────────────────────────────────────────────────────────
# E4. ASPECT-RATIO DISTORTION: candidate frame is much wider (squashed).
# both resized to common canvas → distortion hidden.
a = draw_frame(TMP/"e4a.png", size=(1200,850), box=[100,100,500,750])  # tall narrow
b = draw_frame(TMP/"e4b.png", size=(1200,850), box=[100,100,1100,400]) # short wide
results.append(("E4 aspect distortion", report("E4 aspect distortion", compare(a,b), "fail")))

# ─────────────────────────────────────────────────────────────────────────
# E5. MISSING INK UNDER F1+DILATION: how much geometry can vanish at >=0.97?
# Start from full frame, progressively delete inner content. Find max deletion
# that still scores >= 0.97.
def grid(path, n_lines, size=(1200,850)):
    im = Image.new("RGB", size, (255,255,255)); d = ImageDraw.Draw(im)
    d.rectangle([60,60,size[0]-60,size[1]-60], outline=(0,0,0), width=3)
    ys = np.linspace(120, size[1]-120, n_lines).astype(int)
    for y in ys:
        d.line([80, int(y), size[0]-80, int(y)], fill=(0,0,0), width=2)
    im.save(path); return path
a = grid(TMP/"e5a.png", 40)
for missing in [1,2,4,6,8,10,15]:
    b = grid(TMP/"e5b.png", 40-missing)
    r = compare(a,b)
    tag = "FALSE-PASS" if r.band=="pass" else "ok"
    print(f"[{tag:11}] E5 missing {missing:2}/40 inner lines           iou={r.ink_iou:.4f} band={r.band}")

# ─────────────────────────────────────────────────────────────────────────
# E6. BOTH-BLANK: a render bug producing blank for BOTH baseline and candidate.
# (self-baseline recorded from a broken renderer, candidate also broken-blank.)
a = Image.new("RGB",(1200,850),(255,255,255)); a.save(TMP/"e6a.png")
b = Image.new("RGB",(1200,850),(255,255,255)); b.save(TMP/"e6b.png")
results.append(("E6 both-blank (broken both)", report("E6 both-blank (broken both)", compare(TMP/"e6a.png",TMP/"e6b.png"), "fail")))

# E6b. Near-blank: baseline is a faint stray dot, candidate also a faint stray
# dot elsewhere (both essentially empty drawings but not exactly 0 ink).
def dot(path, xy):
    im = Image.new("RGB",(1200,850),(255,255,255)); d=ImageDraw.Draw(im)
    d.ellipse([xy[0],xy[1],xy[0]+6,xy[1]+6], fill=(0,0,0)); im.save(path); return path
a = dot(TMP/"e6ba.png",(100,100)); b = dot(TMP/"e6bb.png",(1000,700))
results.append(("E6b near-blank diff dot", report("E6b near-blank diff dot", compare(a,b), "fail")))

# ─────────────────────────────────────────────────────────────────────────
# E7. TINY THICK INK dominates: a tiny but ink-dense blob, the rest sparse.
# Tests whether one dense region swamps the F1 so big sparse geometry loss hides.
def blob_plus_lines(path, n_lines):
    im = Image.new("RGB",(1200,850),(255,255,255)); d=ImageDraw.Draw(im)
    d.rectangle([900,650,1140,810], fill=(0,0,0))  # huge solid ink block
    ys = np.linspace(80, 600, n_lines).astype(int)
    for y in ys: d.line([80,int(y),840,int(y)], fill=(0,0,0), width=1)
    im.save(path); return path
a = blob_plus_lines(TMP/"e7a.png", 30)
b = blob_plus_lines(TMP/"e7b.png", 5)  # 25 of 30 line-drawings gone
results.append(("E7 dense-blob masks line loss", report("E7 dense-blob masks line loss", compare(a,b), "fail")))

# ─────────────────────────────────────────────────────────────────────────
print("\n--- SUMMARY ---")
fp = [n for n,(v,s) in results if v=="FALSE-PASS"]
print("FALSE-PASS cases:", fp if fp else "(see E5 sweep above)")
print("tmp:", TMP)
