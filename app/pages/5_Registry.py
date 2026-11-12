"""Registry page (spec §13): filterable evidence table with units and provenance, explicit unknowns,
CSV/Parquet export and the data dictionary."""

import pandas as pd
import streamlit as st

from ember.export import (
    TABLES,
    dictionary_frame,
    dictionary_markdown,
    tables,
    to_csv_bytes,
    to_parquet_bytes,
)
from ember.llm.templates import format_range
from ember.registry import load_registry
from ember.ui.badges import sidebar_legend
from ember.ui.layout import empty_state, page_header

st.set_page_config(page_title="EMBER · Registry", layout="wide")


@st.cache_resource
def _data():
    reg = load_registry()
    return reg, tables(reg)


reg, T = _data()
ev = T["evidence"]
by_id = reg.evidence_by_id()

sidebar_legend()
page_header(
    "Registry",
    "Every evidence record EMBER can rank, with units, the status of each condition and where each value "
    "came from. Unknown values are shown as unknown, never filled in.",
    section="Data",
)

# ------------------------------------------------------------------------------------- filters
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    inv = c1.multiselect("Investigation", sorted(ev["investigation"].unique()), key="f_inv")
    phen_all = sorted({p for v in ev["phenomena"] for p in v.split("; ") if p})
    phen = c2.multiselect("Phenomenon", phen_all, key="f_phen")
    grav = c3.multiselect("Gravity", sorted(ev["gravity"].unique()), key="f_grav")
    fuel = c4.multiselect("Fuel class", sorted(ev["fuel_class"].unique()), key="f_fuel")
    c5, c6, c7 = st.columns([2, 1, 1])
    text = c5.text_input(
        "Search id, fuel or hardware", key="f_text", placeholder="e.g. SIBAL, PSI-69, MSG"
    )
    need_o2 = c6.checkbox("Ambient O₂ known", key="f_o2")
    need_p = c7.checkbox("Pressure known", key="f_p")

mask = pd.Series(True, index=ev.index)
if inv:
    mask &= ev["investigation"].isin(inv)
if phen:
    mask &= ev["phenomena"].map(lambda v: any(p in v.split("; ") for p in phen))
if grav:
    mask &= ev["gravity"].isin(grav)
if fuel:
    mask &= ev["fuel_class"].isin(fuel)
if text.strip():
    q = text.strip().lower()
    hay = (
        ev["evidence_id"]
        + " "
        + ev["fuel_name"].fillna("")
        + " "
        + ev["hardware_family"].fillna("")
    ).str.lower()
    mask &= hay.str.contains(q, regex=False)
if need_o2:
    mask &= ev["x_o2_ambient_usable"]
if need_p:
    mask &= ev["p_kpa_status"] == "known"
sel = ev[mask]

# ------------------------------------------------------------------------------------- summary
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Records shown", f"{len(sel)} of {len(ev)}")
m2.metric("Investigations", sel["investigation"].nunique())
n = max(len(sel), 1)
m3.metric("Ambient O₂ known", f"{sel['x_o2_ambient_usable'].sum() / n:.0%}")
m4.metric("Pressure known", f"{(sel['p_kpa_status'] == 'known').sum() / n:.0%}")
m5.metric("Flow known", f"{(sel['u_cms_status'] == 'known').sum() / n:.0%}")


def _prov(row, k: str) -> str:
    if row[f"{k}_status"] != "known":
        return ""
    loc = row[f"{k}_source_locator"]
    return (
        f"{row[f'{k}_source_id']} · {loc}"
        if isinstance(loc, str) and loc
        else str(row[f"{k}_source_id"])
    )


def _o2_ctx(row) -> str:
    return {"burner_oxidizer_flow": "burner-side (not ambient)", "ambient": "ambient"}.get(
        row["o2_context"], "unknown"
    )


view = pd.DataFrame(
    {
        "Evidence": sel["evidence_id"],
        "Investigation": sel["investigation"],
        "PSI": sel["psi_id"].fillna("non-PSI"),
        "Fuel": sel["fuel_name"].fillna("unknown"),
        "Fuel class": sel["fuel_class"].str.replace("_", " "),
        "Phenomena": sel["phenomena"].str.replace("_", " "),
        "Gravity": sel["gravity"],
        "X_O₂ (mole fraction)": [format_range(by_id[i].x_o2, "{:.4g}") for i in sel["evidence_id"]],
        "O₂ context": [_o2_ctx(r) for _, r in sel.iterrows()],
        "P (kPa)": [format_range(by_id[i].p_kpa, "{:.4g}") for i in sel["evidence_id"]],
        "Flow (cm/s)": [format_range(by_id[i].u_cms, "{:.3g}") for i in sel["evidence_id"]],
        "Granularity": sel["granularity"].str.replace("_", " "),
        "X_O₂ source": [_prov(r, "x_o2") for _, r in sel.iterrows()],
        "P source": [_prov(r, "p_kpa") for _, r in sel.iterrows()],
        "Flow source": [_prov(r, "u_cms") for _, r in sel.iterrows()],
        "Sources": sel["sources"],
    }
)
if sel.empty:
    empty_state(
        "No records match these filters",
        "Clear a filter or the search box to see more. Filters combine with AND.",
    )
else:
    st.dataframe(view, hide_index=True, width="stretch", height=460)
st.caption(
    "Ranges stay ranges (min–max). **unknown** = the source does not state it; **n/a** = not applicable "
    "(e.g. O₂ for a smoke-particle run). Burner-side O₂ (CFI-G inverse flames) is stored with its context "
    "and never used as an ambient atmosphere. Source columns give the source id and the table row, page "
    "or column the value was read from."
)

# ------------------------------------------------------------------------------------- export
st.subheader("Export")
st.markdown(
    "Clean, unit-normalized tables for modelers. Units are in column names (`x_o2_*` mole fraction, "
    "`p_kpa_*` kPa, `u_cms_*` cm/s); each condition keeps its status and provenance columns. "
    "The same files can be written to `exports/` with `uv run python -m ember.export`."
)
c1, c2, c3 = st.columns(3)
c1.download_button(
    f"Filtered evidence · CSV ({len(sel)} rows)",
    to_csv_bytes(sel),
    "ember_evidence_filtered.csv",
    "text/csv",
    width="stretch",
)
c2.download_button(
    f"All evidence · Parquet ({len(ev)} rows)",
    to_parquet_bytes(ev),
    "ember_evidence.parquet",
    "application/octet-stream",
    width="stretch",
)
c3.download_button(
    "Data dictionary · Markdown",
    dictionary_markdown().encode("utf-8"),
    "ember_data_dictionary.md",
    "text/markdown",
    width="stretch",
)
with st.expander("Other tables (measurements, claims, sources, files, relations)"):
    for name in TABLES:
        if name == "evidence":
            continue
        df = T[name]
        a, b, c = st.columns([2, 1, 1])
        a.markdown(f"**{name}** · {len(df)} rows")
        b.download_button(
            "CSV", to_csv_bytes(df), f"ember_{name}.csv", "text/csv", key=f"csv_{name}"
        )
        c.download_button(
            "Parquet",
            to_parquet_bytes(df),
            f"ember_{name}.parquet",
            "application/octet-stream",
            key=f"pq_{name}",
        )

st.subheader("Data dictionary")
dd = dictionary_frame()
tab = st.selectbox("Table", list(TABLES), key="dd_table")
st.dataframe(dd[dd["table"] == tab].drop(columns="table"), hide_index=True, width="stretch")
