"""Validation page (ticket T14): gold-set results, ablations, CompareLab. Only real numbers; "pending" otherwise."""

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

from ember import config
from ember.demo import air_fields, lunar_fields, ranked, scenario_dict
from ember.eval.run_eval import RESULTS
from ember.paths import ROOT
from ember.registry import load_registry
from ember.ui.badges import sidebar_legend
from ember.ui.layout import page_header
from ember.ui.theme import show_chart

st.set_page_config(page_title="EMBER · Validation", layout="wide")
sidebar_legend()
page_header(
    "Validation",
    "What has been measured so far, and what is built but still waiting for human relevance labels. Only measured numbers appear here; nothing is estimated or filled in.",
    section="Trust",
)

if not RESULTS.exists():
    st.info("Pending: the evaluation has not been run. Run `uv run python -m ember.eval.run_eval`.")
    st.stop()

r = json.loads(RESULTS.read_text())
g = r["gold"]
queries = {
    q["qid"]: q
    for q in yaml.safe_load((ROOT / "ember" / "eval" / "gold" / "queries.yaml").read_text())
}


# ------------------------------------------------------------------ measured now (top of page)
@st.cache_data(show_spinner=False)
def _stability() -> dict:
    """Monte Carlo rank stability for the two demo scenarios, from the same cache the Ask page uses."""
    reg = load_registry()
    lunar = lunar_fields()
    out = {}
    for name, fields in (("Lunar habitat", lunar), ("Earth air", air_fields(lunar))):
        res, stab, _ = ranked(scenario_dict(fields), reg)
        out[name] = {
            "stable": sum(1 for x in res[: stab["k"]] if x["stable"]),
            "k": stab["k"],
            "n": stab["n"],
            "tau": stab["kendall_tau_median"],
            "tau_ci": stab["kendall_tau_ci"],
        }
    return out


adv = r.get("adversarial")
cl = r.get("comparelab")
stab = _stability()

st.subheader("Measured now")
m = st.columns(4)
if adv:
    m[0].metric(
        "Trick prompts handled",
        f"{sum(p['handled'] for p in adv['prompts'])} of {adv['n_prompts']}",
        help="Spec §12.4 prompts (e.g. 'is this material safe on the Moon?') that must be refused or flagged.",
    )
    m[1].metric(
        "Hostile sentences dropped",
        f"{sum(p['handled'] for p in adv['probes'])} of {adv['n_probes']}",
        help="Sentences with invented numbers, fake citations or 'safe' claims fed to the cite-or-drop verifier.",
    )
if cl:
    m[2].metric(
        "False 'comparable' verdicts",
        f"{cl['false_comparable']} of {cl['n']}",
        help="CompareLab starter pairs labelled from spec statements. A smoke test, not a rate.",
    )
lunar_s = stab["Lunar habitat"]
m[3].metric(
    "Top-5 stable (lunar demo)",
    f"{lunar_s['stable']} of {lunar_s['k']}",
    help=f"Stays in the top {lunar_s['k']} in ≥{config.STABLE_P_TOPK:.0%} of {lunar_s['n']} runs with "
    f"elasticities ±{config.MC_EPS_PCT:.0%} and priors ±{config.MC_PRIOR_PCT:.0%}.",
)
st.caption(
    "Each number is recomputed from the evaluation run or the rank-stability cache; hover a tile for its definition."
)

st.subheader("Rank stability")
st.markdown(
    f"EMBER's weights come from published correlations, so the ranking should not hinge on their exact values. "
    f"Each scenario is re-ranked {lunar_s['n']} times with every elasticity perturbed by up to "
    f"±{config.MC_EPS_PCT:.0%} and every prior by up to ±{config.MC_PRIOR_PCT:.0%}. This tests sensitivity to "
    "EMBER's own weights, not the underlying NASA data."
)
st.dataframe(
    pd.DataFrame(
        [
            {
                "Scenario": name,
                f"Stable in top {v['k']}": f"{v['stable']} of {v['k']}",
                "Median Kendall τ vs. base order": f"{v['tau']:.3f}",
                "95% interval of τ": f"{v['tau_ci'][0]:.3f}–{v['tau_ci'][1]:.3f}",
                "Runs": v["n"],
            }
            for name, v in stab.items()
        ]
    ),
    hide_index=True,
    width="stretch",
)
st.caption("Open Ask to run the same test on any scenario you set in the sidebar.")

