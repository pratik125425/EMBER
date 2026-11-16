"""Ask page: question → proposed scenario (user confirms) → deterministic ranking → cite-or-drop summary."""

import pandas as pd
import streamlit as st

from ember import config
from ember.engine.robustness import cached_rank_stability
from ember.engine.score import collapse, rank, scenario_to_dict
from ember.llm.guards import question_guards, refused
from ember.llm.narrator import narrate
from ember.llm.parser import parse_question
from ember.llm.templates import format_range, partial_g_disclaimer
from ember.registry import load_registry
from ember.ui.badges import badges_for
from ember.ui.charts import stability_bars, why_bars
from ember.ui.layout import callout, page_header, panel_title
from ember.ui.scenario import PARSE_LABELS, apply_parsed, scenario_chips_html, scenario_sidebar
from ember.ui.theme import show_chart

st.set_page_config(page_title="EMBER · Ask", layout="wide")


@st.cache_resource
def _registry():
    return load_registry()


@st.cache_data(show_spinner=False)
def _parse(q: str):
    return parse_question(q)


reg = _registry()
scenario = scenario_sidebar()

page_header(
    "Ask",
    "Which NASA fire experiments apply to this scenario, and how far are you extrapolating?",
    section="Analyse",
)
ask_panel = st.container(border=True, key="panel_ask")
ask_panel.markdown(
    '<div class="ember-panel-title"><h3>Active scenario</h3><span>set in the sidebar</span></div>'
    + scenario_chips_html(scenario),
    unsafe_allow_html=True,
)

question = ask_panel.text_input(
    "Ask in plain language (optional)",
    placeholder="e.g. Fabric flammability in a lunar habitat at 34% O₂ and 8.2 psi",
    help="The question is turned into a proposed scenario. Nothing changes until you press 'Use this scenario'.",
)
with ask_panel:
    if question:
        notices = question_guards(question)
        for n in notices:
            if n.kind == "refuse":
                st.error(n.text)
            elif n.kind != "partial_g":  # the partial-g disclaimer is shown with the results below
                st.warning(n.text)
        if not refused(notices):
            parsed = _parse(question)
            rows = []
            for key, label in PARSE_LABELS.items():
                v = parsed.fields.get(key)
                rows.append(
                    {
                        "Field": label,
                        "Proposed": "—" if v is None else str(v),
                        "Origin": "from your question"
                        if v is not None
                        else (
                            "not stated: stays unspecified"
                            if key == "u_cms"
                            else "not stated: sidebar value kept"
                        ),
                    }
                )
            with st.container(border=True):
                st.markdown("**Proposed scenario** (check it, then confirm)")
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
                for note in (
                    [parsed.fields["notes"]] if parsed.fields.get("notes") else []
                ) + parsed.notes:
                    st.caption(note)
                for d in parsed.dropped:
                    st.caption(f"Dropped from the LLM proposal: {d}")
                if parsed.fields.get("u_cms") is None:
                    st.caption(
                        "Airflow was not stated, so it stays unspecified. EMBER never guesses airflow."
                    )
                st.button(
                    "Use this scenario",
                    type="primary",
                    on_click=apply_parsed,
                    args=(parsed.fields,),
                )
                mode = "LLM (cached)" if parsed.mode == "llm" else "rule-based parser"
                why = f" LLM unavailable: {parsed.error}." if parsed.error else ""
                st.caption(f"Parsed by: {mode}.{why}")
        if st.session_state.get("parse_warning"):
            st.warning(st.session_state.pop("parse_warning"))

    grouped = st.toggle(
        "One row per investigation (best-ranked test)",
        value=True,
        help="Per-test PSI tables add hundreds of near-identical rows. When on, each investigation shows its best-ranked "
        "record and how many records it stands for; rank stability is computed on the same grouping.",
    )

s = scenario_to_dict(scenario)
evidence_dicts = reg.evidence_dicts()
results = rank(s, evidence_dicts)
group_key = "investigation" if grouped else None
stability, stability_cached = cached_rank_stability(s, evidence_dicts, group_by=group_key)
if grouped:
    results = collapse(results, "investigation")


