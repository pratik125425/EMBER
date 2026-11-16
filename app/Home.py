"""EMBER entry point: grouped navigation over every page (run: uv run streamlit run app/Home.py)."""

from pathlib import Path

import streamlit as st

from ember.ui.guide import next_steps, sidebar_glossary
from ember.ui.layout import footer, inject_css, persist_scenario

HERE = Path(__file__).parent

st.set_page_config(page_title="EMBER", page_icon=":material/local_fire_department:", layout="wide")
persist_scenario()
inject_css()


def page(path: str, title: str, icon: str, url: str, **kw) -> st.Page:
    return st.Page(str(HERE / path), title=title, icon=f":material/{icon}:", url_path=url, **kw)


nav = st.navigation(
    {
        "Start": [
            page("views/overview.py", "Overview", "home", "overview", default=True),
            page("pages/0_Demo.py", "Guided demo", "slideshow", "demo"),
        ],
        "Analyse": [
            page("pages/1_Ask.py", "Ask", "search", "ask"),
            page("pages/2_Evidence_Map.py", "Evidence map", "scatter_plot", "evidence-map"),
            page("pages/3_Compare.py", "Compare", "compare_arrows", "compare"),
            page("pages/4_Gaps.py", "Gaps", "grid_off", "gaps"),
        ],
        "Data": [
            page("pages/5_Registry.py", "Registry", "table_view", "registry"),
            page("pages/7_Sources.py", "Sources", "menu_book", "sources"),
        ],
        "Trust": [
            page("pages/6_Validation.py", "Validation", "fact_check", "validation"),
        ],
    }
)
nav.run()
if nav.title != "Overview":  # the overview is one full-window story with its own ending
    next_steps(nav.url_path)
    sidebar_glossary()
    footer()
