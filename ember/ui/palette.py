"""One palette for every surface: the overview component, the Streamlit pages and the chart theme.

Dark is the default: a charcoal canvas, blue-grey data surfaces, frosted glass for floating chrome.
Ember orange marks the scenario, the reticle and primary actions; gold marks NASA reference
atmospheres. Light is the white-sky print a viewer gets from Streamlit's light base.

``.streamlit/config.toml`` cannot import Python, so it repeats the dark values; tests/test_palette.py
keeps the two in step and checks text contrast on every surface.
"""

from __future__ import annotations

DARK: dict[str, str] = {
    # surfaces
    "canvas": "#090c13",  # page and hero base
    "surface": "#111a29",  # charts and data
    "surface2": "#162133",  # raised data (fields, table headers)
    "wash": "#0d131e",  # sidebar base and quiet callouts
    "glass": "rgba(28, 38, 56, 0.75)",
    "glass_solid": "#1a2333",  # glass without blur
    "glass_edge": "rgba(196, 210, 232, 0.14)",
    "hair": "rgba(168, 180, 199, 0.14)",
    "line": "#263247",
    # text
    "ink": "#f2f4f8",
    "ink2": "#a8b4c7",
    "muted": "#8592a8",
    # meaning
    "accent": "#ff8a4c",  # flame, active reticle, primary actions
    "accent_ink": "#1a1208",  # text on accent
    "accent_wash": "#3a2619",
    "gold": "#e3c46e",  # NASA reference atmospheres
    "warn": "#f2c45a",  # partial-gravity and envelope callouts
    "warn_wash": "#2a2414",
}

LIGHT: dict[str, str] = {
    "canvas": "#f4f6f9",
    "surface": "#ffffff",
    "surface2": "#eef1f6",
    "wash": "#eaeef4",
    "glass": "rgba(250, 251, 253, 0.78)",
    "glass_solid": "#f7f9fc",
    "glass_edge": "rgba(20, 32, 54, 0.12)",
    "hair": "rgba(20, 32, 54, 0.10)",
    "line": "#cdd5e1",
    "ink": "#141c2b",
    "ink2": "#3d4a60",
    "muted": "#56637a",
    "accent": "#c4501c",
    "accent_ink": "#ffffff",
    "accent_wash": "#fbe3d5",
    "gold": "#7d5f14",
    "warn": "#7a5600",
    "warn_wash": "#fdf3d6",
}

# Shape and rhythm, shared by the overview CSS and the Streamlit layer.
RADII = {"xl": "22px", "lg": "16px", "md": "11px", "pill": "999px"}


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def luminance(h: str) -> float:
    def ch(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = hex_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
