"""GapScope panels: one heatmap per gravity, partial-g panels hatched with non-PSI overlays."""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ember import config
from ember.engine.gapscope import GRAVITY_NAME, GapGrid
from ember.schemas import Scenario

# Sequential ramps: one hue, light → dark (coverage = blue, priority = orange).
COVERAGE_SCALE = [[0.0, "#f4f7fc"], [0.5, "#86b3e8"], [1.0, "#0f3f7a"]]
PRIORITY_SCALE = [[0.0, "#fdf4ef"], [0.5, "#f3a37f"], [1.0, "#8a2f0e"]]
INK_SECONDARY = "#52514e"
SHORT_TARGET = {
    "ISS/Earth": "ISS 21%/101",
    "10.2 psia option": "10.2 psia/26.5%",
    "Exploration Atm 8.2/34": "8.2 psia/34%",
}


def gap_panels(
    grids: dict[float, GapGrid],
    mode: str = "coverage",
    scenario: Scenario | None = None,
    show_targets: bool = True,
) -> go.Figure:
    order = [g for g in config.GAP_G if g in grids]
    titles = [
        GRAVITY_NAME[g] + ("  — no evidence in PSI" if grids[g].hatched else "") for g in order
    ]
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=titles,
        horizontal_spacing=0.08,
        vertical_spacing=0.14,
        shared_xaxes=False,
        shared_yaxes=False,
    )
    scale, zlabel = (
        (COVERAGE_SCALE, "Coverage C") if mode == "coverage" else (PRIORITY_SCALE, "Priority π")
    )
    first_bar = True
    for idx, g in enumerate(order):
        gg = grids[g]
        row, col = idx // 2 + 1, idx % 2 + 1
        Z = gg.C if mode == "coverage" else gg.priority
        x0, x1 = float(gg.X[0]), float(gg.X[-1])
        p0, p1 = float(gg.P[0]), float(gg.P[-1])
        if gg.hatched:
            fig.add_trace(
                go.Scatter(
                    x=[x0, x1, x1, x0, x0],
                    y=[p0, p0, p1, p1, p0],
                    mode="lines",
                    fill="toself",
                    fillpattern=dict(
                        shape="/", fgcolor="#b9b7b1", bgcolor="white", size=8, solidity=0.4
                    ),
                    line=dict(color="#b9b7b1", width=1),
                    hoverinfo="skip",
                    showlegend=False,
                ),
                row=row,
                col=col,
            )
            fig.add_annotation(
                x=(x0 + x1) / 2,
                y=math.log10(p0 * 1.12),
                xref=f"x{idx + 1}",
                yref=f"y{idx + 1}",
                text="No PSI evidence at this gravity · C = 0<br>(not interpolated from µg / 1-g)",
                showarrow=False,
                yanchor="bottom",
                font=dict(size=11, color=INK_SECONDARY),
                bgcolor="rgba(255,255,255,0.9)",
            )
            for ov in config.PARTIAL_G_OVERLAYS:
                if abs(ov["gravity_g0"] - g) < 0.02:
                    fig.add_trace(
                        go.Scatter(
                            x=[ov["x_o2"]],
                            y=[ov["p_kpa"]],
                            mode="markers+text",
                            text=[ov["name"].split(" (")[0] + " (not in PSI)"],
                            textposition="bottom right" if ov["p_kpa"] > 90 else "top right",
                            textfont=dict(size=11, color=INK_SECONDARY),
                            marker=dict(
                                symbol="diamond-open",
                                size=13,
                                color=INK_SECONDARY,
                                line=dict(width=2),
                            ),
                            hovertext=[
                                f"<b>{ov['name']}</b><br>X_O₂ {ov['x_o2']:.3f} · P {ov['p_kpa']:.1f} kPa · {ov['gravity_g0']:.3f} g"
                                f"<br>{ov['status']}<br>[{ov['source_id']}]"
                            ],
                            hoverinfo="text",
                            showlegend=False,
                        ),
                        row=row,
                        col=col,
                    )
        else:
            hover = np.empty(Z.shape, dtype=object)
            for i in range(Z.shape[0]):
                for j in range(Z.shape[1]):
                    c = gg.C[i, j]
                    d = "—" if c <= 0 else f"{-math.log(c):.2f}"
                    near = gg.nearest[i, j] or "none"
                    hover[i, j] = (
                        f"X_O₂ {gg.X[j]:.3f} · P {gg.P[i]:.1f} kPa<br>C = {c:.2f} · D = {d}<br>"
                        f"π = {gg.priority[i, j]:.2f}<br>nearest: {near}"
                    )
            fig.add_trace(
                go.Heatmap(
                    x=gg.X,
                    y=gg.P,
                    z=Z,
                    zmin=0,
                    zmax=1,
                    colorscale=scale,
                    showscale=first_bar,
                    colorbar=dict(title=zlabel, thickness=12, len=0.9) if first_bar else None,
                    hovertext=hover,
                    hoverinfo="text",
                    xgap=1,
                    ygap=1,
                ),
                row=row,
                col=col,
            )
            first_bar = False
        if show_targets:
            for name, tx, tp in config.TARGETS:
                dx, dp = config.TARGET_TOL_X_O2, tp * config.TARGET_TOL_P_FRAC
                if not (x0 <= tx <= x1 and p0 <= tp <= p1):
                    continue
                fig.add_shape(
                    type="rect",
                    x0=tx - dx,
                    x1=tx + dx,
                    y0=tp - dp,
                    y1=tp + dp,
                    row=row,
                    col=col,
                    line=dict(color=config.TARGET_ACCENT, width=1.5),
                )
                fig.add_annotation(
                    # Beside the box, not above it: targets stack in pressure and the
                    # top one would clip at the panel edge.
                    x=tx + dx,
                    y=math.log10(tp),
                    xref=f"x{idx + 1}",
                    yref=f"y{idx + 1}",
                    text=SHORT_TARGET.get(name, name),
                    showarrow=False,
                    xanchor="left",
                    yanchor="middle",
                    xshift=4,
                    font=dict(size=10, color=config.TARGET_ACCENT),
                )
        if (
            scenario
            and scenario.gravity_g0 is not None
            and abs(scenario.gravity_g0 - g) < 1e-9
            and scenario.x_o2 is not None
            and scenario.p_kpa is not None
        ):
            fig.add_trace(
                go.Scatter(
                    x=[scenario.x_o2],
                    y=[scenario.p_kpa],
                    mode="markers",
                    name="Your scenario",
                    marker=dict(
                        symbol="star",
                        size=16,
                        color=config.SCENARIO_ACCENT,
                        line=dict(color="white", width=2),
                    ),
                    hovertext=[f"Scenario: X_O₂ {scenario.x_o2:.3f}, P {scenario.p_kpa:.1f} kPa"],
                    hoverinfo="text",
                    showlegend=False,
                ),
                row=row,
                col=col,
            )
        fig.update_xaxes(range=[x0, x1], title_text="X_O₂" if row == 2 else None, row=row, col=col)
        fig.update_yaxes(
            type="log",
            range=[math.log10(p0), math.log10(p1)],
            title_text="P, kPa (log)" if col == 1 else None,
            tickvals=[30, 40, 56.5, 70.3, 101.3],
            ticktext=["30", "40", "56.5", "70.3", "101.3"],
            row=row,
            col=col,
        )
    fig.update_annotations(font=dict(size=12))
    fig.update_layout(
        height=720, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="#fcfcfb", font=dict(size=12)
    )
    return fig
