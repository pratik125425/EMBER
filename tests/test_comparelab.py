"""T10: CompareLab rule engine and labeled-pair validation."""

import yaml

from ember.engine.comparelab import (
    CAVEATS,
    COMPARABLE,
    NOT_COMPARABLE,
    compare_evidence,
    compare_measurements,
    false_comparable_rate,
    units_convertible,
)
from ember.paths import ROOT
from ember.registry import load_registry
from ember.schemas import Measurement

REG = load_registry()
E = REG.evidence_by_id()
M = {m.measurement_id: m for m in REG.measurements}


def test_units_convertible():
    assert (
        units_convertible("kPa", "psi")
        and units_convertible("mg/m3", "g/m3")
        and units_convertible("cm/s", "mm/s")
    )
    assert not units_convertible("kPa", "cm/s") and not units_convertible("dimensionless", "kPa")


def test_cfig_burner_vs_ambient_is_not_comparable():
    r = compare_evidence(E["CFIG:burner85"], E["BASS-II:campaign"])
    assert r["verdict"] == NOT_COMPARABLE  # no shared phenomenon → rule 1 already fails
    # Same investigation, shared phenomenon, burner-side vs ambient O2 → rule 4 is the gate that fails.
    r = compare_evidence(E["CFIG:burner85"], E["CFIG:coolflame_2bar"])
    assert r["verdict"] == NOT_COMPARABLE
    assert any(x["rule"] == 4 and not x["passed"] for x in r["rules"])
    assert any("burner" in c.lower() for c in r["confounders"])
    # Measurement form: burner-context O2 vs ambient O2 of the same quantity.
    ma = Measurement(
        measurement_id="t1",
        evidence_id="CFIG:burner85",
        quantity="loc_x_o2",
        value=0.85,
        unit="dimensionless",
        value_kind="set_point",
        context="burner",
        source_id="PSI-159",
        source_locator="t",
    )
    mb = Measurement(
        measurement_id="t2",
        evidence_id="BASS-II:LOC",
        quantity="loc_x_o2",
        value=0.17,
        unit="dimensionless",
        value_kind="measured",
        context="ambient",
        source_id="PSI-25",
        source_locator="t",
    )
    r = compare_measurements(ma, E["CFIG:burner85"], mb, E["BASS-II:LOC"])
    assert r["verdict"] == NOT_COMPARABLE and [x["rule"] for x in r["rules"]] == [1, 2, 3, 4]


def test_saffire_i_vs_vi_caveat_on_duct_size():
    r = compare_evidence(E["SAFFIRE1:SIBAL"], E["SAFFIRE6:SIBAL"])
    assert r["verdict"] == CAVEATS
    assert any("25 cm vs 15 cm" in c for c in r["confounders"])
    assert any("non-PSI" in c for c in r["confounders"])
    assert [x["rule"] for x in r["rules"]] == [1, 2, 3, 4, 5, 6]


def test_bass2_vs_saffire6_caveats_hardware_scale_and_fuel():
    r = compare_evidence(E["BASS-II:campaign"], E["SAFFIRE6:SIBAL"])
    assert r["verdict"] == CAVEATS
    joined = " ".join(r["confounders"])
    assert "MSG+SPICE-duct vs Saffire Flow Unit/Cygnus" in joined and "sample scale" in joined
    assert "thick solid vs thin solid" in joined
    assert {row["condition"] for row in r["shared_conditions"]} >= {"gravity"}
    assert any(
        row["condition"] == "X_O₂" for row in r["differing_conditions"]
    )  # 0.136–0.222 vs 0.288–0.31


def test_no_shared_phenomenon_is_not_comparable():
    r = compare_evidence(E["SAMER:runs"], E["BASS-II:campaign"])
    assert r["verdict"] == NOT_COMPARABLE and r["rules"][0]["rule"] == 1 and len(r["rules"]) == 1


def test_measurement_pairs_from_seed():
    r = compare_measurements(
        M["M-BASS2-LOC-ug"], E["BASS-II:LOC"], M["M-BASS2-LOC-1g"], E["BASS-II:LOC_1g"]
    )
    assert r["verdict"] == CAVEATS and any("gravity" in c for c in r["confounders"])
    r = compare_measurements(
        M["M-DAFT-mass"], E["DAFT:ISS_ambient"], M["M-DAFT-count"], E["DAFT:ISS_ambient"]
    )
    assert r["verdict"] == NOT_COMPARABLE and r["rules"][0]["rule"] == 1


def test_identical_records_are_comparable():
    r = compare_evidence(E["SAFFIRE6:SIBAL"], E["SAFFIRE6:SIBAL"])
    # Same record → only the non-PSI note remains a caveat (it is a source caveat, kept deliberately).
    assert r["verdict"] in (COMPARABLE, CAVEATS)
    r2 = compare_evidence(E["BASS-II:campaign"], E["BASS-II:campaign"])
    assert r2["verdict"] == COMPARABLE and r2["confounders"] == []
    assert any(
        "ppO₂" in n
        for n in compare_evidence(E["SAFFIRE6:SIBAL"], E["SAFFIRE6:PMMA"])["normalizations_applied"]
    )


def test_labeled_pairs_zero_false_comparable():
    pairs = yaml.safe_load((ROOT / "ember" / "eval" / "comparelab_pairs.yaml").read_text())
    assert len(pairs) >= 10
    results = []
    for p in pairs:
        if p["kind"] == "evidence":
            r = compare_evidence(E[p["a"]], E[p["b"]])
        else:
            ma, mb = M[p["a"]], M[p["b"]]
            r = compare_measurements(ma, E[ma.evidence_id], mb, E[mb.evidence_id])
        results.append((r["verdict"], p["label"]))
    m = false_comparable_rate(results)
    assert m["false_comparable"] == 0 and m["false_comparable_rate"] == 0.0
    assert m["exact_agreement"] == 1.0, results
