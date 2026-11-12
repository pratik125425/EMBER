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

# "plate" is the default navy atlas plate (Streamlit dark base); "light" is the white-sky print
# a viewer gets from Streamlit's built-in Light theme.
TOKENS = {
    "light": {
        "ink": "#13234a",
        "ink2": "#3b4a6b",
        "muted": "#56627f",
        "line": "#c9d1e2",
        "card": "#ffffff",
        "wash": "#eef1f7",
        "plate": "#f7f8fb",
        "accent": "#c4501c",
        "accent_ink": "#ffffff",
        "accent_wash": "#fbe2d4",
        "gold": "#8a6a1c",
    },
    "dark": {
        "ink": "#efe9da",
        "ink2": "#b9c3dc",
        "muted": "#8d9bbd",
        "line": "#2c406c",
        "card": "#152649",
        "wash": "#0d1830",
        "plate": "#12213f",
        "accent": "#ff8a4c",
        "accent_ink": "#12213f",
        "accent_wash": "#5a3424",
        "gold": "#e3c46e",
    },
}

SERIF = '"Libre Caslon Text", Georgia, serif'
DISPLAY = '"Libre Caslon Display", "Libre Caslon Text", Georgia, serif'

CSS = (
    """
<style>
:root {{ --e-ink:{ink}; --e-ink2:{ink2}; --e-muted:{muted}; --e-line:{line}; --e-card:{card};
  --e-wash:{wash}; --e-plate:{plate}; --e-accent:{accent}; --e-accent-ink:{accent_ink};
  --e-accent-wash:{accent_wash}; --e-gold:{gold};
  --e-serif:"""
    + SERIF.replace("{", "{{")
    + """; --e-display:"""
    + DISPLAY
    + """;
  --e-ease: cubic-bezier(0.23, 1, 0.32, 1); }}
/* Browser surfaces carry the plate: selection, caret, link underlines, scrollbars */
::selection {{ background: var(--e-accent-wash); color: var(--e-ink); }}
input, textarea {{ caret-color: var(--e-accent); }}
[data-testid="stMarkdownContainer"] a {{ text-underline-offset: .2em; text-decoration-thickness: 1px; }}
html {{ scrollbar-color: var(--e-line) transparent; }}
/* Page frame and rhythm: more space above a heading than below it */
.block-container {{ padding-top: 2rem; padding-bottom: 4rem; max-width: 1360px; }}
h1 {{ letter-spacing: -0.012em; line-height: 1.1 !important; font-weight: 500 !important; }}
h1, h2, h3 {{ text-wrap: balance; }}
h2, h3 {{ letter-spacing: -0.004em; }}
[data-testid="stHeadingWithActionElements"] h2 {{ padding-top: 2rem; padding-bottom: .35rem; }}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{ line-height: 1.6;
  text-wrap: pretty; }}
[data-testid="stSliderThumbValue"] p, [data-testid="stSliderTickBar"] p {{ white-space: nowrap; text-wrap: nowrap; }}
/* Numbers line up wherever they are compared */
[data-testid="stMetricValue"], [data-testid="stDataFrame"], [data-testid="stTable"],
[data-testid="stCaptionContainer"] {{ font-variant-numeric: tabular-nums; }}
/* Keyboard focus: one ember ring */
a:focus-visible, button:focus-visible, summary:focus-visible, [data-testid="stPageLink"] a:focus-visible,
iframe:focus-visible {{ outline: 2px solid var(--e-accent); outline-offset: 2px; border-radius: 2px; }}
/* Primary action: ember fill needs plate-coloured text to stay legible */
button[data-testid="stBaseButton-primary"], [data-testid="stDownloadButton"] button[kind="primary"] {{
  color: var(--e-accent-ink) !important; font-weight: 600; }}
button[data-testid="stBaseButton-primary"] p {{ color: var(--e-accent-ink) !important; }}
/* Press feedback: controls settle under the pointer (transform only) */
@media (prefers-reduced-motion: no-preference) {{
  .stButton button, .stDownloadButton button, .stFormSubmitButton button,
  [data-testid="stPageLink"] a {{ transition: transform 160ms var(--e-ease), background-color 160ms var(--e-ease); }}
  .stButton button:active, .stDownloadButton button:active, .stFormSubmitButton button:active,
  [data-testid="stPageLink"] a:active {{ transform: scale(0.97); }}
}}
.ember-lede {{ color: var(--e-ink2); font-family: var(--e-serif); font-size: 1.12rem; line-height: 1.55;
  max-width: 58rem; margin: -.1rem 0 1.4rem 0; }}
.ember-lede b {{ color: var(--e-ink); font-weight: 600; }}
.ember-rule {{ border: 0; border-top: 1px solid var(--e-line); margin: .2rem 0 1.4rem 0; }}
/* Metric tiles read as plate-margin entries: a top hairline, label above, value below */
[data-testid="stMetric"] {{ background: transparent; border: 0; border-top: 1px solid var(--e-line);
  border-radius: 0; padding: .7rem 0 .2rem; }}
[data-testid="stMetricValue"] {{ font-size: 1.7rem; line-height: 1.15; letter-spacing: -0.01em; }}
[data-testid="stMetricLabel"] p {{ color: var(--e-ink2); font-size: .8rem; }}
/* Bordered containers: hairline frames on the plate, no card fill */
[data-testid="stVerticalBlockBorderWrapper"] {{ background: transparent; }}
[data-testid="stExpander"] details {{ border-color: var(--e-line); background: transparent; }}
[data-testid="stExpander"] summary p {{ font-weight: 500; }}
/* Page links read as index entries */
[data-testid="stPageLink"] a p {{ font-weight: 600; font-size: 1rem; }}
/* Callouts as margin notes on the plate: wash, ivory text, one hairline rule. Gold stays for
   NASA targets; errors keep the ember rule so they still stand apart. */
[data-testid="stAlertContainer"] {{ background: var(--e-wash) !important; color: var(--e-ink) !important;
  border: 0; border-left: 2px solid var(--e-ink2); border-radius: 0; }}
[data-testid="stAlertContainer"] p, [data-testid="stAlertContainer"] li {{ color: var(--e-ink) !important; }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{ border-left-color: var(--e-accent); }}
@keyframes ember-reveal {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@media (prefers-reduced-motion: no-preference) {{
  [data-testid="stExpander"] details[open] > :not(summary) {{
    animation: ember-reveal 180ms var(--e-ease); }}
}}
@media (prefers-contrast: more) {{
  :root {{ --e-line: var(--e-ink2); --e-muted: var(--e-ink2); }}
  .ember-empty {{ border-style: solid; }}
}}
/* Overview, below the plate: the plate legend and the index of plates */
.ember-atlas-actions {{ margin: .2rem 0 .6rem; }}
.ember-reading {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.2rem 2.4rem;
  margin: .2rem 0 .4rem; }}
@media (max-width: 900px) {{ .ember-reading {{ grid-template-columns: 1fr; }} }}
.ember-reading h4 {{ font-family: var(--e-serif); font-style: italic; font-weight: 500; font-size: 1.15rem;
  color: var(--e-ink); margin: 0 0 .35rem; padding: 0; }}
.ember-reading p {{ font-size: .95rem; line-height: 1.6; color: var(--e-ink2); margin: 0; max-width: 34rem; }}
.ember-reading b {{ color: var(--e-ink); font-weight: 600; }}
.ember-steps {{ list-style: none; counter-reset: step; display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 1rem 1.6rem; margin: .4rem 0 1rem; padding: 0; }}
@media (max-width: 1180px) {{ .ember-steps {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 520px) {{ .ember-steps {{ grid-template-columns: 1fr; }} }}
.ember-steps li {{ border-top: 1px solid var(--e-line); padding: .7rem 0 0; margin: 0; }}
.ember-steps li::before {{ counter-increment: step; content: counter(step); display: block;
  font-family: var(--e-display); font-size: 2rem; line-height: 1; color: var(--e-ink2);
  margin-bottom: .45rem; font-variant-numeric: lining-nums; }}
.ember-steps .t {{ font-weight: 600; color: var(--e-ink); margin: 0 0 .2rem; }}
.ember-steps .d {{ font-size: .9rem; color: var(--e-ink2); line-height: 1.5; }}
.ember-index-q {{ font-family: var(--e-serif); font-style: italic; font-size: 1.12rem; line-height: 1.4;
  color: var(--e-ink); margin: .15rem 0 0; text-wrap: balance; }}
.ember-index-row {{ border-top: 1px solid var(--e-line); }}
.ember-index-d {{ font-size: .88rem; color: var(--e-ink2); line-height: 1.5; margin: .1rem 0 .5rem; }}
/* Plain-language help: glossary terms inside page guides, and the next-steps footer */
.ember-terms-title, .ember-next-title {{ font-weight: 600; color: var(--e-ink); margin: .6rem 0 .3rem; }}
.ember-next-title {{ margin-top: 2.6rem; padding-top: 1.2rem; border-top: 1px solid var(--e-line);
  font-family: var(--e-serif); font-style: italic; font-weight: 500; font-size: 1.15rem; }}
.ember-terms {{ display: grid; grid-template-columns: minmax(9rem, max-content) 1fr; gap: .35rem 1.2rem;
  margin: 0; font-size: .9rem; line-height: 1.5; }}
.ember-terms dt {{ font-weight: 600; color: var(--e-ink); }}
.ember-terms dd {{ margin: 0; color: var(--e-ink2); }}
@media (max-width: 640px) {{ .ember-terms {{ grid-template-columns: 1fr; gap: 0 0; }}
  .ember-terms dd {{ margin-bottom: .5rem; }} .block-container {{ padding-top: 1.2rem; }} }}
/* Empty / pending states */
.ember-empty {{ border: 1px dashed var(--e-line); border-radius: 2px; padding: 1.4rem 1.6rem;
  background: var(--e-wash); color: var(--e-ink2); }}
.ember-empty b {{ color: var(--e-ink); display: block; margin-bottom: .25rem; }}
/* Sidebar */
[data-testid="stSidebarNavSeparator"] {{ margin: .3rem 0; }}
[data-testid="stSidebar"] h2 {{ font-size: 1.05rem !important; font-style: italic; }}
/* Footer */
.ember-footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--e-line);
  font-size: .8rem; color: var(--e-muted); }}
</style>
"""
)


def persist_scenario() -> None:
    ss = st.session_state
    for k in PERSISTENT_KEYS:
        if k in ss:
            ss[k] = ss[k]


def tokens() -> dict[str, str]:
    from ember.ui.theme import is_dark

    return TOKENS["dark" if is_dark() else "light"]


def inject_css() -> None:
    st.markdown(CSS.format(**tokens()), unsafe_allow_html=True)


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
