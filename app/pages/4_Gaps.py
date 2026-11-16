"""Gaps page (ticket T09): GapScope coverage/priority panels, hatched partial-g, templated gap report."""

import pandas as pd
import streamlit as st

from ember import config
from ember.engine.gapscope import (
    GRAVITY_NAME,
    all_gravities,
    gap_report_markdown,
    target_coverage,
    top_priority_cells,
)
from ember.registry import load_registry
from ember.ui.gaps_chart import gap_panels
from ember.ui.layout import page_header
from ember.ui.scenario import PHENOMENON_LABELS, scenario_chips_html, scenario_sidebar
from ember.ui.theme import show_chart

st.set_page_config(page_title="EMBER · Gaps", layout="wide")


@st.cache_resource
def _registry():
    return load_registry()


@st.cache_data(show_spinner=False)
def _grids(phen: str, fuel_class: str | None, u: float | None, psi_only: bool):
    ev = _registry().evidence_dicts()
    return all_gravities(ev, phen, fuel_class, u, psi_only)


reg = _registry()
scenario = scenario_sidebar()

page_header(
    "Gaps",
    "What has nobody tested? Coverage of oxygen–pressure space per gravity regime, for the scenario's phenomenon.",
    section="Analyse",
)
st.markdown(scenario_chips_html(scenario), unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
mode = c1.radio(
    "Layer",
    ["coverage", "priority"],
    horizontal=True,
    format_func=lambda m: {"coverage": "Coverage C", "priority": "Priority π"}[m],
)
use_fuel = c2.checkbox(
    "Filter by scenario fuel class",
    value=scenario.fuel_class is not None,
    disabled=scenario.fuel_class is None,
)
psi_only = c3.checkbox(
    "PSI records only",
    value=False,
    help="Exclude non-PSI NASA sources such as the Saffire VI paper.",
)
show_targets = c4.checkbox("NASA target boxes", value=True)

phen = scenario.phenomenon.value
fuel_class = scenario.fuel_class.value if (use_fuel and scenario.fuel_class) else None
u = scenario.u_cms
grids = _grids(phen, fuel_class, u, psi_only)

show_chart(
    gap_panels(grids, mode=mode, scenario=scenario, show_targets=show_targets),
    width="stretch",
)
st.caption(
    f"{PHENOMENON_LABELS.get(phen, phen)} · fuel: {fuel_class.replace('_', ' ') if fuel_class else 'any'} · "
    f"flow: {'not specified (flow dimension not scored)' if u is None else f'{u:g} cm/s'}. "
    "Coverage C = max exp(−D) over records whose every weighted condition is known; C = 1 inside a tested envelope. "
    "Priority π = (1 − C)·T with T = 1 inside NASA target boxes, 0.25 elsewhere — a heuristic, not information gain. "
    "Partial-g panels are hatched: PSI holds no partial-gravity combustion data and EMBER never interpolates between µg and 1-g. "
    "Low coverage is absence of evidence, not a verdict either way."
)

st.subheader("NASA target atmospheres")
rows = target_coverage(reg.evidence_dicts(), phen, fuel_class, u, psi_only)
st.dataframe(
    pd.DataFrame(
        [
            {
                "Target": r["target"],
                "X_O₂": r["x_o2"],
                "P (kPa)": r["p_kpa"],
                "Gravity": GRAVITY_NAME[r["g"]],
                "C": round(r["C"], 2),
                "Nearest evidence": r["nearest"] or "none",
                "D": None if r["D"] is None else round(r["D"], 3),
                "exp(D)": None if r["expD"] is None else round(r["expD"], 2),
                "Flags": ", ".join(r["flags"]) or "—",
                "Complete / partial records": f"{r['n_pool']} / {r['n_partial']}",
            }
            for r in rows
        ]
    ),
    hide_index=True,
    width="stretch",
)

left, right = st.columns(2)
with left:
    st.subheader("Top priority cells")
    cells = top_priority_cells(grids, n=10)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "X_O₂": round(c["x_o2"], 3),
                    "P (kPa)": round(c["p_kpa"], 1),
                    "Gravity": GRAVITY_NAME[c["g"]],
                    "C": round(c["C"], 2),
                    "π": round(c["priority"], 2),
                    "Nearest": c["nearest"] or "none",
                    "Target box": c["target"] or "—",
                }
                for c in cells
            ]
        ),
        hide_index=True,
        width="stretch",
    )
with right:
    st.subheader("Partial-condition evidence (not counted)")
    partial = sorted(
        {e["evidence_id"]: e for gg in grids.values() for e in gg.partial}.values(),
        key=lambda e: e["evidence_id"],
    )
    if partial:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Evidence": e["evidence_id"],
                        "Gravity": e["gravity"],
                        "Missing": ", ".join(
                            k
                            for k in config.DIMS
                            if e.get(f"{k}_min") is None and not (k == "u_cms" and u is None)
                        ),
                    }
                    for e in partial
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.write("None for this selection.")
    st.caption(
        "A record with an unknown pressure cannot cover a pressure range, so it is listed here rather than counted."
    )

st.subheader("Gap report")
md = gap_report_markdown(reg.evidence_dicts(), phen, fuel_class, u, psi_only)
st.download_button(
    "Download gap report (Markdown)",
    md,
    file_name=f"ember_gap_report_{phen}.md",
    mime="text/markdown",
)
with st.expander("Preview report"):
    st.markdown(md)
