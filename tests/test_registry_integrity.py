"""T05: seed registry integrity (spec §14)."""

import csv

import duckdb
import pandas as pd
import pytest

from ember.curate.build_registry import (
    RegistryIntegrityError,
    build,
    check_integrity,
    load_seed_models,
    read_manifest,
    review_todos,
)
from ember.engine.score import rank
from ember.paths import MANIFEST_CSV, SEED_DIR
from ember.registry import load_registry


@pytest.fixture(scope="module")
def models():
    return load_seed_models(SEED_DIR)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("curated")
    summary = build(
        SEED_DIR, out, MANIFEST_CSV, extracted_dir=None
    )  # seed-only: counts below are the seed's
    return out, summary


@pytest.fixture(scope="module")
def built_full(tmp_path_factory):
    out = tmp_path_factory.mktemp("curated_full")
    return out, build(SEED_DIR, out, MANIFEST_CSV)


def test_seeds_validate_and_have_no_integrity_problems(models):
    assert check_integrity(models, read_manifest(MANIFEST_CSV)) == []


def test_every_evidence_row_has_a_source(models):
    assert all(len(e.sources) >= 1 for e in models["evidence"])


def test_every_source_in_manifest(models):
    manifest_ids = {r["source_id"] for r in read_manifest(MANIFEST_CSV)}
    assert {s.source_id for s in models["sources"]} <= manifest_ids


def test_no_duplicate_ids(models):
    for key, attr in (
        ("evidence", "evidence_id"),
        ("sources", "source_id"),
        ("measurements", "measurement_id"),
        ("claims", "claim_id"),
        ("relations", "relation_id"),
    ):
        ids = [getattr(m, attr) for m in models[key]]
        assert len(ids) == len(set(ids)), key


def test_known_values_all_have_provenance(models):
    for e in models["evidence"]:
        for k in ("x_o2", "p_kpa", "u_cms", "size_cm"):
            r = getattr(e, k)
            if r is not None and r.status == "known":
                assert r.source_id and r.source_locator, f"{e.evidence_id}.{k}"


def test_appendix_a_values_are_exactly_as_specified(models):
    by = {e.evidence_id: e for e in models["evidence"]}
    b2 = by["BASS-II:campaign"]
    assert (b2.x_o2.min, b2.x_o2.max, b2.x_o2.status) == (0.136, 0.222, "known")
    assert b2.p_kpa.status == "unknown" and b2.p_kpa.min is None
    assert (b2.u_cms.min, b2.u_cms.max) == (0.0, 40.0)
    s6 = by["SAFFIRE6:SIBAL"]
    assert s6.psi_id is None and (s6.x_o2.min, s6.x_o2.max) == (0.288, 0.310)
    assert (s6.p_kpa.min, s6.p_kpa.max) == (54.1, 55.2) and s6.tensions
    assert by["CFIG:burner85"].o2_context.value == "burner_oxidizer_flow"
    assert by["CFIG:burner85"].x_o2.status == "unknown"  # ≤85% is not a known ambient range
    assert by["SAMER:runs"].x_o2.status == "not_applicable"
    assert by["LUCI:overlay"].gravity.value == "simulated_partial"
    assert by["LUCI:overlay"].x_o2.status == "unknown"  # "air" not yet confirmed
    assert by["SAFFIRE1:SIBAL"].x_o2.status == "unknown"  # [A] not seeded until sourced
    assert by["BASS-II:LOC_1g"].gravity.value == "1g" and by["BASS-II:LOC_1g"].x_o2.min == 0.18


def test_review_todos_track_unfilled_locators(models):
    todos = review_todos(models)
    assert any(t["id"] == "SAFFIRE6:SIBAL" and t["field"] == "x_o2" for t in todos)
    # Locators confirmed from the downloaded PSI table/record are no longer TODO.
    assert not any(t["id"] == "BASS-II:campaign" for t in todos)
    assert not any(t["id"] == "CFIG:coolflame_2bar" for t in todos)
    # Locators that are real (not TODO) are not listed.
    assert not any(t["id"] == "C-FM2-GOLDILOCKS" for t in todos)


def test_integrity_check_catches_dangling_source(models):
    broken = dict(models)
    broken["sources"] = [s for s in models["sources"] if s.source_id != "PSI-98"]
    problems = check_integrity(broken, read_manifest(MANIFEST_CSV))
    assert any("SAFFIRE1:SIBAL: unknown source PSI-98" in p for p in problems)


def test_build_writes_parquet_duckdb_and_todo_csv(built):
    out, summary = built
    for t in ("sources", "evidence", "measurements", "claims", "relations"):
        assert (out / f"{t}.parquet").exists()
    assert (out / "ember.duckdb").exists() and (out / "review_todo.csv").exists()
    assert summary["counts"]["evidence"] == 14
    with (out / "review_todo.csv").open() as f:
        assert len(list(csv.DictReader(f))) == summary["review_todos"] > 0
    con = duckdb.connect(str(out / "ember.duckdb"), read_only=True)
    try:
        n = con.execute("SELECT count(*) FROM evidence").fetchone()[0]
        known = con.execute("SELECT count(*) FROM evidence WHERE x_o2_status = 'known'").fetchone()[
            0
        ]
    finally:
        con.close()
    assert n == 14 and known == 6


