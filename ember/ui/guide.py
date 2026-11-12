"""Plain-language help for readers new to spacecraft fire safety.

Everything here is optional reading that sits beside the technical content and never replaces it:
a glossary (sidebar, every page), a collapsed "how to read this page" guide under each page title,
and "where to go next" links at the bottom of each page. Definitions follow the build spec's
science primer (§3) and glossary (Appendix C)."""

from __future__ import annotations

import html

import streamlit as st

# term -> plain-language definition. Order is the order a newcomer meets them.
GLOSSARY: dict[str, str] = {
    "Scenario": "The atmosphere you describe: oxygen level, pressure, airflow, gravity and the kind "
    "of material that might burn. Set it in the sidebar or by asking a question.",
    "Evidence record": "One NASA fire experiment result (or one set of test conditions) in EMBER's "
    "registry, with its source and a status for every condition.",
    "Microgravity (µg)": "The near-weightless conditions on an orbiting spacecraft such as the ISS. "
    "1-g means Earth gravity.",
    "Partial gravity": "Moon (0.166 g) or Mars (0.38 g). NASA's PSI archive has no fire experiments at "
    "these gravities, so EMBER can only bracket them between microgravity and Earth results.",
    "Oxygen %, X_O₂": "The share of the air that is oxygen. Earth air is about 21%. Some planned "
    "exploration habitats use about 34% at lower pressure.",
    "Pressure (kPa, psia)": "Total air pressure. Sea level is 101.3 kPa (14.7 psia). NASA's "
    "Exploration Atmosphere is 56.5 kPa (8.2 psia).",
    "ppO₂": "Oxygen partial pressure: oxygen % × total pressure. It tells you how much oxygen is "
    "actually available to a flame.",
    "Airflow (cm/s)": "How fast air moves past the material, for example from ventilation fans. "
    "Without gravity, hot gas does not rise, so this flow is what feeds a flame fresh oxygen.",
    "Opposed / concurrent flow": "Opposed: the flame spreads into the oncoming air. Concurrent: the "
    "flame spreads in the same direction as the air.",
    "Limiting oxygen concentration (LOC)": "The lowest oxygen level at which a material keeps burning.",
    "Transfer distance D": "How far a NASA test's conditions are from your scenario, weighted by how "
    "strongly each condition affects the flame. D = 0 means your scenario sits inside the tested "
    "range; larger D means more extrapolation.",
    "exp(D)": "The largest change in the flame's response that NASA's correlations imply over that "
    "distance. Above about 2.7× EMBER flags the record as beyond the tested envelope.",
    "Relevance R": "EMBER's ranking score. It combines how close the conditions are (D) with whether "
    "the phenomenon and fuel match and how detailed the source data is (a per-test table counts "
    "more than a paper-only value). Higher R ranks first.",
    "Lower bound": "Some of the record's conditions are unknown, so its true distance could be larger "
    "than shown. Unknown values are never filled in.",
    "Stable": "The record stayed in the top 5 in at least 80% of Monte Carlo runs, where EMBER "
    "jiggles its weights to see whether the ranking holds up.",
    "Coverage / gap": "Coverage shows where in oxygen–pressure space NASA has tested. A gap is a "
    "region nobody has tested.",
    "Comparable": "Whether two results can fairly be put side by side. EMBER checks rules in order "
    "(same quantity, units, hardware, enclosure and so on) and lists anything that gets in the way.",
    "PSI": "NASA's Physical Sciences Informatics archive, where most of EMBER's experiments come from.",
    "Cite-or-drop": "Every sentence in a generated summary must cite a record. Sentences without a "
    "valid citation are removed, and the count of removed sentences is shown.",
}

