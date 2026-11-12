"""Overview: what EMBER does, where to start, what it will not do. Numbers are counted live."""

import streamlit as st

from ember.export import tables
from ember.registry import load_registry
from ember.ui.badges import legend_markdown, sidebar_legend


@st.cache_resource
def _counts():
    reg = load_registry()
    t = tables(reg)
    ev, files = t["evidence"], t["files"]
    return {
        "records": len(ev),
        "investigations": ev["investigation"].nunique(),
        "sources": len(t["sources"]),
        "mirrored": int(files["sha256"].notna().sum()),
        "files": len(files),
        "o2_known": float(ev["x_o2_ambient_usable"].mean()),
    }


c = _counts()
sidebar_legend()

st.markdown(
    f"""
<div class="ember-hero">
  <div class="kicker">NASA Space Apps Challenge 2026 · Flame in Freefall</div>
  <h1 class="title">EMBER</h1>
  <div class="expansion">Evidence-Mapped Bounds for Exploration fire Risk</div>
  <p class="pitch">Give EMBER a habitat's oxygen, pressure and airflow. It shows which NASA fire
  experiments apply, how far you are extrapolating from them, and what nobody has tested yet.</p>
  <div class="facts">
    <div class="fact"><b>{c["records"]:,}</b><span>evidence records</span></div>
    <div class="fact"><b>{c["investigations"]}</b><span>NASA investigations</span></div>
    <div class="fact"><b>{c["sources"]}</b><span>cited sources</span></div>
    <div class="fact"><b>{c["mirrored"]} of {c["files"]}</b><span>files mirrored, SHA-256 checked</span></div>
    <div class="fact"><b>{c["o2_known"]:.0%}</b><span>records with ambient O₂ known</span></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

with st.container(border=True):
    a, b = st.columns([3, 1], vertical_alignment="center")
    a.markdown("**New here? Start with the guided demo.**")
    a.caption(
        "Nine steps: a lunar-habitat question, the ranked evidence, a comparison, the cited summary, "
        "the gap map and the honest answer. About three minutes."
    )
    b.page_link("pages/0_Demo.py", label="Open the guided demo", icon=":material/arrow_forward:")

st.subheader("How it works")
st.markdown(
    """
<div class="ember-steps">
  <div class="ember-step"><div class="n">1</div><div class="t">Describe the atmosphere</div>
    <div class="d">Oxygen, pressure, airflow, gravity and fuel, in the sidebar or as a plain question.</div></div>
  <div class="ember-step"><div class="n">2</div><div class="t">Rank the NASA evidence</div>
    <div class="d">Every record gets a transfer distance D from your scenario. Smaller D, closer match.</div></div>
  <div class="ember-step"><div class="n">3</div><div class="t">Check what transfers</div>
    <div class="d">Rule-gated comparisons, cited summaries and flags for anything unknown.</div></div>
  <div class="ember-step"><div class="n">4</div><div class="t">See what is missing</div>
    <div class="d">Coverage maps per gravity regime show what nobody has tested.</div></div>
</div>
""",
    unsafe_allow_html=True,
)

st.subheader("Analyse a scenario")
cards = [
    (
        "pages/1_Ask.py",
        "Ask",
        "search",
        "Ask in plain language or set the sliders. Get the ranked NASA "
        "evidence, the transfer distance D and why each record ranks where it does.",
    ),
    (
        "pages/2_Evidence_Map.py",
        "Evidence map",
        "scatter_plot",
        "Every test in oxygen–pressure space, with your "
        "scenario on top. Click a test to see its conditions.",
    ),
    (
        "pages/3_Compare.py",
        "Compare",
        "compare_arrows",
        "Can two results be put side by side? A rule-gated verdict with the confounders listed.",
    ),
    (
        "pages/4_Gaps.py",
        "Gaps",
        "grid_off",
        "What nobody has tested: coverage per gravity regime, NASA target "
        "atmospheres and a downloadable gap report.",
    ),
]
cols = st.columns(4)
for col, (path, title, icon, text) in zip(cols, cards, strict=True):
    with col.container(border=True, height="stretch"):
        st.page_link(path, label=title, icon=f":material/{icon}:")
        st.caption(text)

st.subheader("Data and trust")
cols = st.columns(3)
for col, (path, title, icon, text) in zip(
    cols,
    [
        (
            "pages/5_Registry.py",
            "Registry",
            "table_view",
            "All evidence with units and provenance. Export CSV/Parquet with a data dictionary.",
        ),
        (
            "pages/7_Sources.py",
            "Sources",
            "menu_book",
            "Every NASA source: DOI, PSI status, mirrored files "
            "with checksums, and the records citing it.",
        ),
        (
            "pages/6_Validation.py",
            "Validation",
            "fact_check",
            "Retrieval benchmark, rank stability and the "
            "adversarial prompt suite. Measured numbers only.",
        ),
    ],
    strict=True,
):
    with col.container(border=True, height="stretch"):
        st.page_link(path, label=title, icon=f":material/{icon}:")
        st.caption(text)

left, right = st.columns(2)
with left:
    st.subheader("How EMBER decides")
    st.markdown(
        "- **Deterministic ranking.** R = M_φ · M_f · Q · exp(−D); D is an elasticity-weighted log distance "
        "from NASA's published spread correlations (Ruff 2021).\n"
        "- **Unknown stays unknown.** A missing condition makes D a lower bound; nothing is imputed. "
        f"Ambient O₂ is known for {c['o2_known']:.0%} of records.\n"
        "- **Constrained language model.** It may propose a scenario and write a summary; every sentence "
        "must cite a record, and numbers are checked against it."
    )
with right:
    st.subheader("What EMBER will not do")
    st.markdown(
        "- Call a material or atmosphere safe.\n"
        "- Report partial-gravity results from PSI: there are none. Lunar and Martian scenarios are "
        "brackets from µg and 1-g tests, flagged.\n"
        "- Treat CFI-G's 85% O₂ as a cabin atmosphere: it is burner-side oxidizer flow."
    )

with st.expander("Badge legend"):
    st.markdown(legend_markdown())