def test_parquet_roundtrip_preserves_models(built, models):
    out, _ = built
    reg = load_registry(out, build_if_missing=False)
    assert {e.evidence_id for e in reg.evidence} == {e.evidence_id for e in models["evidence"]}
    seed_by = {e.evidence_id: e for e in models["evidence"]}
    for e in reg.evidence:
        assert e == seed_by[e.evidence_id], e.evidence_id
    assert len(reg.sources) == len(models["sources"])
    assert len(reg.measurements) == len(models["measurements"])
    assert len(reg.claims) == len(models["claims"])
    assert reg.claims_for("BASS-II:LOC")[0].claim_type.value == "measured"
    assert {m.quantity for m in reg.measurements_for("DAFT:ISS_ambient")} == {
        "mass_conc_mg_m3",
        "particle_count_per_cc",
    }


def test_unknown_columns_are_explicitly_null_in_parquet(built):
    out, _ = built
    df = pd.read_parquet(out / "evidence.parquet").set_index("evidence_id")
    assert (
        pd.isna(df.loc["BASS:campaign", "x_o2_min"])
        and df.loc["BASS:campaign", "x_o2_status"] == "unknown"
    )
    assert df.loc["SAMER:runs", "x_o2_status"] == "not_applicable"


def test_ranking_over_seed_registry_demo_scenario(built):
    out, _ = built
    reg = load_registry(out, build_if_missing=False)
    s = {
        "x_o2": 0.34,
        "p_kpa": 56.5,
        "u_cms": None,
        "gravity_g0": 0.166,
        "phenomenon": "spread_opposed",
        "fuel_class": "thin_solid",
        "fuel_name": None,
    }
    ranked = rank(s, reg.evidence_dicts())
    ids = [r["evidence_id"] for r in ranked]
    assert "LUCI:overlay" not in ids  # overlay excluded from the pool
    s6 = next(r for r in ranked if r["evidence_id"] == "SAFFIRE6:SIBAL")
    assert s6["D"] == pytest.approx(0.084, abs=0.002)
    codes = {f.split(":")[0] for f in s6["flags"]}
    assert {"NON_PSI_SOURCE", "TENSION", "GRAVITY_EXTRAPOLATION"} <= codes
    # O2 and P are known and opposed spread has ε_u = 0, so nothing is missing → no lower-bound flag.
    assert "INCOMPLETE_CONDITIONS" not in codes and s6["D_lower_bound"] is False
    b2 = next(r for r in ranked if r["evidence_id"] == "BASS-II:campaign")
    assert b2["parts"]["x_o2"] == pytest.approx(
        0.9 * __import__("math").log(0.34 / 0.222), abs=1e-6
    )
    assert b2["D_lower_bound"] is True  # pressure unknown


def test_build_fails_loudly_on_integrity_problem(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "sources_seed.yaml").write_text("[]\n")
    (seed / "evidence_seed.yaml").write_text(
        "- evidence_id: X\n  investigation: X\n  hardware_family: h\n  fuel_class: thin_solid\n"
        "  phenomena: [ignition]\n  gravity: unknown\n  x_o2: {status: unknown}\n  p_kpa: {status: unknown}\n"
        "  u_cms: {status: unknown}\n  granularity: paper_only\n  sources: [NOPE]\n"
    )
    with pytest.raises(RegistryIntegrityError):
        build(seed, tmp_path / "out", MANIFEST_CSV)


# ---------------------------------------------------------------- full registry (seed + PSI tables)
def test_full_build_merges_extracted_tables(built_full):
    out, summary = built_full
    assert summary["evidence_from_seed"] == 14
    assert summary["evidence_from_tables"] == 968
    assert summary["counts"]["evidence"] == 982
    reg = load_registry(out, build_if_missing=False)
    ids = [e.evidence_id for e in reg.evidence]
    assert len(ids) == len(set(ids))
    extracted = [e for e in reg.evidence if e.evidence_id.startswith("PSI-")]
    assert {e.psi_id for e in extracted} == {
        "PSI-25",
        "PSI-26",
        "PSI-69",
        "PSI-100",
        "PSI-101",
        "PSI-159",
    }
    for e in extracted:
        for k in ("x_o2", "p_kpa", "u_cms", "size_cm"):
            r = getattr(e, k)
            if r is not None and r.status == "known":
                assert r.source_id == e.psi_id and "data row" in r.source_locator, (
                    e.evidence_id,
                    k,
                )
        if e.x_o2.status == "known" and e.o2_context.value == "ambient":
            assert 0.0 < e.x_o2.min <= e.x_o2.max < 0.5, e.evidence_id  # ambient O₂ never 85 %
    for m in reg.measurements:
        if m.measurement_id.startswith("M-PSI-69"):
            assert "data row" in m.source_locator


def test_burner_side_oxygen_never_enters_distance():
    reg = load_registry()
    inv = [e for e in reg.evidence if e.evidence_id.startswith("PSI-159:I:")]
    assert len(inv) == 154
    high = [e for e in inv if e.x_o2.status == "known" and e.x_o2.max == 0.85]
    assert high and all(e.o2_context.value == "burner_oxidizer_flow" for e in high)
    from ember.engine.score import evidence_to_dict, score

    d = evidence_to_dict(high[0])
    assert d["x_o2_min"] is None and d["x_o2_status"] == "burner_side_not_ambient"
    s = {
        "x_o2": 0.85,
        "p_kpa": d["p_kpa_min"],
        "u_cms": None,
        "gravity_g0": 0.0,
        "phenomenon": "flame_structure",
    }
    r = score(s, d)
    assert r["parts"]["x_o2"] is None and r["D_lower_bound"] is True
    assert any(f.startswith("BURNER_SIDE_O2") for f in r["flags"])
