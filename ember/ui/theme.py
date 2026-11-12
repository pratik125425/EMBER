"""One Plotly template for every chart (dataviz reference palette: recessive grid and axes, ink
tokens for text, series colours only on marks), in a light and a dark variant.

Chart code is written once against the LIGHT tokens. ``show_chart`` renders with the template and,
when the viewer has picked the dark theme, swaps every light token for its dark step in one pass
(same hues stepped for the dark surface, not a different palette; sequential ramps run
surface→bright so "more" still reads as "stronger")."""

from __future__ import annotations

import re

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
FONT = '"Source Sans", "Source Sans Pro", "Source Sans 3", system-ui, -apple-system, sans-serif'
SERIF = '"Source Serif", "Source Serif 4", "Source Serif Pro", Georgia, serif'

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
    "#3987e5",
    "#d95926",
    "#199e70",
    "#c98500",
    "#d55181",
    "#008300",
    "#9085e9",
    "#e66767",
]

# Light token → dark token. Matched case-insensitively in a single regex pass, so a dark value
# that equals another light key (e.g. INK_2 dark = AXIS light) is never re-mapped.
DARK_MAP: dict[str, str] = {
    SURFACE: "#1a1a19",
    "#ffffff": "#242423",
    '"white"': '"#242423"',  # quoted: only the bare colour value, never inside words
    INK: "#f0efec",
    INK_2: "#c3c2b7",
    MUTED: "#9a9890",
    GRID: "#383835",
    AXIS: "#5a5953",
    "#b9b7b1": "#6b6a65",
    "rgba(82,81,78,0.07)": "rgba(240,239,236,0.06)",
    "rgba(255,255,255,0.9)": "rgba(26,26,25,0.92)",
    "rgba(98,80,214,0.1)": "rgba(144,133,233,0.16)",
    # Sequential ramps (Gaps heatmaps): low end sits near the surface in both modes.
    "#f4f7fc": "#1f2733",
    "#86b3e8": "#2a5a96",
    "#0f3f7a": "#5b93da",
    "#fdf4ef": "#2e221c",
    "#f3a37f": "#8f4220",
    "#8a2f0e": "#e07a4a",
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
