"""Compare page (ticket T10): CompareLab rule-gated comparability verdicts."""

import html

import pandas as pd
import streamlit as st

from ember.engine.comparelab import (
    CAVEATS,
    COMPARABLE,
    NOT_COMPARABLE,
    compare_evidence,
    compare_measurements,
)
from ember.registry import load_registry
from ember.ui.layout import empty_state, page_header
from ember.ui.scenario import scenario_sidebar

st.set_page_config(page_title="EMBER · Compare", layout="wide")


@st.cache_resource
def _registry():
    return load_registry()


reg = _registry()
scenario_sidebar()  # keeps the shared scenario chip consistent across pages

page_header(
    "Compare",
    "Can these two results be compared? A rule-gated verdict with the confounders listed. Rules run in order; the first failing gate decides.",
    section="Analyse",
)

by_id = reg.evidence_by_id()
ev_ids = sorted(by_id)
meas = {m.measurement_id: m for m in reg.measurements}

mode = st.radio(
    "Compare", ["Evidence records (condition envelopes)", "Measurements"], horizontal=True
)

if mode.startswith("Evidence"):
    default = [i for i in ("BASS-II:campaign", "SAFFIRE6:SIBAL") if i in by_id]
    picked = st.multiselect(
        "Pick two or more evidence records",
        ev_ids,
        default=default,
        format_func=lambda i: f"{i} — {by_id[i].investigation}",
    )
    items = [(i, by_id[i]) for i in picked]

    def run(a, b):
        return compare_evidence(a[1], b[1])
else:
    m_ids = sorted(meas)
    default = [i for i in ("M-BASS2-LOC-ug", "M-BASS2-LOC-1g") if i in meas]
    picked = st.multiselect(
        "Pick two or more measurements",
        m_ids,
        default=default,
        format_func=lambda i: f"{i} — {meas[i].quantity} ({meas[i].evidence_id})",
    )
    items = [(i, meas[i]) for i in picked]

    def run(a, b):
        return compare_measurements(a[1], by_id[a[1].evidence_id], b[1], by_id[b[1].evidence_id])


VERDICT_UI = {
    COMPARABLE: ("Comparable", st.success),
    CAVEATS: ("Comparable with caveats", st.warning),
    NOT_COMPARABLE: ("Not comparable", st.error),
}

if len(items) < 2:
    empty_state(
        "Pick two or more items to compare",
        "Choose evidence records (or measurements) in the box above. EMBER runs the comparability rules "
        "in order and lists every confounder.",
    )
    st.stop()

pairs = [(items[i], items[j]) for i in range(len(items)) for j in range(i + 1, len(items))]
if len(pairs) > 1:
    st.subheader("Pairwise verdicts")
    rows = []
    for a, b in pairs:
        r = run(a, b)
        rows.append(
            {
                "A": a[0],
                "B": b[0],
                "Verdict": VERDICT_UI[r["verdict"]][0],
                "Confounders": len(r["confounders"]),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    labels = [f"{a[0]}  vs  {b[0]}" for a, b in pairs]
    sel = st.selectbox("Show details for", labels)
    a, b = pairs[labels.index(sel)]
else:
    a, b = pairs[0]

r = run(a, b)
label, box = VERDICT_UI[r["verdict"]]
box(f"**{label}** — {r['a']} vs {r['b']}")

c1, c2 = st.columns([1, 1])
with c1:
    st.markdown("**Rule trace** (evaluated in order; gates stop evaluation)")
    # The rows that decide the verdict are the failing ones; they carry the emphasis.
    trace = "".join(
        f'<tr class="{"" if x["passed"] else "drives"}"><td>{x["rule"]}</td>'
        f"<td>{html.escape(str(x['name']))}<br><small>{html.escape(str(x['kind']))}</small></td>"
        f"<td>{'pass' if x['passed'] else '<b>FAIL</b>'}</td><td>{html.escape(str(x['detail']))}</td></tr>"
        for x in r["rules"]
    )
    st.markdown(
        '<table class="ember-diff"><thead><tr><th>#</th><th>Rule</th><th>Result</th><th>Detail</th>'
        f"</tr></thead><tbody>{trace}</tbody></table>",
        unsafe_allow_html=True,
    )
    with st.expander("Rule trace as a sortable table"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "#": x["rule"],
                        "Rule": x["name"],
                        "Type": x["kind"],
                        "Result": "pass" if x["passed"] else "FAIL",
                        "Detail": x["detail"],
                    }
                    for x in r["rules"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    st.markdown("**Confounders**")
    if r["confounders"]:
        for c in r["confounders"]:
            st.markdown(f"- {c}")
    else:
        st.write("None found by the rules.")
    st.markdown("**Normalizations applied**")
    if r["normalizations_applied"]:
        for n in r["normalizations_applied"]:
            st.markdown(f"- {n}")
    else:
        st.write("None needed.")
with c2:
    st.markdown("**Shared conditions**")
    if r["shared_conditions"]:
        st.dataframe(pd.DataFrame(r["shared_conditions"]), hide_index=True, width="stretch")
    else:
        st.write("None.")
    st.markdown("**Differing conditions**")
    if r["differing_conditions"]:
        st.dataframe(pd.DataFrame(r["differing_conditions"]), hide_index=True, width="stretch")
    else:
        st.write("None.")
    st.markdown("**Unknown on at least one side** (never guessed)")
    if r["unknown_conditions"]:
        st.dataframe(pd.DataFrame(r["unknown_conditions"]), hide_index=True, width="stretch")
    else:
        st.write("None.")

st.caption(
    "Rules (spec §10.7): 1 same canonical quantity · 2 units convertible · 3 same value kind · 4 same context "
    "(burner O₂ is never cabin O₂) · 5 hardware/scale confounders · 6 same regime. Rules 1, 2 and 4 are gates; "
    "3, 5 and 6 add caveats. Validation: a labeled pair set lives in ember/eval/comparelab_pairs.yaml (starter set; "
    "the target is 60 pairs with a second annotator and a false-'comparable' rate of 0)."
)
