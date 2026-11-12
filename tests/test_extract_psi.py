"""T11: per-investigation PSI table parsers."""

import pytest

from ember.ingest import extract_psi as X
from ember.paths import RAW_DIR

RAW = RAW_DIR


def _raw(psi, name):
    p = RAW / psi / name
    if not p.exists():
        pytest.skip(f"{p} not mirrored (run ember.ingest.download)")
    return p


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2 cm SIBAL", "thin_solid"),
        ('1/4" clear rod', "thick_solid"),
        ("100 micron PMMA film   2 cm wide", "thin_solid"),
        ("2 cm   0.4 mm thick film", "thin_solid"),
        ("5 mm thick PMMA   2 cm wide", "thick_solid"),
        ("Nomex natural (nomex III)", "thin_solid"),
        ("PMMA sphere 2 cm", "thick_solid"),
        ("Japan Wax candle", "thick_solid"),
        ("ultem sheet", "thin_solid"),
    ],
)
def test_fuel_class_from_text(text, expected):
    assert X.fuel_class_from_text(text) == expected


def test_flex_synthetic_cp1252_sentinels_diluents_and_units(tmp_path):
    header = (
        "FLEX Test #,FLEX Identifier,Test Date,Test GMT,Fuel,Ambient pressure; mmHg,"
        "O initial ambient composition; mole fraction,N initial ambient composition; mole fraction,"
        "CO initial ambient composition; mole fraction,He initial ambient composition; mole fraction,"
        "Droplet initial diameter; mm,Visible flame extinction diameter; mm,Burning rate; mm,Burn time; s,Test end\n"
    )
    rows = (
        "1,A,1/1/2009,1:00,Methanol,760,0.21,0.79,0,0,2.0,0.9,0.52,4,Extinction\n"
        "2,B,1/1/2009,2:00,Heptane,0,0.15,0.15,0.7,0,\u2013,\u2013,0.6,5,Disruption\n"
        "3,C,1/1/2009,3:00,Heptane,1520,0.3,0.25,0,0.45,3.0,1.1,0.7,6,Completion\n"
    )
    p = tmp_path / "flex.csv"
    p.write_bytes((header + rows).encode("cp1252"))
    ex = X.parse_flex(p)
    e1, e2, e3 = ex.evidence
    assert (
        e1.p_kpa.min == pytest.approx(101.325, abs=0.01) and "data row 1" in e1.p_kpa.source_locator
    )
    assert e1.diluent == "N2" and e1.phenomena == ["burning_rate", "extinction"]
    assert e1.size_cm.min == pytest.approx(0.2)
    assert e2.p_kpa.status == "unknown"  # 0 mmHg treated as missing, never 0 kPa
    assert e2.diluent == "N2+CO2" and "suppression" in e2.phenomena  # header 'CO' read as CO2
    assert e2.size_cm is None  # en dash (0x96) is a sentinel
    assert e3.diluent == "N2+He" and "extinction" not in e3.phenomena
    ks = {m.evidence_id: m for m in ex.measurements if m.quantity == "burning_rate_K_mm2_s"}
    assert ks["PSI-69:T001"].value == 0.52 and ks["PSI-69:T001"].unit == "mm**2/s"
    dext = [m for m in ex.measurements if m.quantity == "extinction_diameter_mm"]
    assert [m.evidence_id for m in dext] == ["PSI-69:T001"]  # only rows that ended in extinction
    assert ex.skipped["extinction diameter present but test end ≠ Extinction (not stored)"] == 1


def test_cfig_inverse_synthetic_is_burner_side_and_skips_blank_rows(tmp_path):
    p = tmp_path / "inv.csv"
    p.write_text(
        "Flame Type,Day,Fuel,Test,Xf  before test,Xf  after test,approx p (bar),XO2,HC burnrate (mg/s),"
        "O2 flow rate (mg/s),TFP,Tad (K),Zst,Hot ignition,burn time (sec),Self -ext or flow term,"
        "Peak burner Temp (C),Peak burner temp (K),Color,Comments\n"
        "Inverse,1,ethane,21196 A1,0.3,0.29,2.2066,0.85,1.5,5.6,No,2120,0.17,Yes,35,SE,100,373,blue,\n"
        ",,,,,,,,,,,,,,,,,,,\n"
    )
    ex = X.parse_cfig_inverse(p)
    assert len(ex.evidence) == 1 and ex.skipped["blank spreadsheet row"] == 1
    e = ex.evidence[0]
    assert e.evidence_id == "PSI-159:I:21196A1" and e.o2_context.value == "burner_oxidizer_flow"
    assert e.x_o2.max == 0.85 and "burner/oxidizer-side" in e.x_o2.source_locator
    assert e.p_kpa.min == pytest.approx(220.66) and "extinction" in e.phenomena


def test_real_tables_row_counts_and_mappings():
    reps = {(r["psi_id"], r["file"]): r for r in X.run(RAW, RAW.parent / "_extract_test_tmp")}
    if any(r.get("missing") for r in reps.values()):
        pytest.skip("raw PSI tables not mirrored")
    get = lambda f: next(r for (psi, name), r in reps.items() if name == f)  # noqa: E731
    assert get("PSI-25_Experimental table_BASS-II.csv")["evidence_out"] == 129
    assert get("PSI-26_Experimental table_BASS.csv")["evidence_out"] == 121
    assert get("PSI-69_Experimental table_FLEX.csv")["evidence_out"] == 274
    assert get("PSI-100_Experimental table_SAFFIRE-3.csv")["evidence_out"] == 2
    assert get("PSI-101_Experimental table_SAME-R.csv")["evidence_out"] == 109
    assert get("PSI-159_Experimental table_CFI-G_Normal Flames.csv")["evidence_out"] == 179
    inv = get("PSI-159_Experimental table_CFI-G_Inverse Flames.csv")
    assert inv["evidence_out"] == 154 and inv["skipped"]["blank spreadsheet row"] == 861
    import shutil

    shutil.rmtree(RAW.parent / "_extract_test_tmp", ignore_errors=True)


def test_committed_extracts_match_a_fresh_parse(tmp_path):
    """data/extracted must be regenerated whenever a parser changes."""
    _raw("PSI-69", "PSI-69_Experimental table_FLEX.csv")
    X.run(RAW, tmp_path)
    for name in ("evidence_PSI-69.jsonl", "evidence_PSI-159.jsonl", "evidence_PSI-25.jsonl"):
        assert (tmp_path / name).read_text() == (X.EXTRACTED_DIR / name).read_text(), name


def test_cool_flame_rows_match_updated_seed():
    p = _raw("PSI-159", "PSI-159_Experimental table_CFI-G_Normal Flames.csv")
    ex = X.parse_cfig_normal(p)
    cool = [e for e in ex.evidence if "cool_flame" in [ph.value for ph in e.phenomena]]
    assert len(cool) == 7
    assert min(e.x_o2.min for e in cool) == 0.385474447 and max(e.x_o2.max for e in cool) == 0.3993
    assert {e.p_kpa.min for e in cool} == {202.66}
