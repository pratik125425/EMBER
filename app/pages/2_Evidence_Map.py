"""Evidence Map page (ticket T07): X_O₂ vs P map with range boxes, target rectangles, ppO₂ isolines, scenario star."""

import pandas as pd
import streamlit as st

from ember import config
from ember.engine.score import rank, scenario_to_dict
from ember.llm.templates import format_range
from ember.registry import load_registry
from ember.ui.badges import badges_for
from ember.ui.evidence_map import FAMILY_COLORS, evidence_map
from ember.ui.layout import page_header
from ember.ui.scenario import scenario_chips_html, scenario_sidebar
from ember.ui.theme import show_chart

st.set_page_config(page_title="EMBER · Evidence Map", layout="wide")


@st.cache_resource
def _registry():
    return load_registry()


reg = _registry()
scenario = scenario_sidebar()

page_header(
    "Evidence map",
    "Where NASA tests sit in oxygen–pressure space, and where your scenario sits relative to them. Moving the sidebar sliders re-ranks live.",
    section="Analyse",
)
st.markdown(scenario_chips_html(scenario), unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
show_ppo2 = c1.checkbox("ppO₂ isolines", value=True, help="ppO₂ = X_O₂ · P. Equal-ppO₂ curves.")
show_targets = c2.checkbox(
    "NASA target boxes", value=True, help="Dashed boxes around NASA/TP-2010-216134 atmospheres."
)
show_region = c3.checkbox(
    "Challenge region", value=True, help="≥30% O₂ at ≤10.2 psia, from the challenge brief."
)
fams = c4.multiselect("Phenomenon families", list(FAMILY_COLORS), default=list(FAMILY_COLORS))

results = rank(scenario_to_dict(scenario), reg.evidence_dicts(), include_partial_g=True)
fig, placement = evidence_map(
    reg.evidence,
    scenario,
    results,
    show_ppo2=show_ppo2,
    show_targets=show_targets,
    show_challenge_region=show_region,
    families=set(fams),
)
event = show_chart(
    fig, width="stretch", on_select="rerun", selection_mode="points", key="evidence_map"
)

st.caption(
    "Boxes are tested envelopes (min–max of X_O₂ and P as sourced); points are single conditions. Color = phenomenon "
    "family (the scenario's phenomenon when the record covers it), marker shape = gravity. Transfer distance D is "
    "measured in log space to the nearest box edge, so a scenario inside a box has D = 0 on those dimensions. "
    "Gravity is never a distance term. The LUCI overlay (simulated partial-g, non-PSI) is shown for context only."
)

# ---- Selection details ---------------------------------------------------------------------------
sel_ids: list[str] = []
try:
    sel_ids = [p.get("customdata") for p in event.selection.points if p.get("customdata")]
except Exception:  # noqa: BLE001 - selection payload shape differs across Streamlit versions
    sel_ids = []
if sel_ids:
    by_id = reg.evidence_by_id()
    by_res = {r["evidence_id"]: r for r in results}
    st.subheader("Selected record")
    for eid in dict.fromkeys(sel_ids):
        e, r = by_id.get(eid), by_res.get(eid)
        if not e:
            continue
        st.markdown(
            f"**{e.investigation} — {eid}** · X_O₂ {format_range(e.x_o2, '{:.3g}')} · P {format_range(e.p_kpa, '{:.4g}', 'kPa')} · "
            f"flow {format_range(e.u_cms, '{:.3g}', 'cm/s')} · {e.gravity.value} · "
            + (
                f"D {r['D']:.3f}, exp(D) {r['expD']:.2f}×, R {r['R']:.3f} · {' '.join(badges_for(r))}"
                if r
                else ""
            )
        )

# ---- Live nearest table -------------------------------------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.subheader("Nearest evidence (live)")
    ranked_pool = [
        r
        for r in results
        if reg.evidence_by_id()[r["evidence_id"]].gravity.value != "simulated_partial"
    ]
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "#": i + 1,
                    "Investigation": r["investigation"],
                    "Evidence": r["evidence_id"],
                    "D": round(r["D"], 3),
                    "exp(D)": round(r["expD"], 2),
                    "R": round(r["R"], 3),
                    "Tier": r["tier"].replace("_", " "),
                    "Badges": " · ".join(badges_for(r)),
                }
                for i, r in enumerate(ranked_pool[:8])
            ]
        ),
        hide_index=True,
        width="stretch",
    )
with right:
    st.subheader("Not on the map")
    rows = [(e, "P unknown (shown in strip)") for e in placement.p_unknown] + list(
        placement.not_plottable
    )
    if rows:
        groups: dict[tuple[str, str], list[str]] = {}
        for e, reason in rows:
            groups.setdefault((e.investigation, reason), []).append(e.evidence_id)
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Investigation": inv,
                        "Reason": reason,
                        "Records": len(ids),
                        "Examples": ", ".join(ids[:3]) + (" …" if len(ids) > 3 else ""),
                    }
                    for (inv, reason), ids in sorted(groups.items())
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    st.caption(
        "Records are placed only where both X_O₂ and P are sourced. Nothing is positioned at a guessed value."
    )

st.caption(
    f"Target boxes: ±{config.TARGET_TOL_X_O2 * 100:.2f} pct-points O₂ (33.5–35% control box) and "
    f"±{config.TARGET_TOL_P_FRAC * 100:.0f}% pressure around {', '.join(t[0] for t in config.TARGETS)} "
    f"[{config.TARGET_SOURCE}]. Partial-gravity scenarios have no evidence at their gravity; see the Gaps page."
)
