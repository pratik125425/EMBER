"""Overview: the Evidence Sky Atlas first, then how to read it and where to go. Numbers are live."""

import streamlit as st

from ember.ui.atlas import atlas, sky
from ember.ui.badges import legend_markdown
from ember.ui.scenario import scenario_sidebar

scenario = scenario_sidebar()
atlas(scenario)
counts = sky()["counts"]

a, b, _ = st.columns([1.5, 1.5, 1.6], vertical_alignment="center")
with a:
    st.page_link(
        "pages/0_Demo.py", label="Take the three-minute guided demo", icon=":material/slideshow:"
    )
with b:
    st.page_link(
        "pages/1_Ask.py", label="See the full ranking for this point", icon=":material/search:"
    )

st.subheader("Reading the plate")
st.markdown(
    """
<div class="ember-reading">
  <div><h4>Why the sky matters</h4><p><b>Flames behave differently without gravity.</b> On Earth hot
  gas rises and pulls in fresh air; in orbit it doesn't, so a flame only gets oxygen from airflow such
  as ventilation fans. That changes how materials ignite, spread and go out.</p></div>
  <div><h4>Where habitats want to go</h4><p><b>Exploration habitats plan more oxygen at lower
  pressure.</b> NASA's Exploration Atmosphere is 34% O₂ at 56.5 kPa (8.2 psia), against about 21% at
  101.3 kPa on Earth. The gold marks on the plate are these targets.</p></div>
  <div><h4>What dark sky means</h4><p><b>Not every atmosphere has been tested.</b> Dark sky is where
  no NASA test sits. The further your reticle is from a star, the more you would be extrapolating,
  and EMBER says by how much. PSI holds no tests at Moon or Mars gravity.</p></div>
</div>
""",
    unsafe_allow_html=True,
)

st.subheader("How EMBER answers")
st.markdown(
    """
<ol class="ember-steps">
  <li><div class="t">Describe the atmosphere</div>
    <div class="d">Drag the reticle, use the sidebar, or ask a plain question on the Ask page.</div></li>
  <li><div class="t">Measure the distance</div>
    <div class="d">Every record gets a transfer distance D from your scenario, weighted by NASA's
    published flame-spread correlations.</div></li>
  <li><div class="t">Check what transfers</div>
    <div class="d">Rule-gated comparisons, cited summaries and a flag on anything unknown.</div></li>
  <li><div class="t">Map what is missing</div>
    <div class="d">Coverage per gravity regime shows the dark sky nobody has tested.</div></li>
</ol>
""",
    unsafe_allow_html=True,
)

st.subheader("Index of plates")
INDEX = [
    (
        "pages/1_Ask.py",
        "Ask",
        "search",
        "Has NASA tested anything like my habitat?",
        "The ranked evidence, D and exp(D) per record, rank stability and a cite-or-drop summary.",
    ),
    (
        "pages/2_Evidence_Map.py",
        "Evidence map",
        "scatter_plot",
        "Where do the tests sit next to my scenario?",
        "This plate in full detail: ranges, phenomena, gravity and every record on click.",
    ),
    (
        "pages/3_Compare.py",
        "Compare",
        "compare_arrows",
        "Can these two results be compared fairly?",
        "A rule-gated verdict with the confounders listed in order.",
    ),
    (
        "pages/4_Gaps.py",
        "Gaps",
        "grid_off",
        "What has nobody tested yet?",
        "Coverage per gravity regime, NASA target atmospheres and a downloadable gap report.",
    ),
    (
        "pages/5_Registry.py",
        "Registry",
        "table_view",
        "What data does EMBER use?",
        f"All {counts['records']:,} records with units, status and provenance, exportable.",
    ),
    (
        "pages/7_Sources.py",
        "Sources",
        "menu_book",
        "Where does each number come from?",
        f"{counts['sources']} NASA sources; {counts['mirrored']} of {counts['files']} files "
        "mirrored with SHA-256 checksums.",
    ),
    (
        "pages/6_Validation.py",
        "Validation",
        "fact_check",
        "How well does EMBER work?",
        "Retrieval benchmark, ablations and the adversarial prompt suite. Measured numbers only.",
    ),
]
for path, title, icon, question, text in INDEX:
    st.markdown('<div class="ember-index-row"></div>', unsafe_allow_html=True)
    q, link = st.columns([3, 1.3], vertical_alignment="center")
    with q:
        st.markdown(
            f'<p class="ember-index-q">{question}</p><p class="ember-index-d">{text}</p>',
            unsafe_allow_html=True,
        )
    with link:
        st.page_link(path, label=title, icon=f":material/{icon}:")

left, right = st.columns(2, gap="large")
with left:
    st.subheader("How EMBER decides")
    st.markdown(
        "- **Deterministic ranking.** R = M_φ · M_f · Q · exp(−D); D is an elasticity-weighted log "
        "distance from NASA's published spread correlations (Ruff 2021).\n"
        "- **Unknown stays unknown.** A missing condition makes D a lower bound; nothing is imputed. "
        f"{counts['uncharted']} records stay off the plate for that reason.\n"
        "- **Constrained language model.** It may propose a scenario and write a summary; every "
        "sentence must cite a record, and numbers are checked against it."
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
st.caption(
    "Unfamiliar term? The **Glossary** at the bottom of the sidebar explains each one, and every "
    "page has a **How to read this page** guide under its title."
)
