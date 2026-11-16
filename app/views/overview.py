"""Overview: a full-window, scroll-driven story built around the Evidence Sky Atlas.

Everything visible is one offline component (ember/ui/atlas_frontend). It reports what the visitor
did (reticle moved, gravity picked, page chosen) and Python answers with the engine's ranking.
Numbers are counted live from the registry.
"""

import streamlit as st

from ember.ui.atlas import atlas, sky
from ember.ui.scenario import scenario_sidebar

# The story fills the window: no Streamlit header, padding or sidebar on this page. The sidebar
# scenario still runs (hidden) so every other page opens on the scenario chosen here.
st.markdown(
    """
<style>
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"] { display: none !important; }
[data-testid="stMainBlockContainer"], .block-container { padding: 0 !important; max-width: none !important; }
[data-testid="stMain"] { overflow: hidden; }
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: 0 !important; }
[data-testid="stElementContainer"]:has(> .stMarkdown style) { display: none; }
iframe[title="ember.ui.atlas.ember_atlas"] { display: block; }
</style>
""",
    unsafe_allow_html=True,
)

scenario = scenario_sidebar()
counts = sky()["counts"]
PAGES = [
    {
        "key": "ask",
        "title": "Ask",
        "question": "Has NASA tested anything like my habitat?",
        "text": "Ranked evidence with distances, rank stability and a cited summary.",
    },
    {
        "key": "evidence-map",
        "title": "Evidence map",
        "question": "Where does every test sit?",
        "text": "The full chart: ranges, phenomena, gravity and every record on click.",
    },
    {
        "key": "compare",
        "title": "Compare",
        "question": "Can these two results be compared fairly?",
        "text": "A rule-gated verdict with the confounders listed in order.",
    },
    {
        "key": "gaps",
        "title": "Gaps",
        "question": "What has nobody tested yet?",
        "text": "Coverage per gravity regime and a downloadable gap report.",
    },
    {
        "key": "registry",
        "title": "Registry",
        "question": "What data does EMBER use?",
        "text": f"All {counts['records']:,} records with units, status and provenance.",
    },
    {
        "key": "sources",
        "title": "Sources",
        "question": "Where does each number come from?",
        "text": f"{counts['sources']} NASA sources; {counts['mirrored']} of {counts['files']} files "
        "mirrored with SHA-256 checks.",
    },
    {
        "key": "validation",
        "title": "Validation",
        "question": "How well does EMBER work?",
        "text": "Retrieval benchmark, ablations and the adversarial prompt suite.",
    },
    {
        "key": "demo",
        "title": "Guided demo",
        "question": "New here? Take the three-minute tour.",
        "text": "Four steps through a real lunar-habitat question.",
    },
]

atlas(scenario, PAGES)

target = st.session_state.pop("_atlas_nav", None)
if target:
    st.switch_page(target)
