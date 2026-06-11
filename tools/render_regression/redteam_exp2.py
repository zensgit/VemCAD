"""Follow-ups: (1) why E5 (dense thin-line art) false-FAILS even when identical;
(2) does scale-normalization actually hide scale bugs when the *shape* is the
same; (3) the realistic font-substitution case the spec calls out."""
import sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare, _ink_iou_tol, _ink_mask, _crop_resize, _best_shift  # noqa

TMP = Path(tempfile.mkdtemp(prefix="redteam2_"))

# (1) IDENTICAL dense thin-line art compared to ITSELF (the self-baseline case).
def grid(path, n_lines, size=(1200,850), w=1):
    im = Image.new("RGB", size, (255,255,255)); d = ImageDraw.Draw(im)
    d.rectangle([60,60,size[0]-60,size[1]-60], outline=(0,0,0), width=2)
    ys = np.linspace(120, size[1]-120, n_lines).astype(int)
    for y in ys: d.line([80,int(y),size[0]-80,int(y)], fill=(0,0,0), width=w)
    im.save(path); return path

print("=== (1) IDENTICAL dense line art vs itself (self-baseline, should be ~1.0) ===")
for n,w in [(40,1),(40,2),(40,3),(20,1),(10,2),(60,1)]:
    a = grid(TMP/f"g_{n}_{w}.png", n, w=w)
    r = compare(a, a)   # literally identical bytes
    flag = "FALSE-FAIL" if r.band!="pass" else "ok"
    print(f"[{flag:11}] grid n={n:2} w={w}px  iou={r.geometry_ink_iou:.4f} band={r.band}")

print("\n=== (2) scale bug where SHAPE identical, only overall size differs ===")
# A clean frame at full size vs the SAME frame scaled down but same aspect.
def frame(path, scale=1.0, size=(1200,850)):
    im = Image.new("RGB", size, (255,255,255)); d = ImageDraw.Draw(im)
    w,h = size
    cx,cy = w//2,h//2
    bw,bh = int(500*scale), int(350*scale)
    d.rectangle([cx-bw,cy-bh,cx+bw,cy+bh], outline=(0,0,0), width=3)
    d.line([cx-bw,cy,cx+bw,cy], fill=(0,0,0), width=2)
    d.line([cx,cy-bh,cx,cy+bh], fill=(0,0,0), width=2)
    im.save(path); return path
a = frame(TMP/"s_full.png", 1.0)
for sc in [0.9,0.75,0.5,0.25]:
    b = frame(TMP/f"s_{sc}.png", sc)
    r = compare(a,b)
    flag = "FALSE-PASS" if r.band=="pass" else "caught"
    print(f"[{flag:11}] same-shape scale={sc}  iou={r.geometry_ink_iou:.4f} band={r.band}")

print("\n=== (3) font substitution: same geometry, different glyph shapes in title ===")
# Spec: geometry score gates, text region recorded separately. Code mixes them.
# Heavy text drawing vs same frame with text replaced by different-shape glyphs.
def titled(path, glyph='A', size=(1200,850), ncols=20):
    im = Image.new("RGB", size, (255,255,255)); d = ImageDraw.Draw(im)
    d.rectangle([60,60,size[0]-60,size[1]-60], outline=(0,0,0), width=3)
    # simulate a text-dense BOM region: many small glyph rectangles vs filled
    for r_ in range(15):
        for c_ in range(ncols):
            x,y = 100+c_*50, 120+r_*40
            if glyph=='A':
                d.rectangle([x,y,x+30,y+25], outline=(0,0,0), width=1)
            else:
                d.rectangle([x,y,x+30,y+25], fill=(0,0,0))  # substituted glyph: solid
    im.save(path); return path
a = titled(TMP/"t_a.png",'A')
b = titled(TMP/"t_b.png",'B')  # same layout, very different glyph ink
r = compare(a,b)
print(f"font-sub (outline vs solid glyph): iou={r.geometry_ink_iou:.4f} band={r.band} ssim={r.ssim:.3f}")
print("  -> if this FAILS, font substitution would trip the gate the spec says")
print("     should be geometry-only. Code has NO text/geometry separation.")

print("\n=== (4) the REAL scale-hiding case: drawing window/extents wrong, ===")
print("    same content but baseline frames a sub-region candidate frames whole ===")
# baseline: window crops to the sheet rect (correct). candidate: extents blown
# by a stray entity so the sheet is tiny in a corner + huge whitespace, BUT the
# stray entity itself is sub-tol and gets cropped... actually the bbox includes
# the stray. Model it: candidate has sheet + 1 far dot -> bbox huge -> sheet shrinks.
def sheet(path, stray=False, size=(1200,850)):
    im = Image.new("RGB", size, (255,255,255)); d = ImageDraw.Draw(im)
    d.rectangle([100,100,500,400], outline=(0,0,0), width=3)
    d.line([100,250,500,250], fill=(0,0,0), width=2)
    if stray:
        d.point([size[0]-5, size[1]-5], fill=(0,0,0))  # 1px stray at far corner
        d.point([size[0]-4, size[1]-5], fill=(0,0,0))
    im.save(path); return path
a = sheet(TMP/"sh_a.png", stray=False)
b = sheet(TMP/"sh_b.png", stray=True)   # stray blows the bbox -> sheet shrinks on crop
r = compare(a,b)
print(f"stray-extent (bbox blowup): iou={r.geometry_ink_iou:.4f} band={r.band} dx={r.dx} dy={r.dy}")

print("\ntmp:", TMP)
