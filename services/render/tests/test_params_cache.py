import pytest

from app.cache import cache_key, font_fingerprint
from app.renderer import ParamError, RenderParams


def test_params_ok():
    p = RenderParams.parse("png", "2400", 1697, "dark", "extents")
    assert p.width == 2400 and p.fmt == "png"
    assert p.as_dict()["bg"] == "dark"
    assert "style" not in p.as_dict()  # source style keeps legacy cache keys stable


def test_non_source_styles_enter_params_and_cache_key():
    source = RenderParams.parse("png", 100, 50, "white", "sheet")
    plot = RenderParams.parse("png", 100, 50, "white", "sheet", "acad-plot")
    display = RenderParams.parse("png", 100, 50, "white", "sheet", "acad-display")
    plot_view = RenderParams.parse("png", 100, 50, "white", "acad-plot", "acad-display")
    assert plot.style == "acad-plot"
    assert plot.as_dict()["style"] == "acad-plot"
    assert display.style == "acad-display"
    assert display.as_dict()["style"] == "acad-display"
    assert plot_view.view == "acad-plot"
    assert plot_view.as_dict()["view"] == "acad-plot"
    assert cache_key("c" * 64, source.as_dict(), "cli", "fp") != cache_key(
        "c" * 64, plot.as_dict(), "cli", "fp"
    )
    assert cache_key("c" * 64, source.as_dict(), "cli", "fp") != cache_key(
        "c" * 64, display.as_dict(), "cli", "fp"
    )
    assert cache_key("c" * 64, plot.as_dict(), "cli", "fp") != cache_key(
        "c" * 64, display.as_dict(), "cli", "fp"
    )
    assert cache_key("c" * 64, source.as_dict(), "cli", "fp") != cache_key(
        "c" * 64, plot_view.as_dict(), "cli", "fp"
    )


@pytest.mark.parametrize(
    "kw",
    [
        dict(fmt="pdf", width=100, height=100, bg="dark", view="extents"),
        dict(fmt="png", width=8, height=100, bg="dark", view="extents"),
        dict(fmt="png", width=9000, height=100, bg="dark", view="extents"),
        dict(fmt="png", width=8192, height=8192, bg="dark", view="extents"),  # > 64 MP
        dict(fmt="png", width=100, height=100, bg="grey", view="extents"),
        dict(fmt="png", width=100, height=100, bg="#12345", view="extents"),
        dict(fmt="png", width=100, height=100, bg="dark", view="layout:A"),
        dict(fmt="png", width=100, height=100, bg="dark", view="extents", style="screen"),
        dict(fmt="svg", width=100, height=100, bg="white", view="acad-plot"),
        dict(fmt="svg", width=100, height=100, bg="white", view="extents", style="acad-plot"),
        dict(fmt="svg", width=100, height=100, bg="white", view="extents", style="acad-display"),
    ],
)
def test_params_rejected(kw):
    with pytest.raises(ParamError):
        RenderParams.parse(
            kw["fmt"], kw["width"], kw["height"], kw["bg"], kw["view"],
            kw.get("style", "source"),
        )


def test_cache_key_is_stable_and_sensitive():
    params = {"format": "png", "width": 100, "height": 50, "bg": "dark", "view": "extents"}
    k1 = cache_key("c" * 64, params, "cli" + "0" * 61, "no-fonts")
    k2 = cache_key("c" * 64, dict(reversed(list(params.items()))), "cli" + "0" * 61, "no-fonts")
    assert k1 == k2  # canonical ordering
    assert cache_key("d" * 64, params, "cli" + "0" * 61, "no-fonts") != k1
    assert cache_key("c" * 64, params, "x" + "0" * 63, "no-fonts") != k1  # renderer version
    assert cache_key("c" * 64, params, "cli" + "0" * 61, "fp") != k1  # font set


def test_font_fingerprint_empty(tmp_path):
    assert font_fingerprint(None) == "no-fonts"
    assert font_fingerprint(tmp_path) == "no-fonts"
    (tmp_path / "a.ttf").write_bytes(b"x")
    fp1 = font_fingerprint(tmp_path)
    (tmp_path / "b.ttf").write_bytes(b"y")
    fp2 = font_fingerprint(tmp_path)
    assert fp1 != "no-fonts" and fp1 != fp2