st.subheader("Trick prompts and hostile sentences")
if adv:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Prompt": p["prompt"],
                    "Expected": p["expected"],
                    "Shown": ", ".join(p["notices"]) or "—",
                    "Handled": "yes" if p["handled"] else "NO",
                    "Path": p["mode"],
                }
                for p in adv["prompts"]
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Hostile sentences fed to the verifier"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Sentence": p["text"],
                        "Dropped": "yes" if p["handled"] else "NO",
                        "Reason": p["reason"] or "—",
                    }
                    for p in adv["probes"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    if any("template" in m for m in adv["narrator_modes"]):
        st.caption(
            "These runs used the rule-based parser and template narration because no LLM answer was cached "
            "or callable. The guards and verifier are the same in LLM mode, but LLM-mode results are not yet measured."
        )
else:
    st.write("Pending.")

st.subheader("CompareLab")
if cl:
    st.markdown(
        f"False-'comparable' verdicts: **{cl['false_comparable']} of {cl['n']}** labelled pairs "
        f"(exact agreement {cl['exact_agreement']:.0%}). This is a starter set labelled from spec statements; "
        f"the target is {cl['target_pairs']} pairs with a second annotator, so treat it as a smoke test, not a rate."
    )
else:
    st.write("Pending.")

st.divider()
st.subheader("Ranking benchmark: built, waiting for labels")
st.markdown(
    "The benchmark that answers *does EMBER rank better than text search and an additive score?* is fully built: "
    f"{r['n_queries']} questions, a pool of {len(r['pool'])} investigations, and baselines "
    f"({', '.join(s for s in r['systems'] if s != 'ember')}). Its rankings are already recorded below. "
    "Scores need two independent human relevance labellers; until both finish, EMBER reports no ranking metric "
    "rather than a self-graded one."
)
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Gold queries",
    r["n_queries"],
    help=f"{r['n_scenario_queries']} with a confirmed scenario; the rest are text-only.",
)
c2.metric("Annotator A labels", f"{g['labeled_A']} / {g['pairs']}")
c3.metric("Annotator B labels", f"{g['labeled_B']} / {g['pairs']}")
c4.metric("Frozen (gold-v1)", "yes" if g["frozen"] else "no")
st.caption(
    f"Results generated {r['generated_at']} · pool of {len(r['pool'])} investigations · systems: {', '.join(r['systems'])}"
    + (f" · unavailable: {', '.join(r['unavailable'])}" if r.get("unavailable") else "")
)

if r["status"] == "error":
    st.error(r["error"])
elif r["status"] != "complete":
    st.warning(
        "**Pending human labels.** No ranking metric is reported yet. "
        "Two annotators label `ember/eval/gold/qrels_A.csv` and `qrels_B.csv` from NASA documents per "
        "`GUIDELINE.md`; `gold_tools merge` computes agreement (weighted κ) and `gold_tools freeze` locks the set "
        "before any tuning (spec §12.1)."
    )
    st.markdown(
        "Metrics that will appear here: nDCG@5, Recall@5 and MRR with 95% bootstrap CIs for random, BM25, dense, "
        "hybrid, additive and EMBER; a paired permutation test against the best baseline; six ablations."
    )
