from pathlib import Path

from PIL import Image

from app.renderer import apply_acad_display_style, apply_acad_plot_style


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
