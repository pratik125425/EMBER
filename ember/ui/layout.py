"""Shared page chrome: navigation map, CSS, page header, scenario persistence across pages."""

from __future__ import annotations

import html
import re

import streamlit as st

from ember.ui.palette import DARK, LIGHT, RADII

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
    "demo_mode",
)


# Semantic tokens for the CSS below and the overview component, both built from ember/ui/palette.py
# so the Streamlit pages, the overview and the charts share one set of values.
def _tokens(p: dict[str, str]) -> dict[str, str]:
    return {
        **p,
        "card": p["surface2"],
        "plate": p["surface"],
        "deep": p["canvas"],
        "radius_xl": RADII["xl"],
        "radius_lg": RADII["lg"],
        "radius_md": RADII["md"],
    }


TOKENS = {"light": {**_tokens(LIGHT), "base": "light"}, "dark": {**_tokens(DARK), "base": "dark"}}

SERIF = '"Libre Caslon Text", Georgia, serif'
DISPLAY = '"Libre Caslon Display", "Libre Caslon Text", Georgia, serif'

# Every colour below is a var(--e-*) set from the palette in inject_css(), so this block is plain CSS.
CSS = """
<style>
/* ---------------------------------------------------------------- base */
::selection { background: var(--e-accent-wash); color: var(--e-ink); }
input, textarea { caret-color: var(--e-accent); }
html { scrollbar-color: var(--e-line) transparent; }
[data-testid="stApp"] { background:
  radial-gradient(1100px 520px at 78% -8%, var(--e-glow), transparent 62%),
  radial-gradient(900px 600px at -10% 110%, var(--e-glow2), transparent 60%), var(--e-canvas); }
[data-testid="stMarkdownContainer"] a { text-underline-offset: .2em; text-decoration-thickness: 1px; }
.block-container { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1480px; }
h1 { letter-spacing: -0.012em; line-height: 1.1 !important; font-weight: 500 !important; }
h1, h2, h3 { text-wrap: balance; }
h2, h3 { letter-spacing: -0.004em; }
[data-testid="stHeadingWithActionElements"] h2 { padding-top: 1.8rem; padding-bottom: .35rem; }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { line-height: 1.6; text-wrap: pretty; }
[data-testid="stSliderThumbValue"] p, [data-testid="stSliderTickBar"] p { white-space: nowrap; text-wrap: nowrap; }
[data-testid="stMetricValue"], [data-testid="stDataFrame"], [data-testid="stTable"],
[data-testid="stCaptionContainer"] { font-variant-numeric: tabular-nums; }

/* ---------------------------------------------------------------- focus and actions */
a:focus-visible, button:focus-visible, summary:focus-visible, [role="radio"]:focus-visible,
[data-testid="stSidebarNavLink"]:focus-visible, iframe:focus-visible, input:focus-visible {
  outline: 2px solid var(--e-accent) !important; outline-offset: 2px; }
button[data-testid="stBaseButton-primary"], [data-testid="stDownloadButton"] button[kind="primary"] {
  color: var(--e-accent-ink) !important; font-weight: 600; border: 0; }
button[data-testid="stBaseButton-primary"] p { color: var(--e-accent-ink) !important; }
button[data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button:not([kind="primary"]) {
  background: var(--e-surface2); border: 1px solid var(--e-glass-edge); }
button[data-testid="stBaseButton-secondary"]:hover { border-color: var(--e-ink2); }
.stButton button, .stDownloadButton button, .stFormSubmitButton button, [data-testid="stPageLink"] a,
[data-testid="stLinkButton"] a { border-radius: var(--e-r-md); min-height: 2.6rem; }
@media (prefers-reduced-motion: no-preference) {
  .stButton button, .stDownloadButton button, .stFormSubmitButton button, [data-testid="stPageLink"] a {
    transition: transform 160ms var(--e-ease), background-color 160ms var(--e-ease), border-color 160ms var(--e-ease); }
  .stButton button:active, .stDownloadButton button:active, .stFormSubmitButton button:active,
  [data-testid="stPageLink"] a:active { transform: scale(0.97); }
}

/* ---------------------------------------------------------------- fields */
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-baseweb="input"],
[data-baseweb="textarea"], [data-baseweb="select"] > div {
  border-radius: var(--e-r-md) !important; background: var(--e-surface2) !important; border-color: var(--e-line) !important; }
[data-testid="stTextInputRootElement"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: var(--e-accent) !important; box-shadow: 0 0 0 3px var(--e-accent-wash); }
[data-testid="stWidgetLabel"] p { color: var(--e-ink2); font-size: .86rem; font-weight: 500; }
[data-testid="stSegmentedControl"] button, [data-testid="stPills"] button, [data-testid="stButtonGroup"] button {
  border-radius: var(--e-r-pill) !important; }
[data-testid="stTabs"] [data-baseweb="tab-list"] button { border-radius: var(--e-r-md) var(--e-r-md) 0 0; }

/* ---------------------------------------------------------------- panels
   Bordered containers read as one raised layer: a faint glass tint over the canvas, a cool edge,
   no blur (they hold data). Keyed panels (st-key-panel_*) get a little more presence. */
[data-testid="stVerticalBlock"][class*="st-key-panel"], [data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--e-r-xl) !important; }
[data-testid="stVerticalBlock"][class*="st-key-panel"] {
  background: linear-gradient(180deg, var(--e-panel-top), var(--e-panel-bot)) !important;
  border: 1px solid var(--e-glass-edge) !important; padding: 1.1rem 1.25rem 1.2rem !important;
  box-shadow: 0 1px 0 var(--e-sheen) inset, 0 28px 60px -36px rgba(0, 0, 0, .55); }
[class*="st-key-panel"] h3 { padding-top: 0 !important; margin-top: 0; }
.ember-panel-title { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
  margin: 0 0 .1rem; }
.ember-panel-title h3 { font-family: var(--e-serif); font-weight: 500; font-size: 1.35rem; margin: 0; padding: 0; color: var(--e-ink); }
.ember-panel-title span { font-size: .82rem; color: var(--e-muted); }
[data-testid="stExpander"] details { border: 1px solid var(--e-glass-edge); border-radius: var(--e-r-lg); overflow: hidden;
  background: color-mix(in srgb, var(--e-surface) 55%, transparent); }
[data-testid="stExpander"] summary { border-radius: var(--e-r-lg); }
[data-testid="stExpander"] summary p { font-weight: 500; }
[data-testid="stExpander"] summary:hover { background: color-mix(in srgb, var(--e-surface2) 70%, transparent); }

/* data surfaces: opaque, rounded, crisp */
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius: var(--e-r-lg); overflow: hidden;
  border: 1px solid var(--e-line); background: var(--e-surface); }
[data-testid="stPlotlyChart"] { border-radius: var(--e-r-lg); overflow: hidden; background: var(--e-surface);
  border: 1px solid var(--e-hair); }

/* metric tiles: label above, value below, a quiet top rule */
[data-testid="stMetric"] { background: transparent; border: 0; border-top: 1px solid var(--e-line); border-radius: 0; padding: .7rem 0 .2rem; }
[data-testid="stMetricValue"] { font-size: 1.7rem; line-height: 1.15; letter-spacing: -0.01em; }
[data-testid="stMetricLabel"] p { color: var(--e-ink2); font-size: .8rem; }

/* callouts: quiet notes on a wash; errors keep the ember rule; warnings get the warn rule */
[data-testid="stAlertContainer"] { background: var(--e-wash) !important; color: var(--e-ink) !important;
  border: 1px solid var(--e-glass-edge); border-left: 3px solid var(--e-ink2); border-radius: var(--e-r-md); }
[data-testid="stAlertContainer"] p, [data-testid="stAlertContainer"] li { color: var(--e-ink) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { border-left-color: var(--e-warn); background: var(--e-warn-wash) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { border-left-color: var(--e-accent); }
/* the one callout that must never be missed: partial gravity, and envelope warnings */
.ember-callout { display: grid; grid-template-columns: auto 1fr; gap: .2rem .9rem; align-items: start;
  border-radius: var(--e-r-lg); padding: .95rem 1.15rem; margin: .2rem 0 .9rem;
  background: var(--e-warn-wash); border: 1px solid color-mix(in srgb, var(--e-warn) 55%, transparent);
  box-shadow: inset 4px 0 0 var(--e-warn); color: var(--e-ink); }
.ember-callout .ic { grid-row: span 2; width: 1.7rem; height: 1.7rem; border-radius: 50%; display: grid; place-items: center;
  background: var(--e-warn); color: var(--e-canvas); font-weight: 700; font-size: .95rem; margin-top: .1rem; }
.ember-callout .t { font-weight: 650; color: var(--e-ink); font-size: .98rem; }
.ember-callout .b { color: var(--e-ink); font-size: .92rem; line-height: 1.55; }
.ember-callout .b cite { font-style: normal; color: var(--e-ink2); }

/* scenario summary chips */
.ember-scn { display: flex; flex-wrap: wrap; gap: .4rem; margin: .1rem 0 .2rem; }
.ember-scn span { display: inline-flex; align-items: baseline; gap: .4rem; padding: .32rem .75rem; border-radius: var(--e-r-pill);
  background: var(--e-surface2); border: 1px solid var(--e-glass-edge); font-size: .86rem; color: var(--e-ink);
  font-variant-numeric: tabular-nums; }
.ember-scn span i { font-style: normal; color: var(--e-muted); font-size: .76rem; }
.ember-scn span.k { border-color: color-mix(in srgb, var(--e-accent) 55%, transparent); }
.ember-scn span.k b { color: var(--e-accent); font-weight: 600; }
.ember-scn span.g { border-color: color-mix(in srgb, var(--e-warn) 50%, transparent); }

/* ---------------------------------------------------------------- sidebar: tinted glass */
[data-testid="stSidebar"] { background: transparent; border-right: 1px solid var(--e-glass-edge); }
[data-testid="stSidebar"] > div:first-child { background: var(--e-glass);
  -webkit-backdrop-filter: blur(18px) saturate(130%); backdrop-filter: blur(18px) saturate(130%); }
header[data-testid="stHeader"] { background: color-mix(in srgb, var(--e-canvas) 72%, transparent);
  -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); }
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  [data-testid="stSidebar"] > div:first-child { background: var(--e-glass-solid); }
  header[data-testid="stHeader"] { background: var(--e-canvas); } }
@media (prefers-reduced-transparency: reduce) {
  [data-testid="stSidebar"] > div:first-child { background: var(--e-glass-solid); backdrop-filter: none; -webkit-backdrop-filter: none; }
  header[data-testid="stHeader"] { background: var(--e-canvas); backdrop-filter: none; -webkit-backdrop-filter: none; } }
[data-testid="stSidebarNavSeparator"] { margin: .35rem 12px; border-color: var(--e-hair); }
[data-testid="stNavSectionHeader"] { color: var(--e-muted) !important; font-size: .74rem !important; letter-spacing: .02em; }
[data-testid="stSidebarNavLink"] { border-radius: var(--e-r-md); margin: 1px 0; padding-left: .7rem; position: relative;
  transition: background-color 160ms var(--e-ease); }
[data-testid="stSidebarNavLink"]:hover { background: color-mix(in srgb, var(--e-ink) 7%, transparent); }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: color-mix(in srgb, var(--e-accent) 15%, transparent) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"]::before { content: ""; position: absolute; left: 0; top: 22%; bottom: 22%;
  width: 3px; border-radius: 3px; background: var(--e-accent); }
[data-testid="stSidebarNavLink"][aria-current="page"] span { color: var(--e-ink) !important; font-weight: 600; }
[data-testid="stSidebar"] h2 { font-size: 1.05rem !important; font-style: italic; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"][class*="st-key-sb_"] {
  background: color-mix(in srgb, var(--e-canvas) 45%, transparent); border: 1px solid var(--e-glass-edge) !important;
  border-radius: var(--e-r-lg) !important; padding: .75rem .8rem .55rem !important; gap: .55rem; }
[data-testid="stSidebar"] p.ember-sb-h, .ember-sb-h { font-size: .78rem !important; font-weight: 600; color: var(--e-ink2);
  letter-spacing: .02em; margin: 0 0 .15rem !important; line-height: 1.3; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: var(--e-muted); }
@media (max-height: 760px) {
  [data-testid="stSidebar"] [data-testid="stVerticalBlock"][class*="st-key-sb_"] { padding: .55rem .65rem .4rem !important; gap: .35rem; }
}
@media (max-width: 640px) {
  [data-testid="stSidebar"] > div:first-child { -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px); }
  [data-testid="stVerticalBlock"][class*="st-key-panel"] { padding: .85rem .8rem 1rem !important; border-radius: var(--e-r-lg) !important; }
  .block-container { padding-top: 1.2rem; }
}

/* ---------------------------------------------------------------- page text */
.ember-lede { color: var(--e-ink2); font-family: var(--e-serif); font-size: 1.12rem; line-height: 1.55;
  max-width: 58rem; margin: -.1rem 0 1.4rem 0; }
.ember-lede b { color: var(--e-ink); font-weight: 600; }
.ember-rule { border: 0; border-top: 1px solid var(--e-line); margin: .2rem 0 1.4rem 0; }
[data-testid="stPageLink"] a p { font-weight: 600; font-size: 1rem; }
@keyframes ember-reveal { from { opacity: 0; } to { opacity: 1; } }
@media (prefers-reduced-motion: no-preference) {
  [data-testid="stExpander"] details[open] > :not(summary) { animation: ember-reveal 180ms var(--e-ease); }
}
@media (prefers-contrast: more) {
  :root { --e-line: var(--e-ink2); --e-muted: var(--e-ink2); --e-glass-edge: var(--e-ink2); }
  .ember-empty { border-style: solid; }
}
.ember-atlas-actions { margin: .2rem 0 .6rem; }
.ember-reading { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.2rem 2.4rem; margin: .2rem 0 .4rem; }
@media (max-width: 900px) { .ember-reading { grid-template-columns: 1fr; } }
.ember-reading h4 { font-family: var(--e-serif); font-style: italic; font-weight: 500; font-size: 1.15rem; color: var(--e-ink); margin: 0 0 .35rem; padding: 0; }
.ember-reading p { font-size: .95rem; line-height: 1.6; color: var(--e-ink2); margin: 0; max-width: 34rem; }
.ember-reading b { color: var(--e-ink); font-weight: 600; }
.ember-steps { list-style: none; counter-reset: step; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem 1.6rem; margin: .4rem 0 1rem; padding: 0; }
@media (max-width: 1180px) { .ember-steps { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 520px) { .ember-steps { grid-template-columns: 1fr; } }
.ember-steps li { border-top: 1px solid var(--e-line); padding: .7rem 0 0; margin: 0; }
.ember-steps li::before { counter-increment: step; content: counter(step); display: block; font-family: var(--e-display); font-size: 2rem;
  line-height: 1; color: var(--e-ink2); margin-bottom: .45rem; font-variant-numeric: lining-nums; }
.ember-steps .t { font-weight: 600; color: var(--e-ink); margin: 0 0 .2rem; }
.ember-steps .d { font-size: .9rem; color: var(--e-ink2); line-height: 1.5; }
.ember-index-q { font-family: var(--e-serif); font-style: italic; font-size: 1.12rem; line-height: 1.4; color: var(--e-ink); margin: .15rem 0 0; text-wrap: balance; }
.ember-index-row { border-top: 1px solid var(--e-line); }
.ember-index-d { font-size: .88rem; color: var(--e-ink2); line-height: 1.5; margin: .1rem 0 .5rem; }
.ember-terms-title, .ember-next-title { font-weight: 600; color: var(--e-ink); margin: .6rem 0 .3rem; }
.ember-next-title { margin-top: 2.6rem; padding-top: 1.2rem; border-top: 1px solid var(--e-line);
  font-family: var(--e-serif); font-style: italic; font-weight: 500; font-size: 1.15rem; }
.ember-terms { display: grid; grid-template-columns: minmax(9rem, max-content) 1fr; gap: .35rem 1.2rem; margin: 0; font-size: .9rem; line-height: 1.5; }
.ember-terms dt { font-weight: 600; color: var(--e-ink); }
.ember-terms dd { margin: 0; color: var(--e-ink2); }
@media (max-width: 640px) { .ember-terms { grid-template-columns: 1fr; gap: 0 0; } .ember-terms dd { margin-bottom: .5rem; } }
.ember-empty { border: 1px dashed var(--e-line); border-radius: var(--e-r-lg); padding: 1.4rem 1.6rem; background: var(--e-wash); color: var(--e-ink2); }
.ember-empty b { color: var(--e-ink); display: block; margin-bottom: .25rem; }
.ember-footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--e-line); font-size: .8rem; color: var(--e-muted); }
</style>
"""


