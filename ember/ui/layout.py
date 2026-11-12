"""Shared page chrome: navigation map, CSS, page header, scenario persistence across pages."""

from __future__ import annotations

import html
import re

import streamlit as st

# Widget keys of the shared scenario. Streamlit drops a widget's state on a page that does not
# render it; re-assigning them on every run keeps the scenario when you visit Registry/Sources.
PERSISTENT_KEYS = (
    "preset",
    "x_o2_pct",
    "p_unit",
    "p_kpa",
    "p_psi",
    "u_specified",
    "u_cms",
    "gravity_label",
    "phenomenon",
    "fuel_class",
    "fuel_name",
    "demo_step",
)

TOKENS = {
    "light": {
        "ink": "#0b0b0b",
        "ink2": "#52514e",
        "muted": "#6b6964",
        "line": "#e1e0d9",
        "card": "#ffffff",
        "wash": "#f3f2ee",
        "accent": "#6250d6",
        "accent_wash": "#efedfb",
    },
    "dark": {
        "ink": "#f0efec",
        "ink2": "#c3c2b7",
        "muted": "#9a9890",
        "line": "#383835",
        "card": "#222221",
        "wash": "#242423",
        "accent": "#9085e9",
        "accent_wash": "#2a2740",
    },
}

CSS = """
<style>
:root {{ --e-ink:{ink}; --e-ink2:{ink2}; --e-muted:{muted}; --e-line:{line}; --e-card:{card};
  --e-wash:{wash}; --e-accent:{accent}; --e-accent-wash:{accent_wash}; }}
/* Browser surfaces carry the palette too: selection, caret, link underlines, scrollbars */
::selection {{ background: var(--e-accent-wash); color: var(--e-ink); }}
input, textarea {{ caret-color: var(--e-accent); }}
[data-testid="stMarkdownContainer"] a {{ text-underline-offset: .18em; text-decoration-thickness: 1px; }}
html {{ scrollbar-color: var(--e-line) transparent; }}
/* Page frame and rhythm */
.block-container {{ padding-top: 2.4rem; padding-bottom: 4rem; max-width: 1360px; }}
h1 {{ letter-spacing: -0.015em; line-height: 1.15 !important; }}
h1, h2, h3 {{ text-wrap: balance; }}
h2, h3 {{ letter-spacing: -0.005em; }}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{ line-height: 1.6;
  text-wrap: pretty; }}
/* Numbers line up in columns wherever they are compared */
[data-testid="stMetricValue"], [data-testid="stDataFrame"], [data-testid="stTable"] {{
  font-variant-numeric: tabular-nums; }}
/* Keyboard focus: one visible accent ring on links, buttons and page links */
a:focus-visible, button:focus-visible, summary:focus-visible, [data-testid="stPageLink"] a:focus-visible {{
  outline: 2px solid var(--e-accent); outline-offset: 2px; border-radius: 4px; }}
/* Press feedback: buttons settle slightly under the pointer (transform only, compositor-cheap) */
@media (prefers-reduced-motion: no-preference) {{
  .stButton button, .stDownloadButton button, .stFormSubmitButton button,
  [data-testid="stPageLink"] a {{ transition: transform 160ms cubic-bezier(0.23, 1, 0.32, 1); }}
  .stButton button:active, .stDownloadButton button:active, .stFormSubmitButton button:active,
  [data-testid="stPageLink"] a:active {{ transform: scale(0.97); }}
}}
[data-testid="stHeadingWithActionElements"] h2 {{ padding-top: 1.4rem; }}
.ember-lede {{ color: var(--e-ink2); font-size: 1.05rem; line-height: 1.6; max-width: 60rem;
  margin: -.2rem 0 1.4rem 0; }}
.ember-rule {{ border: 0; border-top: 1px solid var(--e-line); margin: .2rem 0 1.4rem 0; }}
/* Metric tiles read as cards */
[data-testid="stMetric"] {{ background: var(--e-card); border: 1px solid var(--e-line);
  border-radius: 6px; padding: .8rem 1rem; }}
[data-testid="stMetricValue"] {{ font-size: 1.75rem; line-height: 1.15; letter-spacing: -0.01em; }}
[data-testid="stMetricLabel"] p {{ color: var(--e-ink2); font-size: .78rem; letter-spacing: .01em; }}
/* Bordered containers: card surface */
[data-testid="stVerticalBlockBorderWrapper"] {{ background: var(--e-card); }}
/* Page links inside cards read as headings */
[data-testid="stPageLink"] a p {{ font-weight: 600; font-size: 1rem; }}
/* Overview hero */
.ember-hero {{ border: 1px solid var(--e-line); border-radius: 8px; padding: 2.2rem 2.4rem 2rem;
  background: linear-gradient(135deg, var(--e-accent-wash) 0%, var(--e-card) 55%); margin-bottom: 1.4rem; }}
.ember-hero h1.title {{ font-family: "Source Serif", "Source Serif 4", Georgia, serif; font-weight: 600;
  font-size: 3rem; margin: 0 0 .25rem; color: var(--e-ink); letter-spacing: -0.02em; padding: 0; }}
.ember-hero .expansion {{ color: var(--e-muted); font-size: .95rem; margin-bottom: 1rem; }}
.ember-hero .pitch {{ font-family: "Source Serif", "Source Serif 4", Georgia, serif; font-size: 1.35rem;
  line-height: 1.5; color: var(--e-ink); max-width: 52rem; margin: 0 0 1.4rem; }}
.ember-hero .facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: 1.1rem 2rem; border-top: 1px solid var(--e-line); padding-top: 1.1rem; }}
.ember-hero .fact b {{ display: block; font-size: 1.6rem; font-weight: 600; color: var(--e-ink);
  font-variant-numeric: tabular-nums; letter-spacing: -0.01em; line-height: 1.2; }}
.ember-hero .fact span {{ font-size: .8rem; color: var(--e-ink2); line-height: 1.35; display: block; }}
@media (max-width: 640px) {{
  .block-container {{ padding-top: 1.2rem; }}
  .ember-hero {{ padding: 1.4rem 1.2rem 1.2rem; }}
  .ember-hero h1.title {{ font-size: 2.3rem; }}
  .ember-hero .pitch {{ font-size: 1.12rem; }}
}}
/* Numbered "how it works" steps */
.ember-steps {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem 1.4rem;
  margin: .4rem 0 1rem; }}
@media (max-width: 1180px) {{ .ember-steps {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 520px) {{ .ember-steps {{ grid-template-columns: 1fr; }} }}
.ember-step {{ border-left: 1px solid var(--e-line); padding: .1rem 0 .1rem .9rem; }}
.ember-step .n {{ font-family: "Source Serif", "Source Serif 4", Georgia, serif; font-size: 1.35rem;
  font-weight: 600; line-height: 1; color: var(--e-accent); font-variant-numeric: lining-nums; }}
.ember-step .t {{ font-weight: 600; color: var(--e-ink); margin: .4rem 0 .2rem; }}
.ember-step .d {{ font-size: .88rem; color: var(--e-ink2); line-height: 1.5; }}
/* Expanders: revealed content fades in (opacity only, so it stays on the compositor) */
@keyframes ember-reveal {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@media (prefers-reduced-motion: no-preference) {{
  [data-testid="stExpander"] details[open] > :not(summary) {{
    animation: ember-reveal 180ms cubic-bezier(0.23, 1, 0.32, 1); }}
}}
/* Higher contrast on request: hairlines and secondary text step up */
@media (prefers-contrast: more) {{
  :root {{ --e-line: var(--e-ink2); --e-muted: var(--e-ink2); }}
  .ember-empty {{ border-style: solid; }}
}}
/* Overview primer for newcomers: serif reading text, three short paragraphs */
.ember-primer {{ max-width: 46rem; }}
.ember-primer p {{ font-family: "Source Serif", "Source Serif 4", Georgia, serif; font-size: 1.05rem;
  line-height: 1.65; color: var(--e-ink2); margin: 0 0 .9rem; text-wrap: pretty; }}
.ember-primer b {{ color: var(--e-ink); font-weight: 600; }}
.ember-card-q {{ font-weight: 600; color: var(--e-ink); font-size: .95rem; line-height: 1.4;
  margin: -.2rem 0 .1rem; text-wrap: balance; }}
/* Plain-language help: glossary terms inside page guides, and the next-steps footer */
.ember-terms-title, .ember-next-title {{ font-weight: 600; color: var(--e-ink); margin: .6rem 0 .3rem; }}
.ember-next-title {{ margin-top: 2.6rem; padding-top: 1.2rem; border-top: 1px solid var(--e-line); }}
.ember-terms {{ display: grid; grid-template-columns: minmax(9rem, max-content) 1fr; gap: .35rem 1.2rem;
  margin: 0; font-size: .9rem; line-height: 1.5; }}
.ember-terms dt {{ font-weight: 600; color: var(--e-ink); }}
.ember-terms dd {{ margin: 0; color: var(--e-ink2); }}
@media (max-width: 640px) {{ .ember-terms {{ grid-template-columns: 1fr; gap: 0 0; }}
  .ember-terms dd {{ margin-bottom: .5rem; }} }}
/* Empty / pending states */
.ember-empty {{ border: 1px dashed var(--e-line); border-radius: 6px; padding: 1.4rem 1.6rem;
  background: var(--e-wash); color: var(--e-ink2); }}
.ember-empty b {{ color: var(--e-ink); display: block; margin-bottom: .25rem; }}
/* Sidebar */
[data-testid="stSidebarNavSeparator"] {{ margin: .3rem 0; }}
[data-testid="stSidebar"] h2 {{ font-size: 1rem !important; }}
/* Footer */
.ember-footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--e-line);
  font-size: .8rem; color: var(--e-muted); }}
</style>
"""


