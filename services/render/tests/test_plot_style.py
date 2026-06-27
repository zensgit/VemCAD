from pathlib import Path

from PIL import Image

from app.renderer import (
    ACAD_PLOT_TARGET_FILL_X,
    ACAD_PLOT_TARGET_FILL_Y,
    apply_acad_display_style,
    apply_acad_plot_style,
    apply_acad_plot_view_frame,
)


def test_acad_plot_style_neutralizes_colours_without_changing_size(tmp_path: Path):
    p = tmp_path / "in.png"
    img = Image.new("RGB", (4, 1), "white")
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((1, 0), (0, 255, 0))
    img.putpixel((2, 0), (0, 255, 255))
    img.save(p)

    apply_acad_plot_style(p)

    out = Image.open(p).convert("RGB")
    assert out.size == (4, 1)
    for x in (0, 1, 2):
        r, g, b = out.getpixel((x, 0))
        assert r == g == b
        assert 0 <= r < 255
    assert out.getpixel((3, 0)) == (255, 255, 255)


def test_acad_display_style_darkens_grey_linework_preserving_colours(tmp_path: Path):
    p = tmp_path / "in.png"
    img = Image.new("RGB", (6, 1), "white")
    img.putpixel((0, 0), (160, 160, 160))  # neutral grey linework -> black
    img.putpixel((1, 0), (230, 230, 230))  # near background -> unchanged
    img.putpixel((2, 0), (255, 255, 0))    # saturated yellow annotation -> unchanged
    img.putpixel((3, 0), (0, 255, 0))      # saturated green annotation -> unchanged
    img.putpixel((4, 0), (10, 10, 10))     # already-dark ink -> unchanged
    img.save(p)

    apply_acad_display_style(p)

    out = Image.open(p).convert("RGB")
    assert out.size == (6, 1)
    assert out.getpixel((0, 0)) == (0, 0, 0)
    assert out.getpixel((1, 0)) == (230, 230, 230)
    assert out.getpixel((2, 0)) == (255, 255, 0)
    assert out.getpixel((3, 0)) == (0, 255, 0)
    assert out.getpixel((4, 0)) == (10, 10, 10)
    assert out.getpixel((5, 0)) == (255, 255, 255)


def _ink_bbox(img: Image.Image):
    pix = img.convert("RGB")
    bg = pix.getpixel((0, 0))
    xs, ys = [], []
    for y in range(pix.height):
        for x in range(pix.width):
            if pix.getpixel((x, y)) != bg:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def test_acad_plot_view_frame_reframes_square_ink_to_plot_height(tmp_path: Path):
    p = tmp_path / "square.png"
    img = Image.new("RGB", (200, 100), "white")
    for x in range(80, 120):
        for y in range(30, 70):
            img.putpixel((x, y), (0, 0, 0))
    img.save(p)

    report = apply_acad_plot_view_frame(p)

    out = Image.open(p).convert("RGB")
    bbox = _ink_bbox(out)
    assert report["mode"] == "framed"
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert round((y1 - y0) / out.height, 2) == round(ACAD_PLOT_TARGET_FILL_Y, 2)
    assert abs(((x1 - x0) / (y1 - y0)) - 1.0) < 0.03


def test_acad_plot_view_frame_reframes_wide_ink_to_plot_width(tmp_path: Path):
    p = tmp_path / "wide.png"
    img = Image.new("RGB", (200, 100), "white")
    for x in range(40, 160):
        for y in range(45, 55):
            img.putpixel((x, y), (0, 0, 0))
    img.save(p)

    report = apply_acad_plot_view_frame(p)

    out = Image.open(p).convert("RGB")
    bbox = _ink_bbox(out)
    assert report["mode"] == "framed"
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert round((x1 - x0) / out.width, 2) == round(ACAD_PLOT_TARGET_FILL_X, 2)


def test_acad_plot_view_frame_falls_back_on_blank(tmp_path: Path):
    p = tmp_path / "blank.png"
    Image.new("RGB", (200, 100), "white").save(p)

    report = apply_acad_plot_view_frame(p)

    assert report == {"mode": "fallback", "reason": "blank"}