# Motion and result components shared by the analysis pages. Transform and opacity only; everything
# is final and readable with reduced motion.
MOTION_CSS = """
<style>
@keyframes ember-rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes ember-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes ember-spot { 0% { opacity: 0; transform: scale(.985); } 100% { opacity: 1; transform: none; } }
@keyframes ember-move { from { transform: translateY(var(--from, 0)); } to { transform: none; } }
@keyframes ember-tick { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@media (prefers-reduced-motion: no-preference) {
  [data-testid="stMainBlockContainer"]:not(:has(iframe[title="ember.ui.atlas.ember_atlas"]))
    > div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"],
  [data-testid="stMainBlockContainer"]:not(:has(iframe[title="ember.ui.atlas.ember_atlas"]))
    > div > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"],
  [data-testid="stMainBlockContainer"]:not(:has(iframe[title="ember.ui.atlas.ember_atlas"]))
    > div > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"],
  [data-testid="stMainBlockContainer"]:not(:has(iframe[title="ember.ui.atlas.ember_atlas"]))
    > div > [data-testid="stVerticalBlock"] > [data-testid="stExpander"] {
    animation: ember-rise 380ms var(--e-ease) both; }
  [data-testid="stVerticalBlock"] > :nth-child(2) { animation-delay: 30ms; }
  [data-testid="stVerticalBlock"] > :nth-child(3) { animation-delay: 60ms; }
  [data-testid="stVerticalBlock"] > :nth-child(4) { animation-delay: 90ms; }
  [data-testid="stVerticalBlock"] > :nth-child(5) { animation-delay: 120ms; }
  [data-testid="stVerticalBlock"] > :nth-child(6) { animation-delay: 150ms; }
  [data-testid="stVerticalBlock"] > :nth-child(n+7) { animation-delay: 180ms; }
  [data-testid="stPlotlyChart"], [data-testid="stDataFrame"] { animation: ember-fade 320ms var(--e-ease) both; }
  .ember-spot { animation: ember-spot 600ms var(--e-ease) 150ms both; }
  .ember-move li { animation: ember-move 700ms var(--e-ease) var(--delay, 300ms) both; }
  .ember-move .bar i { animation: ember-tick 520ms var(--e-ease) 600ms both; }
  .ember-diff tr.drives td { animation: ember-fade 420ms var(--e-ease) both; }
}
.ember-spot { border: 1px solid color-mix(in srgb, var(--e-accent) 60%, transparent); border-radius: 18px; padding: 1.1rem 1.3rem;
  margin: .4rem 0 1rem; background: var(--e-accent-wash); }
.ember-spot .k { font-size: .82rem; color: var(--e-ink2); margin: 0 0 .25rem; }
.ember-spot .v { font-family: var(--e-display); font-size: 2.6rem; line-height: 1; color: var(--e-ink); font-variant-numeric: tabular-nums; }
.ember-spot .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); gap: 1rem 2rem; margin: .6rem 0 .7rem; }
.ember-spot p { margin: .2rem 0 0; color: var(--e-ink); line-height: 1.55; }
.ember-spot .miss { font-family: var(--e-serif); font-style: italic; font-size: 1.1rem; }
.ember-move { list-style: none; margin: .4rem 0 1rem; padding: 0; }
.ember-move li { display: grid; grid-template-columns: 2.2rem 1fr 7.5rem 9rem; align-items: center; gap: .8rem;
  height: 2.6rem; border-top: 1px solid var(--e-line); font-variant-numeric: tabular-nums; }
.ember-move .n { font-family: var(--e-display); font-size: 1.3rem; color: var(--e-ink2); }
.ember-move .inv { font-family: var(--e-serif); font-style: italic; color: var(--e-ink); }
.ember-move .mv { font-size: .85rem; color: var(--e-ink2); }
.ember-move .mv.up { color: var(--e-accent); font-weight: 600; }
.ember-move .d { font-size: .85rem; color: var(--e-ink2); text-align: right; }
.ember-move .bar { grid-column: 2 / -1; display: none; }
.ember-chip { display: inline-block; border: 1px solid var(--e-glass-edge); border-radius: 999px; padding: .2rem .7rem;
  font-size: .85rem; color: var(--e-ink); margin: 0 .4rem .4rem 0; background: var(--e-surface2); }
.ember-chip.fixed { border-color: var(--e-ink2); }
.ember-chip b { font-weight: 600; }
@media (max-width: 640px) { .ember-move li { grid-template-columns: 1.8rem 1fr 5.4rem; } .ember-move .d { display: none; } }
.ember-diff { width: 100%; border-collapse: separate; border-spacing: 0; font-size: .92rem; margin: .4rem 0 1rem;
  border: 1px solid var(--e-line); border-radius: 14px; overflow: hidden; background: var(--e-surface); }
.ember-diff th { text-align: left; font-weight: 600; color: var(--e-ink2); font-size: .8rem; padding: .5rem .7rem;
  border-bottom: 1px solid var(--e-line); background: var(--e-surface2); }
.ember-diff td { padding: .5rem .7rem; border-bottom: 1px solid var(--e-hair); vertical-align: top; color: var(--e-ink); }
.ember-diff tr:last-child td { border-bottom: 0; }
.ember-diff td:first-child { color: var(--e-ink2); white-space: nowrap; }
.ember-diff tr.drives td { background: var(--e-accent-wash); }
.ember-diff tr.drives td:first-child { box-shadow: inset 3px 0 0 var(--e-accent); color: var(--e-ink); font-weight: 600; }
.ember-diff .loc { display: block; font-size: .75rem; color: var(--e-muted); margin-top: .1rem; word-break: break-word; }
</style>
"""


