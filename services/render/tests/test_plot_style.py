from pathlib import Path

from PIL import Image

from app.renderer import apply_acad_plot_style


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
