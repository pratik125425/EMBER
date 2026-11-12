"""Sources page (spec §13): every source with title, year, URL/DOI, in_psi, sha256, retrieved_at and
which records cite it. sha256/retrieved_at live per mirrored file (data/manifest.csv)."""

import pandas as pd
import streamlit as st

from ember.export import citing_evidence, tables, to_csv_bytes
from ember.registry import load_registry
from ember.ui.badges import sidebar_legend
from ember.ui.layout import page_header

st.set_page_config(page_title="EMBER · Sources", layout="wide")


@st.cache_resource
def _data():
    reg = load_registry()
    return reg, tables(reg), citing_evidence(reg)


reg, T, cites = _data()
src, files = T["sources"], T["files"]

sidebar_legend()
page_header(
    "Sources",
    "Every source the registry uses. Checksums and retrieval times belong to individual files: a source "
    "can have several mirrored files, or none (shown as **not mirrored**, never as a blank checksum).",
    section="Data",
)

latest = files.dropna(subset=["retrieved_at"]).groupby("source_id")["retrieved_at"].max()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sources", len(src))
c2.metric("In NASA PSI", int(src["in_psi"].sum()))
c3.metric("Files mirrored (SHA-256)", f"{int(files['sha256'].notna().sum())} of {len(files)}")
c4.metric("Sources cited by no record", int((src["n_evidence_citing"] == 0).sum()))


def _txt(v, empty="unknown"):
    return empty if v is None or (isinstance(v, float) and pd.isna(v)) or v == "" else v


view = pd.DataFrame(
    {
        "Source": src["source_id"],
        "Title": src["title"].map(_txt),
        "Year": src["year"].map(lambda y: "unknown" if pd.isna(y) else str(int(y))),
        "Kind": src["kind"],
        "In PSI": src["in_psi"].map({True: "yes", False: "no"}),
        "URL": src["url"].map(lambda v: _txt(v, "none")),
        "DOI": src["doi"].map(lambda v: _txt(v, "none")),
        "Files mirrored": src["n_files_mirrored"].map(lambda n: str(n) if n else "not mirrored"),
        "Latest retrieved_at (UTC)": src["source_id"].map(lambda s: latest.get(s, "not mirrored")),
        "Records citing": src["n_evidence_citing"],
    }
)
st.dataframe(
    view,
    hide_index=True,
    width="stretch",
    column_config={"URL": st.column_config.LinkColumn("URL")},
)
st.download_button("Sources · CSV", to_csv_bytes(src), "ember_sources.csv", "text/csv")

# ------------------------------------------------------------------------------------- detail
st.subheader("Source detail")
sid = st.selectbox(
    "Source",
    list(src["source_id"]),
    format_func=lambda s: f"{s} · {_txt(src.set_index('source_id').at[s, 'title'])}",
    key="src_pick",
)
row = src.set_index("source_id").loc[sid]
st.markdown(
    f"**{_txt(row['title'])}** ({'unknown year' if pd.isna(row['year']) else int(row['year'])}) · "
    f"{row['kind']} · {'in NASA PSI' if row['in_psi'] else 'not in NASA PSI'}"
)
if isinstance(row["url"], str) and row["url"]:
    st.markdown(f"URL: {row['url']}")
if isinstance(row["doi"], str) and row["doi"]:
    st.markdown(f"DOI: {row['doi']}")

st.markdown("**Files**")
f = files[files["source_id"] == sid]
if f.empty:
    st.info("No files listed in the mirror manifest for this source.")
else:
    st.dataframe(
        pd.DataFrame(
            {
                "Path": f["path"].map(lambda v: _txt(v, "not mirrored")),
                "URL": f["url"],
                "SHA-256": f["sha256"].map(lambda v: _txt(v, "not mirrored")),
                "Retrieved at (UTC)": f["retrieved_at"].map(lambda v: _txt(v, "not mirrored")),
                "HTTP": f["http_status"].map(
                    lambda v: "not attempted" if pd.isna(v) else str(int(v))
                ),
                "Kind": f["kind"],
            }
        ),
        hide_index=True,
        width="stretch",
    )

ev_ids = sorted(cites.get(sid, ()))
st.markdown(f"**Evidence records citing it** · {len(ev_ids)}")
if ev_ids:
    ev = T["evidence"].set_index("evidence_id").loc[ev_ids].reset_index()
    st.dataframe(
        ev[["evidence_id", "investigation", "fuel_name", "gravity", "granularity"]].fillna(
            "unknown"
        ),
        hide_index=True,
        width="stretch",
        height=min(36 * len(ev) + 38, 320),
    )
else:
    st.caption("No evidence record lists this source or takes a condition value from it.")

cl = T["claims"][T["claims"]["source_id"] == sid]
ms = T["measurements"][T["measurements"]["source_id"] == sid]
st.markdown(f"**Claims from it** · {len(cl)}  ·  **Measurements from it** · {len(ms)}")
if not cl.empty:
    st.dataframe(
        cl[["claim_id", "evidence_id", "claim_type", "text"]],
        hide_index=True,
        width="stretch",
    )
if not ms.empty:
    with st.expander(f"{len(ms)} measurements"):
        st.dataframe(ms.drop(columns="source_id"), hide_index=True, width="stretch")
