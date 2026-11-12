"""One Plotly template for every chart, in the atlas-plate world: recessive graticule and axes, ink
tokens for text, series colours only on marks, ember reserved for the scenario.

Chart code is written once against the LIGHT ("white-sky print") tokens. ``show_chart`` renders
with the template and, on the default navy plate (Streamlit's dark base), swaps every light token
for its plate step in one pass (sequential ramps run plate→bright so "more" still reads as
"stronger")."""

from __future__ import annotations

import re

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#6b6964"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
FONT = '"Libre Franklin", system-ui, -apple-system, sans-serif'
SERIF = '"Libre Caslon Text", Georgia, serif'

CATEGORICAL = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#e34948",
]
CATEGORICAL_DARK = [
    "#86b1f2",
    "#e7a0b4",
    "#6fd0a8",
    "#e3c46e",
    "#c9a3e8",
    "#b7d77a",
    "#a99cf0",
    "#ff8f8f",
]
SCENARIO_LIGHT = "#c4501c"
SCENARIO_PLATE = "#ff8a4c"

# Light token → plate token. Matched case-insensitively in a single regex pass, so a plate value
# that equals another light key is never re-mapped.
DARK_MAP: dict[str, str] = {
    SURFACE: "#12213f",
    "#ffffff": "#192b52",
    '"white"': '"#12213f"',  # quoted: only the bare colour value, never inside words
    INK: "#efe9da",
    INK_2: "#b9c3dc",
    MUTED: "#8d9bbd",
    GRID: "#22355c",
    AXIS: "#4a5f8f",
    "#b9b7b1": "#3b5080",
    "rgba(82,81,78,0.07)": "rgba(239,233,218,0.05)",
    "rgba(255,255,255,0.9)": "rgba(18,33,63,0.92)",
    "rgba(98,80,214,0.1)": "rgba(255,138,76,0.14)",
    "rgba(196,80,28,0.1)": "rgba(255,138,76,0.12)",
    SCENARIO_LIGHT: SCENARIO_PLATE,
    "#8a6a1c": "#e3c46e",  # target gold
    "rgba(138,106,28,0.1)": "rgba(227,196,110,0.1)",
    # Sequential ramps (Gaps heatmaps): low end sits on the plate, high end is bright ink.
    "#f4f7fc": "#17284b",
    "#86b3e8": "#3d64a8",
    "#0f3f7a": "#b4cdfa",
    "#fdf4ef": "#1b2645",
    "#f3a37f": "#8a5a3a",
    "#8a2f0e": "#f0b45a",
    **dict(zip(CATEGORICAL, CATEGORICAL_DARK, strict=True)),
}
_DARK_RE = re.compile(
    "|".join(re.escape(k) for k in sorted(DARK_MAP, key=len, reverse=True)), re.IGNORECASE
)
_DARK_LOOKUP = {k.lower(): v for k, v in DARK_MAP.items()}


def _template() -> go.layout.Template:
    return go.layout.Template(
        layout=dict(
            font=dict(family=FONT, size=12, color=INK_2),
            title=dict(font=dict(family=SERIF, size=15, color=INK), x=0, xanchor="left"),
            paper_bgcolor=SURFACE,
            plot_bgcolor=SURFACE,
            colorway=CATEGORICAL,
            xaxis=dict(
                gridcolor=GRID,
                gridwidth=1,
                zeroline=False,
                linecolor=AXIS,
                linewidth=1,
                ticks="outside",
                tickcolor=AXIS,
                ticklen=4,
                tickfont=dict(color=MUTED),
                title=dict(font=dict(color=INK_2, size=12)),
            ),
            yaxis=dict(
                gridcolor=GRID,
                gridwidth=1,
                zeroline=False,
                linecolor=AXIS,
                linewidth=1,
                tickfont=dict(color=INK_2),
                title=dict(font=dict(color=INK_2, size=12)),
            ),
            legend=dict(
                font=dict(color=INK_2, size=12), bgcolor="rgba(0,0,0,0)", title=dict(text="")
            ),
            hoverlabel=dict(
                bgcolor="#ffffff", bordercolor=GRID, font=dict(family=FONT, color=INK, size=12)
            ),
            margin=dict(l=10, r=16, t=36, b=10),
        )
    )


pio.templates["ember"] = _template()
pio.templates.default = "plotly_white+ember"

PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def is_dark() -> bool:
    """True when the viewer is using the dark theme (Streamlit reruns the page when it changes)."""
    try:
        return getattr(st.context.theme, "type", None) == "dark"
    except Exception:  # noqa: BLE001 - no browser context (bare mode, AppTest)
        return False


def to_dark(fig: go.Figure) -> go.Figure:
    """The same figure with every light colour token swapped for its dark step."""
    blob = _DARK_RE.sub(lambda m: _DARK_LOOKUP[m.group(0).lower()], fig.to_json())
    return pio.from_json(blob)


def show_chart(fig: go.Figure, width: str = "stretch", **kw):
    """Render with the EMBER template (not Streamlit's theme), so charts look the same everywhere."""
    fig.update_layout(template="plotly_white+ember", paper_bgcolor=SURFACE, plot_bgcolor=SURFACE)
    if is_dark():
        fig = to_dark(fig)
    return st.plotly_chart(fig, theme=None, width=width, config=PLOTLY_CONFIG, **kw)