else:
    sq = r["scenario_queries"]
    comp = r.get("comparison")
    if comp:
        (st.success if comp["verdict"] == "ember_better" else st.error)(
            f"{comp['statement']}  Paired permutation p = {comp['permutation']['p_value']:.3f} over {comp['permutation']['n']} queries."
        )
    rows = []
    for name, ms in sq["metrics"].items():
        rows.append(
            {
                "System": name,
                **{f"{m} mean": round(v["mean"], 3) for m, v in ms.items()},
                **{f"{m} 95% CI": f"{v['ci95'][0]:.3f}–{v['ci95'][1]:.3f}" for m, v in ms.items()},
                "Queries": ms["ndcg@5"]["n"],
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    names = list(sq["metrics"])
    means = [sq["metrics"][n]["ndcg@5"]["mean"] for n in names]
    lo = [m - sq["metrics"][n]["ndcg@5"]["ci95"][0] for n, m in zip(names, means, strict=True)]
    hi = [sq["metrics"][n]["ndcg@5"]["ci95"][1] - m for n, m in zip(names, means, strict=True)]
    fig = go.Figure(
        go.Bar(
            x=names,
            y=means,
            marker_color=[config.SCENARIO_ACCENT if n == "ember" else "#2a78d6" for n in names],
            error_y=dict(type="data", array=hi, arrayminus=lo, color="#52514e"),
            hovertemplate="%{x}: nDCG@5 %{y:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=320,
        yaxis=dict(title="nDCG@5 (scenario queries)", range=[0, 1], gridcolor="#e1e0d9"),
        plot_bgcolor="#fcfcfb",
        margin=dict(l=10, r=10, t=10, b=10),
    )
    show_chart(fig, width="stretch")
    st.caption(
        f"Scenario queries scored: {len(sq['qids'])}. Gap queries (no investigation labelled ≥ 2, excluded from means): "
        f"{', '.join(r['gap_queries']) or 'none'}. Text-only queries are reported below."
    )
    if r["text_only_queries"]["qids"]:
        st.markdown("**Text-only queries** (text systems only)")
        st.dataframe(
            pd.DataFrame(
                [
                    {"System": n, **{m: round(v["mean"], 3) for m, v in ms.items()}}
                    for n, ms in r["text_only_queries"]["metrics"].items()
                ]
            ),
            hide_index=True,
        )

st.markdown("**Ablations** (scored once labels are frozen)")
abl_desc = {
    "uniform_eps": "uniform weights instead of Ruff 2021 elasticities",
    "no_Q": "granularity prior Q = 1",
    "no_Mf": "fuel prior M_f = 1",
    "no_Mphi": "phenomenon prior M_φ = 1",
    "midpoint": "distance to range midpoint instead of interval",
    "linear": "fractional deviation instead of log ratio",
}
if r["status"] == "complete":
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Variant": n,
                    "Change": abl_desc.get(n.split(":")[-1], "full EMBER"),
                    "nDCG@5": round(ms["ndcg@5"]["mean"], 3),
                    "95% CI": f"{ms['ndcg@5']['ci95'][0]:.3f}–{ms['ndcg@5']['ci95'][1]:.3f}",
                }
                for n, ms in r["ablation_metrics"].items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
else:
    st.dataframe(
        pd.DataFrame(
            [
                {"Variant": f"ember:{k}", "Change": v, "nDCG@5": "pending"}
                for k, v in abl_desc.items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )

st.subheader("Not yet run")
st.markdown(
    "- **Verifier audit** of 50 LLM-generated sentences (spec §12.5): needs live LLM output; not yet run.\n"
    "- **User test** (5 users × 3 tasks vs. the PSI website): manual, not yet run."
)

st.subheader("Rankings per query (inspection only, not a metric)")
qid = st.selectbox("Query", list(queries), format_func=lambda q: f"{q} · {queries[q]['text']}")
sc = queries[qid].get("scenario")
st.caption(
    "Scenario: "
    + (", ".join(f"{k}={v}" for k, v in sc.items()) if sc else "none (text-only question)")
    + (f" · notes: {queries[qid]['notes']}" if queries[qid].get("notes") else "")
)
top = r["rankings_top5"]
cols = [
    n for n in ("random", "bm25", "dense", "hybrid", "additive", "ember") if qid in top.get(n, {})
]
st.dataframe(
    pd.DataFrame({n: top[n][qid] for n in cols}, index=[f"#{i}" for i in range(1, 6)]),
    width="stretch",
)
