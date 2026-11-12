"""Plotly figures shared by pages. Palette: ember.config.WHY_BAR_COLORS (fixed hue per dimension)."""

from __future__ import annotations

import plotly.graph_objects as go

from ember import config

DIM_LABELS = {"x_o2": "O₂", "p_kpa": "Pressure", "u_cms": "Flow"}


def why_bars(results: list[dict], max_rows: int = 10) -> go.Figure:
    """Horizontal stacked bars: each record's D split by dimension (the 'why' of its rank)."""
    rows = results[:max_rows]
    labels = [f"{r['rank']}. {r['evidence_id']}" for r in rows][::-1]
    fig = go.Figure()
    for dim in config.DIMS:
        vals = [(r["parts"].get(dim) or 0.0) for r in rows][::-1]
        hover = []
        for r in rows[::-1]:
            v = r["parts"].get(dim, "n/a")
            if v is None:
                hover.append(f"{DIM_LABELS[dim]}: unknown in evidence (not counted)")
            elif v == "n/a":
                hover.append(f"{DIM_LABELS[dim]}: not asked / zero weight")
            else:
                hover.append(f"{DIM_LABELS[dim]}: {v:.3f} of D = {r['D']:.3f}")
        fig.add_bar(
            y=labels,
            x=vals,
            name=DIM_LABELS[dim],
            orientation="h",
            marker=dict(color=config.WHY_BAR_COLORS[dim], line=dict(color="white", width=2)),
            hovertext=hover,
            hoverinfo="text",
        )
    # Mark lower-bound / no-condition rows at the bar end with text, not color.
    annotations = []
    for r in rows[::-1]:
        if r["tier"] == config.TIER_NO_CONDITIONS:
            txt = "no known conditions"
        elif r["D_lower_bound"]:
            txt = "lower bound"
        else:
            continue
        annotations.append(
            dict(
                x=r["D"],
                y=f"{r['rank']}. {r['evidence_id']}",
                text=txt,
                showarrow=False,
                xanchor="left",
                xshift=6,
                font=dict(size=11, color="#52514e"),
            )
        )
    fig.add_vline(
        x=config.D_ENVELOPE_THRESHOLD,
        line=dict(color="#52514e", width=1, dash="dot"),
        annotation_text="D = 1 (exp(D) ≈ 2.7×)",
        annotation_position="top",
    )
    fig.update_layout(
        barmode="stack",
        height=max(260, 32 * len(rows) + 80),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Transfer distance D (elasticity-weighted log distance)",
        yaxis_title=None,
        legend=dict(orientation="h", y=-0.25, traceorder="normal"),
        plot_bgcolor="#fcfcfb",
        annotations=annotations,
        xaxis=dict(gridcolor="#e1e0d9", zeroline=False),
        font=dict(size=12),
    )
    return fig


def stability_bars(results: list[dict], stability: dict, max_rows: int = 10, key=None) -> go.Figure:
    """P(top-k) per row from the Monte Carlo (single series → one hue, threshold line).

    ``key(row)`` gives the label the stability result is keyed by (evidence id, or investigation
    when the ranking is grouped). Defaults to the evidence id.
    """
    key = key or (lambda r: r["evidence_id"])
    rows = results[:max_rows]
    labels = [f"{r['rank']}. {r['evidence_id']}" for r in rows][::-1]
    p = [stability["p_topk"].get(key(r), 0.0) for r in rows][::-1]
    hover = [
        f"{key(r)}<br>P(top-{stability['k']}) = {stability['p_topk'].get(key(r), 0.0):.2f}"
        f"<br>rank median {stability['rank_median'].get(key(r), float('nan')):.0f}, "
        f"range {stability['rank_min'].get(key(r), '?')}–{stability['rank_max'].get(key(r), '?')}"
        for r in rows
    ][::-1]
    fig = go.Figure(
        go.Bar(
            y=labels,
            x=p,
            orientation="h",
            marker=dict(color=config.SCENARIO_ACCENT, line=dict(color="white", width=2)),
            hovertext=hover,
            hoverinfo="text",
            showlegend=False,
        )
    )
    fig.add_vline(
        x=config.STABLE_P_TOPK,
        line=dict(color="#52514e", width=1, dash="dot"),
        annotation_text=f"stable ≥ {config.STABLE_P_TOPK:.0%}",
        annotation_position="top",
    )
    fig.update_layout(
        height=max(240, 30 * len(rows) + 70),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(
            title=f"P(in top-{stability['k']}) over {stability['n']} perturbed rankings",
            range=[0, 1.02],
            gridcolor="#e1e0d9",
            zeroline=False,
            tickformat=".0%",
        ),
        plot_bgcolor="#fcfcfb",
        font=dict(size=12),
    )
    return fig