def persist_scenario() -> None:
    ss = st.session_state
    for k in PERSISTENT_KEYS:
        if k in ss:
            ss[k] = ss[k]


def tokens() -> dict[str, str]:
    from ember.ui.theme import is_dark

    return TOKENS["dark" if is_dark() else "light"]


def root_css(t: dict[str, str]) -> str:
    """The palette as CSS custom properties (--e-*), for the Streamlit pages."""
    dark = t.get("base") == "dark"
    extra = {
        # decorative canvas lighting and panel tint; data colours never come from here
        "glow": "rgba(70, 92, 128, 0.20)" if dark else "rgba(150, 170, 205, 0.22)",
        "glow2": "rgba(255, 138, 76, 0.045)" if dark else "rgba(196, 80, 28, 0.035)",
        "panel-top": "rgba(30, 41, 60, 0.62)" if dark else "rgba(255, 255, 255, 0.86)",
        "panel-bot": "rgba(20, 29, 44, 0.62)" if dark else "rgba(250, 251, 253, 0.86)",
        "sheen": "rgba(255, 255, 255, 0.04)" if dark else "rgba(255, 255, 255, 0.9)",
    }
    names = {k: k.replace("_", "-") for k in t if k != "base" and not k.startswith("radius")}
    decl = "".join(f"--e-{names[k]}:{t[k]};" for k in names)
    decl += "".join(f"--e-{k}:{v};" for k, v in extra.items())
    decl += (
        f"--e-r-xl:{RADII['xl']};--e-r-lg:{RADII['lg']};--e-r-md:{RADII['md']};"
        f"--e-r-pill:{RADII['pill']};--e-serif:{SERIF};--e-display:{DISPLAY};"
        "--e-ease:cubic-bezier(0.23, 1, 0.32, 1);"
    )
    return f"<style>:root{{{decl}}}</style>"


def inject_css() -> None:
    st.markdown(root_css(tokens()) + CSS + MOTION_CSS, unsafe_allow_html=True)


def callout(title: str, body: str, cite: str | None = None) -> None:
    """A high-contrast warning that must stay readable: partial gravity, envelope limits."""
    c = f" <cite>{html.escape(cite)}</cite>" if cite else ""
    st.markdown(
        f'<div class="ember-callout" role="note"><span class="ic" aria-hidden="true">!</span>'
        f'<div class="t">{html.escape(title)}</div><div class="b">{html.escape(body)}{c}</div></div>',
        unsafe_allow_html=True,
    )


def panel_title(title: str, note: str = "") -> None:
    n = f"<span>{html.escape(note)}</span>" if note else ""
    st.markdown(
        f'<div class="ember-panel-title"><h3>{html.escape(title)}</h3>{n}</div>',
        unsafe_allow_html=True,
    )


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
