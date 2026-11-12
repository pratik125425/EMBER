"""Evidence Map: X_O₂ vs P (log) with evidence range boxes, NASA target boxes, ppO₂ isolines and
the scenario star (spec §13, ticket T07).

Honesty rules for the map:
- A record is drawn as a box/point only when BOTH X_O₂ and P are *known* (status="known").
- Records with known X_O₂ but unknown P are drawn in a separate "P unknown" strip under the map,
  never placed at a guessed pressure.
- Records with unknown X_O₂ are not drawn; the page lists them with the reason.
- Burner-side oxygen records (o2_context = burner_oxidizer_flow) are labeled on the map.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ember import config
from ember.llm.templates import format_range
from ember.schemas import Evidence, Scenario
from ember.units import kpa_to_psi

# Phenomenon → family (fixed categorical hue per family; slots 1–6 of the validated palette).
PHENOMENON_FAMILY: dict[str, str] = {
    "spread_opposed": "Flame spread",
    "spread_concurrent": "Flame spread",
    "extinction": "Extinction / limits",
    "limiting_oxygen": "Extinction / limits",
    "suppression": "Extinction / limits",
    "smoke_particles": "Smoke & detection",
    "detector_response": "Smoke & detection",
    "cool_flame": "Cool flames & structure",
    "flame_structure": "Cool flames & structure",
    "soot_smoke_point": "Cool flames & structure",
    "ignition": "Ignition",
    "burning_rate": "Burning rate",
}
FAMILY_COLORS: dict[str, str] = {
    "Flame spread": "#2a78d6",
    "Extinction / limits": "#eb6834",
    "Smoke & detection": "#1baf7a",
    "Cool flames & structure": "#eda100",
    "Ignition": "#e87ba4",
    "Burning rate": "#008300",
}
GRAVITY_SYMBOL: dict[str, str] = {
    "microgravity": "circle",
    "1g": "square",
    "simulated_partial": "diamond",
    "unknown": "x",
}
GRAVITY_LABEL: dict[str, str] = {
    "microgravity": "µg",
    "1g": "1-g",
    "simulated_partial": "simulated partial-g",
    "unknown": "gravity unknown",
}
X_RANGE = (0.10, 0.60)
P_RANGE = (20.0, 210.0)
PPO2_ISOLINES_KPA: tuple[float, ...] = (15.0, 21.2, 25.0, 30.0)
INK_SECONDARY = "#52514e"
GRID = "#e1e0d9"


@dataclass
class Placement:
    plotted: list[Evidence]  # both X_O₂ and P known
    p_unknown: list[Evidence]  # X_O₂ known, P unknown → strip
    not_plottable: list[tuple[Evidence, str]]  # (record, reason)


def classify(evidence: list[Evidence]) -> Placement:
    plotted, strip, nope = [], [], []
    for e in evidence:
        if e.o2_context.value == "burner_oxidizer_flow":
            nope.append((e, "O₂ is burner/oxidizer-side, not ambient"))
        elif e.x_o2.status != "known":
            reason = "X_O₂ not applicable" if e.x_o2.status == "not_applicable" else "X_O₂ unknown"
            nope.append((e, reason))
        elif e.p_kpa.status == "known":
            plotted.append(e)
        else:
            strip.append(e)
    return Placement(plotted, strip, nope)


def family_for(e: Evidence, scenario_phenomenon: str | None) -> str:
    phens = [p.value for p in e.phenomena]
    if scenario_phenomenon in phens:
        return PHENOMENON_FAMILY[scenario_phenomenon]
    return PHENOMENON_FAMILY[phens[0]] if phens else "Flame spread"


def _hex_to_rgba(h: str, a: float) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def _hover(e: Evidence, res: dict | None) -> str:
    lines = [
        f"<b>{e.investigation}</b> · {e.evidence_id}",
        f"X_O₂ {format_range(e.x_o2, '{:.3g}')}"
        + (
            " (burner/oxidizer-side, not ambient)"
            if e.o2_context.value == "burner_oxidizer_flow"
            else ""
        ),
        f"P {format_range(e.p_kpa, '{:.4g}', 'kPa')}",
        f"flow {format_range(e.u_cms, '{:.3g}', 'cm/s')} · {GRAVITY_LABEL[e.gravity.value]}",
        f"fuel: {e.fuel_name or e.fuel_class.value.replace('_', ' ')}",
        "phenomena: " + ", ".join(p.value.replace("_", " ") for p in e.phenomena),
    ]
    if res:
        lines.append(
            f"D = {res['D']:.3f} (exp(D) = {res['expD']:.2f}×) · R = {res['R']:.3f} · rank {res['rank']}"
        )
    if e.psi_id is None:
        lines.append("non-PSI NASA source")
    return "<br>".join(lines)


def evidence_map(
    evidence: list[Evidence],
    scenario: Scenario | None = None,
    results: list[dict] | None = None,
    show_ppo2: bool = True,
    show_targets: bool = True,
    show_challenge_region: bool = True,
    families: set[str] | None = None,
) -> tuple[go.Figure, Placement]:
    """Build the map. Returns (figure, placement) so the page can list what was not drawn."""
    by_res = {r["evidence_id"]: r for r in (results or [])}
    phen = scenario.phenomenon.value if scenario else None
    placement = classify(evidence)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.84, 0.16],
        vertical_spacing=0.09,
        subplot_titles=(None, "X_O₂ known, pressure unknown (not placed on the P axis)"),
    )
    legend_done: set[str] = set()
    fig.update_annotations(font=dict(size=12, color=INK_SECONDARY))  # subplot title styling

    # ---- Challenge region and NASA target boxes (shapes, below data) -------------------------
    if show_challenge_region:
        fig.add_shape(
            type="rect",
            x0=0.30,
            x1=X_RANGE[1],
            y0=P_RANGE[0],
            y1=70.33,
            row=1,
            col=1,
            fillcolor="rgba(82,81,78,0.07)",
            line=dict(width=0),
            layer="below",
        )
        fig.add_annotation(
            x=0.31,
            y=math.log10(22.0),
            xref="x",
            yref="y",
            showarrow=False,
            text="Challenge brief: ≥30% O₂ at ≤10.2 psia",
            xanchor="left",
            font=dict(size=11, color=INK_SECONDARY),
        )
    if show_targets:
        for name, x, p in config.TARGETS:
            dx, dp = config.TARGET_TOL_X_O2, p * config.TARGET_TOL_P_FRAC
            fig.add_shape(
                type="rect",
                x0=x - dx,
                x1=x + dx,
                y0=p - dp,
                y1=p + dp,
                row=1,
                col=1,
                line=dict(color=config.TARGET_ACCENT, width=1.5),
                fillcolor=_hex_to_rgba(config.TARGET_ACCENT, 0.10),
                layer="below",
            )
            fig.add_annotation(
                x=x + dx,
                y=math.log10(p + dp),
                xref="x",
                yref="y",
                text=name,
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
                xshift=4,
                font=dict(size=11, color=config.TARGET_ACCENT),
            )

    # ---- ppO₂ isolines ------------------------------------------------------------------------
    if show_ppo2:
        xs = [X_RANGE[0] + i * (X_RANGE[1] - X_RANGE[0]) / 60 for i in range(61)]
        for ppo2 in PPO2_ISOLINES_KPA:
            ys = [ppo2 / x for x in xs]
            pts = [(x, y) for x, y in zip(xs, ys, strict=True) if P_RANGE[0] <= y <= P_RANGE[1]]
            if not pts:
                continue
            fig.add_trace(
                go.Scatter(
                    x=[p[0] for p in pts],
                    y=[p[1] for p in pts],
                    mode="lines+text",
                    line=dict(color=INK_SECONDARY, width=1, dash="dot"),
                    text=[""] * (len(pts) - 1) + [f"ppO₂ {ppo2:g} kPa"],
                    textposition="top left",
                    textfont=dict(size=10, color=INK_SECONDARY),
                    hoverinfo="skip",
                    showlegend=False,
                    name=f"ppO₂ {ppo2:g} kPa",
                ),
                row=1,
                col=1,
            )

    # ---- Evidence boxes/points (batched: one outline trace + one marker trace per family) -------
    boxes: dict[str, tuple[list, list]] = {}
    marks: dict[str, dict[str, list]] = {}
    for e in placement.plotted:
        fam = family_for(e, phen)
        if families is not None and fam not in families:
            continue
        x0, x1, y0, y1 = e.x_o2.min, e.x_o2.max, e.p_kpa.min, e.p_kpa.max
        is_point = x0 == x1 and y0 == y1
        if not is_point:
            bx, by = boxes.setdefault(fam, ([], []))
            bx += [x0, x1, x1, x0, x0, None]
            by += [y0, y0, y1, y1, y0, None]
        m = marks.setdefault(fam, {"x": [], "y": [], "sym": [], "size": [], "hover": [], "id": []})
        m["x"].append((x0 + x1) / 2)
        m["y"].append((y0 * y1) ** 0.5)
        m["sym"].append(GRAVITY_SYMBOL[e.gravity.value])
        m["size"].append(11 if is_point else 9)
        m["hover"].append(_hover(e, by_res.get(e.evidence_id)))
        m["id"].append(e.evidence_id)
    for fam, (bx, by) in boxes.items():
        color = FAMILY_COLORS[fam]
        fig.add_trace(
            go.Scatter(
                x=bx,
                y=by,
                mode="lines",
                fill="toself",
                fillcolor=_hex_to_rgba(color, 0.18),
                line=dict(color=color, width=2),
                hoverinfo="skip",
                showlegend=False,
                legendgroup=fam,
                name=fam,
            ),
            row=1,
            col=1,
        )
    for fam, m in marks.items():
        color = FAMILY_COLORS[fam]
        fig.add_trace(
            go.Scatter(
                x=m["x"],
                y=m["y"],
                mode="markers",
                name=fam,
                legendgroup=fam,
                showlegend=fam not in legend_done,
                marker=dict(
                    symbol=m["sym"], size=m["size"], color=color, line=dict(color="white", width=2)
                ),
                hovertext=m["hover"],
                hoverinfo="text",
                customdata=m["id"],
            ),
            row=1,
            col=1,
        )
        legend_done.add(fam)

    # ---- P-unknown strip: one row per investigation, each record's O₂ range as a segment ----------
    strip: dict[str, dict[str, list]] = {}
    for e in placement.p_unknown:
        fam = family_for(e, phen)
        if families is not None and fam not in families:
            continue
        t = strip.setdefault(fam, {"x": [], "y": [], "sym": [], "hover": [], "id": []})
        hover = _hover(e, by_res.get(e.evidence_id))
        t["x"] += [e.x_o2.min, e.x_o2.max, None]
        t["y"] += [e.investigation, e.investigation, None]
        t["sym"] += [GRAVITY_SYMBOL[e.gravity.value]] * 2 + ["circle"]
        t["hover"] += [hover, hover, None]
        t["id"] += [e.evidence_id, e.evidence_id, None]
    for fam, t in strip.items():
        color = FAMILY_COLORS[fam]
        fig.add_trace(
            go.Scatter(
                x=t["x"],
                y=t["y"],
                mode="lines+markers",
                name=fam,
                legendgroup=fam,
                showlegend=fam not in legend_done,
                line=dict(color=color, width=4),
                marker=dict(
                    symbol=t["sym"], size=9, color=color, line=dict(color="white", width=2)
                ),
                hovertext=t["hover"],
                hoverinfo="text",
                customdata=t["id"],
            ),
            row=2,
            col=1,
        )
        legend_done.add(fam)

    # ---- Scenario star ---------------------------------------------------------------------------
    if scenario and scenario.x_o2 is not None and scenario.p_kpa is not None:
        fig.add_trace(
            go.Scatter(
                x=[scenario.x_o2],
                y=[scenario.p_kpa],
                mode="markers",
                name="Your scenario",
                marker=dict(
                    symbol="star",
                    size=18,
                    color=config.SCENARIO_ACCENT,
                    line=dict(color="white", width=2),
                ),
                hovertext=[
                    f"<b>Scenario</b><br>X_O₂ {scenario.x_o2:.3f} · P {scenario.p_kpa:.1f} kPa "
                    f"({kpa_to_psi(scenario.p_kpa):.2f} psia) · ppO₂ {scenario.x_o2 * scenario.p_kpa:.1f} kPa"
                ],
                hoverinfo="text",
            ),
            row=1,
            col=1,
        )

    # Gravity symbol legend entries (shape carries gravity, color carries family).
    for g, sym in GRAVITY_SYMBOL.items():
        if any(e.gravity.value == g for e in placement.plotted + placement.p_unknown):
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    name=GRAVITY_LABEL[g],
                    marker=dict(symbol=sym, size=9, color=INK_SECONDARY),
                    legendgroup="gravity",
                    legendgrouptitle_text="Marker shape = gravity",
                ),
                row=1,
                col=1,
            )

    fig.update_xaxes(
        title_text="Oxygen mole fraction X_O₂",
        range=list(X_RANGE),
        gridcolor=GRID,
        zeroline=False,
        row=2,
        col=1,
    )
    fig.update_xaxes(range=list(X_RANGE), gridcolor=GRID, zeroline=False, row=1, col=1)
    fig.update_yaxes(
        title_text="Total pressure P, kPa (log)",
        type="log",
        range=[math.log10(P_RANGE[0]), math.log10(P_RANGE[1])],
        gridcolor=GRID,
        row=1,
        col=1,
        tickvals=[20, 30, 40, 56.5, 70.3, 101.3, 150, 200],
        ticktext=["20", "30", "40", "56.5 (8.2 psia)", "70.3 (10.2)", "101.3 (14.7)", "150", "200"],
    )
    fig.update_yaxes(showticklabels=False, title_text=None, row=2, col=1)
    fig.update_layout(
        height=640,
        margin=dict(l=10, r=10, t=20, b=10),
        plot_bgcolor="#fcfcfb",
        font=dict(size=12),
        legend=dict(orientation="v", x=1.01, y=1, groupclick="toggleitem"),
        hovermode="closest",
    )
    return fig, placement
