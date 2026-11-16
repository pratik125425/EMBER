"""The palette is declared once in Python and repeated in config.toml and the overview CSS; these
checks keep the copies in step and hold every text colour to WCAG contrast on its surfaces."""

import re
import tomllib
from pathlib import Path

import pytest

from ember.ui.palette import DARK, LIGHT, contrast
from ember.ui.theme import DARK_MAP, SURFACE

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_config_repeats_the_dark_palette():
    theme = tomllib.loads((ROOT / ".streamlit/config.toml").read_text())["theme"]
    assert theme["base"] == "dark"
    assert theme["backgroundColor"].lower() == DARK["canvas"]
    assert theme["secondaryBackgroundColor"].lower() == DARK["surface2"]
    assert theme["textColor"].lower() == DARK["ink"]
    assert theme["primaryColor"].lower() == DARK["accent"]
    assert theme["borderColor"].lower() == DARK["line"]
    assert theme["sidebar"]["backgroundColor"].lower() == DARK["wash"]


def test_overview_css_defaults_repeat_the_dark_palette():
    css = (ROOT / "ember/ui/atlas_frontend/style.css").read_text()
    root = re.search(r":root \{(.*?)\}", css, re.S).group(1)
    decl = dict(re.findall(r"--([\w-]+):\s*([^;]+);", root))
    for css_name, key in {
        "deep": "canvas",
        "plate": "surface",
        "surface": "surface",
        "surface-2": "surface2",
        "ink": "ink",
        "ink2": "ink2",
        "muted": "muted",
        "line": "line",
        "accent": "accent",
        "gold": "gold",
        "glass": "glass",
    }.items():
        assert decl[css_name].strip().lower() == DARK[key], css_name


def test_charts_use_the_palette_surface():
    assert DARK_MAP[SURFACE] == DARK["surface"]


@pytest.mark.parametrize("pal", [DARK, LIGHT], ids=["dark", "light"])
def test_text_contrast_on_every_surface(pal):
    for bg in ("canvas", "surface", "surface2", "wash", "glass_solid"):
        assert contrast(pal["ink"], pal[bg]) >= 7, bg
        assert contrast(pal["ink2"], pal[bg]) >= 4.5, bg
        assert contrast(pal["muted"], pal[bg]) >= 4.5, bg
    # orange buttons carry their own text colour
    assert contrast(pal["accent_ink"], pal["accent"]) >= 4.5
    # gold labels and the partial-gravity callout
    assert contrast(pal["gold"], pal["surface"]) >= 4.5
    assert contrast(pal["ink"], pal["warn_wash"]) >= 7
    assert contrast(pal["ink"], pal["accent_wash"]) >= 7
    # focus ring and the active reticle stand out from the canvas and the chart
    assert contrast(pal["accent"], pal["canvas"]) >= 3
    assert contrast(pal["accent"], pal["surface"]) >= 3
