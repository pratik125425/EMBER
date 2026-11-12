"""T16: export tables, data dictionary, Registry and Sources pages."""

import io
import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from ember.export import (
    TABLES,
    dictionary_frame,
    dictionary_markdown,
    tables,
    to_csv_bytes,
    to_parquet_bytes,
    write_exports,
)
from ember.paths import ROOT
from ember.registry import load_registry


@pytest.fixture(scope="module")
def reg():
    return load_registry()


@pytest.fixture(scope="module")
def T(reg):
    return tables(reg)


def test_every_column_documented_and_nothing_extra(T):
    dd = dictionary_frame()
    for name in TABLES:
        cols = set(T[name].columns)
        doc = set(dd.loc[dd["table"] == name, "column"])
        assert cols == doc, (name, cols ^ doc)
    assert not dd.duplicated(["table", "column"]).any()
    assert (dd["description"].str.len() > 10).all()


def test_units_in_range_columns():
    dd = dictionary_frame().set_index(["table", "column"])
    assert dd.at[("evidence", "p_kpa_min"), "unit"] == "kPa"
    assert dd.at[("evidence", "u_cms_max"), "unit"] == "cm/s"
    assert "mole fraction" in dd.at[("evidence", "x_o2_min"), "unit"]


def test_row_counts_match_registry(reg, T):
    assert len(T["evidence"]) == len(reg.evidence)
    assert len(T["claims"]) == len(reg.claims)
    assert len(T["sources"]) == len(reg.sources)


def test_unknown_is_never_imputed(T):
    ev = T["evidence"]
    for k in ("x_o2", "p_kpa", "u_cms", "size_cm"):
        unk = ev[ev[f"{k}_status"] != "known"]
        assert unk[f"{k}_min"].isna().all() and unk[f"{k}_max"].isna().all(), k
        known = ev[ev[f"{k}_status"] == "known"]
        assert known[f"{k}_min"].notna().all(), k


def test_burner_o2_is_not_ambient_usable(T):
    ev = T["evidence"]
    burner = ev[ev["o2_context"] == "burner_oxidizer_flow"]
    assert len(burner) > 0
    assert not burner["x_o2_ambient_usable"].any()
    usable = ev[ev["x_o2_ambient_usable"]]
    assert (usable["x_o2_status"] == "known").all()


def test_csv_and_parquet_round_trip(T):
    for name in TABLES:
        df = T[name]
        pq = pd.read_parquet(io.BytesIO(to_parquet_bytes(df)))
        assert list(pq.columns) == list(df.columns)
        assert len(pq) == len(df)
        csv = pd.read_csv(io.BytesIO(to_csv_bytes(df)))
        assert list(csv.columns) == list(df.columns)
        assert len(csv) == len(df)


def test_list_fields_are_joined_strings(T):
    ev = T["evidence"]
    for c in ("phenomena", "sources"):
        assert ev[c].map(lambda v: isinstance(v, str)).all(), c


def test_citing_counts_match_evidence(reg, T):
    src = T["sources"].set_index("source_id")
    n = sum(1 for e in reg.evidence if "PSI-69" in e.sources)
    assert src.at["PSI-69", "n_evidence_citing"] >= n > 0


def test_write_exports(tmp_path, reg):
    s = write_exports(tmp_path, reg)
    for name in TABLES:
        assert (tmp_path / f"{name}.csv").exists() and (tmp_path / f"{name}.parquet").exists()
    assert (tmp_path / "data_dictionary.md").read_text().startswith("# EMBER")
    m = json.loads((tmp_path / "export_manifest.json").read_text())
    assert m["rows"]["evidence"] == len(reg.evidence)
    assert len(m["files"]["evidence.csv"]) == 64
    assert s["rows"] == m["rows"]


def test_dictionary_markdown_has_all_tables():
    md = dictionary_markdown()
    for name in TABLES:
        assert f"## {name}" in md


# ------------------------------------------------------------------------------------- pages
def test_registry_page_renders_and_filters():
    at = AppTest.from_file(str(ROOT / "app/pages/5_Registry.py"), default_timeout=60).run()
    assert not at.exception
    total = at.metric[0].value
    at.checkbox(key="f_o2").set_value(True).run()
    assert not at.exception
    assert at.metric[0].value != total
    assert at.metric[2].value == "100%"
    at.text_input(key="f_text").set_value("PSI-69").run()
    assert not at.exception


def test_registry_page_shows_unknown_explicitly():
    at = AppTest.from_file(str(ROOT / "app/pages/5_Registry.py"), default_timeout=60).run()
    df = at.dataframe[0].value
    assert (df["Flow (cm/s)"] == "unknown").any()
    assert df["X_O₂ (mole fraction)"].map(lambda v: v != "" and v is not None).all()
    assert (df["O₂ context"] == "burner-side (not ambient)").any()


def test_sources_page_renders_with_detail():
    at = AppTest.from_file(str(ROOT / "app/pages/7_Sources.py"), default_timeout=60).run()
    assert not at.exception
    df = at.dataframe[0].value
    assert {"Source", "Title", "Year", "In PSI", "URL", "DOI", "Records citing"} <= set(df.columns)
    assert (df["Files mirrored"] == "not mirrored").any()
    at.selectbox(key="src_pick").set_value("PSI-69").run()
    assert not at.exception
    assert any("SHA-256" in d.value.columns for d in at.dataframe[1:])