# Keyed by page title (titles are unique). Each guide: one plain sentence, the reading steps in order,
# the glossary terms that page leans on, and where a reader usually goes next.
PAGE_GUIDES: dict[str, dict] = {
    "Guided demo": {
        "plain": "A short tour that answers one real question, a lunar habitat at 34% oxygen, step "
        "by step. It's the best place to start if this topic is new to you.",
        "steps": [
            "Read the question at the top of each step.",
            "Look at the numbers and charts; each step says what to notice.",
            "Use Next to move on. You can leave at any point and explore on your own.",
        ],
        "terms": ["Scenario", "Partial gravity", "Transfer distance D"],
        "next": [
            ("pages/1_Ask.py", "Ask", "Try your own question"),
            ("pages/2_Evidence_Map.py", "Evidence map", "See all the tests on one chart"),
        ],
    },
    "Ask": {
        "plain": "Describe an atmosphere and EMBER lists the NASA experiments closest to it, with how "
        "much you would be extrapolating from each one.",
        "steps": [
            "Type a question, or set oxygen, pressure and gravity in the sidebar.",
            "Check the scenario line under the title: it is what EMBER actually searched for.",
            "Read the ranked list from the top. Smaller D means a closer match; badges warn about "
            "unknown conditions or gravity gaps.",
            "Open the summary and record details for the cited sources behind each result.",
        ],
        "terms": ["Scenario", "Transfer distance D", "Relevance R", "Lower bound", "Stable"],
        "next": [
            ("pages/2_Evidence_Map.py", "Evidence map", "See where these tests sit"),
            ("pages/3_Compare.py", "Compare", "Check if two results can be compared"),
            ("pages/4_Gaps.py", "Gaps", "See what has not been tested"),
        ],
    },
    "Evidence map": {
        "plain": "A chart of every NASA test by oxygen level and pressure. Your scenario is the star; "
        "the closer a test is to the star, the more directly it applies.",
        "steps": [
            "Find the star: that is your scenario. Move the sidebar sliders and it moves.",
            "Dots and boxes are tests; colour shows what was measured, shape shows the gravity.",
            "Shaded rectangles are NASA's target habitat atmospheres.",
            "Click a test to see its conditions and source.",
        ],
        "terms": ["Oxygen %, X_O₂", "Pressure (kPa, psia)", "ppO₂", "Microgravity (µg)"],
        "next": [
            ("pages/1_Ask.py", "Ask", "Rank these tests for your scenario"),
            ("pages/4_Gaps.py", "Gaps", "See the empty regions of this chart"),
        ],
    },
    "Compare": {
        "plain": "Pick two results and EMBER says whether they can fairly be compared, and if not, "
        "what gets in the way (different hardware, units, enclosure size and so on).",
        "steps": [
            "Choose two or more records or measurements in the box.",
            "Read the coloured verdict: comparable, comparable with caveats, or not comparable.",
            "The rule trace shows each check in order; the first one that fails decides.",
            "Shared and differing conditions are listed side by side below.",
        ],
        "terms": ["Comparable", "Evidence record", "Opposed / concurrent flow"],
        "next": [
            ("pages/1_Ask.py", "Ask", "Find records for your scenario"),
            ("pages/5_Registry.py", "Registry", "Look up any record in full"),
        ],
    },
    "Gaps": {
        "plain": "Where has nobody tested? Each map shows which oxygen and pressure combinations "
        "NASA has covered at each gravity, and which are empty.",
        "steps": [
            "Each panel is one gravity level. Hatched panels have no data at all.",
            "Darker cells are better covered; empty cells are gaps.",
            "Priority cells are poorly covered regions, weighted up near NASA's planned habitat "
            "atmospheres: a rough guide to where new tests would help most.",
            "Download the gap report for a written summary.",
        ],
        "terms": ["Coverage / gap", "Partial gravity", "Microgravity (µg)"],
        "next": [
            ("pages/2_Evidence_Map.py", "Evidence map", "See the tests behind the coverage"),
            ("pages/6_Validation.py", "Validation", "See how EMBER was tested"),
        ],
    },
    "Registry": {
        "plain": "The full list of NASA evidence EMBER uses, with every value's units and source. If a "
        "value was never published, it says unknown.",
        "steps": [
            "Use the filters to narrow by investigation, phenomenon, gravity or fuel.",
            "The tiles show how many records have each condition known.",
            "Scroll the table; status columns say whether each value is known or unknown.",
            "Export the table or read the data dictionary for what each column means.",
        ],
        "terms": ["Evidence record", "Lower bound", "PSI"],
        "next": [
            ("pages/7_Sources.py", "Sources", "See where each record comes from"),
            ("pages/1_Ask.py", "Ask", "Rank these records for a scenario"),
        ],
    },
    "Validation": {
        "plain": "How well does EMBER work? This page reports measured test results only; anything "
        "not yet run says pending.",
        "steps": [
            "Ranking quality compares EMBER with plain text search and a simpler score.",
            "Ablations show what happens when parts of EMBER are switched off.",
            "Adversarial prompts show whether the summary checker catches false statements.",
        ],
        "terms": ["Relevance R", "Cite-or-drop", "Stable"],
        "next": [
            ("pages/7_Sources.py", "Sources", "Check the sources behind the data"),
            ("pages/0_Demo.py", "Guided demo", "See EMBER answer a real question"),
        ],
    },
    "Sources": {
        "plain": "Every NASA document and data file behind the registry, with links, checksums and "
        "which records cite it.",
        "steps": [
            "The tiles count sources, PSI membership and mirrored files.",
            "Pick a source below to see its files and the records that cite it.",
            "A checksum proves the local file matches what was downloaded.",
        ],
        "terms": ["PSI", "Evidence record"],
        "next": [
            ("pages/5_Registry.py", "Registry", "See the records these sources support"),
            ("pages/6_Validation.py", "Validation", "See how EMBER was tested"),
        ],
    },
}

# url_path (as given in app/Home.py) -> page title, for the next-steps footer.
URL_TO_TITLE = {
    "demo": "Guided demo",
    "ask": "Ask",
    "evidence-map": "Evidence map",
    "compare": "Compare",
    "gaps": "Gaps",
    "registry": "Registry",
    "validation": "Validation",
    "sources": "Sources",
}


def page_guide(title: str) -> None:
    """Collapsed 'how to read this page' help under the page title. No-op for unknown titles."""
    g = PAGE_GUIDES.get(title)
    if not g:
        return
    with st.expander("New to this? How to read this page", icon=":material/help:"):
        st.markdown(g["plain"])
        st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(g["steps"], 1)))
        terms = [t for t in g["terms"] if t in GLOSSARY]
        if terms:
            items = "".join(
                f"<dt>{html.escape(t)}</dt><dd>{html.escape(GLOSSARY[t])}</dd>" for t in terms
            )
            st.markdown(
                f'<div class="ember-terms-title">Terms on this page</div>'
                f'<dl class="ember-terms">{items}</dl>',
                unsafe_allow_html=True,
            )


def next_steps(url_path: str) -> None:
    """'Where to go next' links at the bottom of a page, so no page is a dead end."""
    g = PAGE_GUIDES.get(URL_TO_TITLE.get(url_path, ""))
    if not g:
        return
    st.markdown('<div class="ember-next-title">Where to go next</div>', unsafe_allow_html=True)
    cols = st.columns(len(g["next"]))
    for col, (path, label, why) in zip(cols, g["next"], strict=True):
        with col:
            st.page_link(path, label=label, icon=":material/arrow_forward:")
            st.caption(why)


def sidebar_glossary() -> None:
    """Every term, in plain language, one click away on every page."""
    with st.sidebar.expander("Glossary", icon=":material/menu_book:"):
        st.markdown("\n\n".join(f"**{t}.** {d}" for t, d in GLOSSARY.items()))