def persist_scenario() -> None:
    ss = st.session_state
    for k in PERSISTENT_KEYS:
        if k in ss:
            ss[k] = ss[k]


def inject_css() -> None:
    from ember.ui.theme import is_dark

    st.markdown(CSS.format(**TOKENS["dark" if is_dark() else "light"]), unsafe_allow_html=True)


def page_header(title: str, lede: str, section: str | None = None) -> None:
    """Title and a one-sentence purpose line, identical on every page.

    ``section`` is accepted for callers but not drawn: the sidebar already groups pages by section,
    so a label above the title would repeat it."""
    del section
    st.title(title)
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(lede))
    st.markdown(f'<p class="ember-lede">{body}</p>', unsafe_allow_html=True)
    from ember.ui.guide import page_guide

    page_guide(title)


def empty_state(title: str, body: str) -> None:
    """A quiet dashed box for 'nothing here yet' (pending labels, no matches), never a blank area."""
    st.markdown(
        f'<div class="ember-empty"><b>{html.escape(title)}</b>{body}</div>', unsafe_allow_html=True
    )


def footer() -> None:
    st.markdown(
        '<div class="ember-footer">EMBER · NASA Space Apps Challenge 2026 · Data from NASA PSI and '
        "NTRS. EMBER ranks and brackets evidence; it never calls a material or atmosphere safe.</div>",
        unsafe_allow_html=True,
    )