def stab_key(r: dict) -> str:
    return r["group"] if grouped else r["evidence_id"]


for r in results:
    r["p_topk"] = stability["p_topk"].get(stab_key(r), 0.0)
    r["stable"] = stability["stable"].get(stab_key(r), False)
top = results[:10]
by_id = reg.evidence_by_id()

if scenario.gravity_g0 not in config.BRACKET_GRAVITIES:
    text = partial_g_disclaimer()
    body, sep, cite = text.partition(" (")
    callout(
        "No PSI fire test at this gravity",
        body + "." if sep else text,
        "(" + cite if sep else None,
    )
if any(r["D"] > config.D_ENVELOPE_THRESHOLD for r in top):
    callout(
        "Beyond tested envelope",
        "At least one top-10 record implies a response factor above 2.7×.",
    )

rank_panel = st.container(border=True, key="panel_rank")
with rank_panel:
    panel_title("Ranked evidence", "top 10 · scroll sideways on small screens")
    table = pd.DataFrame(
        [
            {
                "#": r["rank"],
                "Investigation": r["investigation"],
                "Evidence": r["evidence_id"],
                "Records": r.get("n_group", 1),
                "R": round(r["R"], 3),
                "D": round(r["D"], 3),
                "exp(D)": round(r["expD"], 2),
                "P(top-5)": round(r["p_topk"], 2),
                "Rank range": f"{stability['rank_min'].get(stab_key(r), '?')}–{stability['rank_max'].get(stab_key(r), '?')}",
                "Tier": r["tier"].replace("_", " "),
                "M_φ": r["priors"]["m_phi"],
                "M_f": r["priors"]["m_f"],
                "Q": r["priors"]["Q"],
                "Badges": " · ".join(badges_for(r)),
            }
            for r in top
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(
        "R = M_φ · M_f · Q · exp(−D). D is the elasticity-weighted log distance; exp(D) is the largest "
        "response factor the published correlation implies. Priors M_φ, M_f, Q are disclosed ordinal choices. "
        "Records with no known conditions are ranked below records with data (R unchanged)."
    )

tau_lo, tau_hi = stability["kendall_tau_ci"]
stab_panel = st.container(border=True, key="panel_stability")
with stab_panel:
    panel_title("Rank stability", "Monte Carlo")
    c1, c2 = st.columns([3, 2])
    with c1:
        show_chart(stability_bars(top, stability, key=stab_key), width="stretch")
    with c2:
        st.metric(
            "Kendall τ vs. base ranking (median)",
            f"{stability['kendall_tau_median']:.3f}",
            help="1.0 = identical order in every perturbed draw.",
        )
        st.markdown(f"95% interval of τ across draws: **{tau_lo:.3f} – {tau_hi:.3f}**")
        pr = stability["params"]
        st.markdown(
            f"{stability['n']} draws · elasticities ±{pr['eps_pct']:.0%} · priors ±{pr['prior_pct']:.0%} · "
            f"seed {pr['seed']} · {'cached' if stability_cached else 'computed now'}"
        )
        st.caption(
            "Each draw multiplies every non-zero elasticity and every non-anchor prior by an independent uniform "
            "factor and re-ranks. Zero elasticities (flow for opposed spread) and the 1.0 anchors stay fixed. "
            "A record is badged **stable** when it stays in the top-5 in ≥80% of draws. This tests sensitivity to "
            "EMBER's own weights, not to the underlying NASA data."
        )

st.subheader("Why: D by dimension")
show_chart(why_bars(top), width="stretch")
if scenario.phenomenon.value == "spread_opposed":
    st.caption(
        "Opposed-flow spread uses ε = (O₂ 0.9, P 0.05, flow 0) from Ruff 2021 (NTRS 20210021318). "
        "Flow has zero weight because the published correlation has no flow term; BASS-II shows a "
        "non-monotonic flow dependence, so a constant flow elasticity would be wrong anyway."
    )

st.subheader("Summary (cite-or-drop)")
use_llm = st.toggle(
    "LLM narrator",
    value=False,
    help="Uses a cached answer when one exists; a live call needs ANTHROPIC_API_KEY. Without either, the "
    "template narration is used. Both go through the same verifier.",
)
narration = narrate(s, top, reg, k=5, question=question or None, use_llm=use_llm)
v = narration.verified
for b in v.banners:
    st.warning(b)
if scenario.gravity_g0 in config.BRACKET_GRAVITIES:
    for d in v.disclaimers:
        st.info(d)
for stmt in v.kept:
    st.markdown(f"- {stmt.text}  \n  <small>`{stmt.badge}`</small>", unsafe_allow_html=True)
mode = "LLM narrator" if narration.mode == "llm" else "template narration"
fallback = f" (LLM unavailable: {narration.error})" if narration.error else ""
st.caption(f"{mode}{fallback} · kept {len(v.kept)} · dropped {v.n_dropped} by the verifier")
if v.dropped:
    with st.expander(f"Dropped sentences ({v.n_dropped})"):
        for text, reason in v.dropped:
            st.markdown(f"- ~~{text}~~ — *{reason}*")

st.subheader("Record details")
for r in top:
    e = by_id[r["evidence_id"]]
    with st.expander(
        f"{r['rank']}. {e.investigation} — {e.evidence_id}  ·  R {r['R']:.3f}  ·  D {r['D']:.3f}"
    ):
        c1, c2 = st.columns([2, 1])
        with c1:
            cond = pd.DataFrame(
                [
                    {
                        "Condition": "X_O₂",
                        "Value": format_range(e.x_o2, "{:.3g}"),
                        "Status": e.x_o2.status,
                        "Context": e.o2_context.value,
                        "Source": e.x_o2.source_id or "",
                        "Locator": e.x_o2.source_locator or "",
                    },
                    {
                        "Condition": "P (kPa)",
                        "Value": format_range(e.p_kpa, "{:.4g}"),
                        "Status": e.p_kpa.status,
                        "Context": "",
                        "Source": e.p_kpa.source_id or "",
                        "Locator": e.p_kpa.source_locator or "",
                    },
                    {
                        "Condition": "Flow (cm/s)",
                        "Value": format_range(e.u_cms, "{:.3g}"),
                        "Status": e.u_cms.status,
                        "Context": e.flow_direction or "",
                        "Source": e.u_cms.source_id or "",
                        "Locator": e.u_cms.source_locator or "",
                    },
                ]
            )
            st.dataframe(cond, hide_index=True, width="stretch")
            st.markdown(
                f"**Fuel:** {e.fuel_name or '—'} ({e.fuel_class.value.replace('_', ' ')}) · "
                f"**Gravity:** {e.gravity.value} · **Hardware:** {e.hardware_family} · "
                f"**Granularity:** {e.granularity.value.replace('_', ' ')}"
            )
            if e.enclosure_note:
                st.markdown(f"**Enclosure:** {e.enclosure_note}")
            if e.diluent:
                st.markdown(f"**Diluent:** {e.diluent}")
        with c2:
            st.markdown("**Flags**")
            for f in r["flags"]:
                st.markdown(f"- {f}")
            st.markdown("**Sources**")
            srcs = reg.source_by_id()
            for sid in e.sources:
                src = srcs.get(sid)
                if src:
                    doi = f" · DOI {src.doi}" if src.doi else ""
                    psi = "PSI" if src.in_psi else "non-PSI"
                    st.markdown(f"- [{sid}]({src.url}) — {src.title} ({psi}{doi})")
                else:
                    st.markdown(f"- {sid}")
            claims = reg.claims_for(e.evidence_id)
            if claims:
                st.markdown("**Claims**")
                for c in claims:
                    st.markdown(
                        f"- {c.text} *[{c.claim_type.value}; {c.source_id}, {c.source_locator}]*"
                    )

if len(results) > 10:
    st.caption(
        f"{len(results) - 10} more records below the top 10. Partial-gravity overlays (LUCI) are excluded from ranking."
    )
