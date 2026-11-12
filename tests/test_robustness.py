"""T08: Monte Carlo rank stability."""

import json

import numpy as np
import pytest

from ember import config
from ember.engine.robustness import cached_rank_stability, perturb, rank_stability
from ember.engine.score import rank
from ember.registry import load_registry

S = {
    "x_o2": 0.34,
    "p_kpa": 56.5,
    "u_cms": None,
    "gravity_g0": 0.166,
    "phenomenon": "spread_opposed",
    "fuel_class": "thin_solid",
    "fuel_name": None,
}


@pytest.fixture(scope="module")
def evidence():
    return load_registry().evidence_dicts()


def test_perturb_respects_zero_weights_and_anchors():
    rng = np.random.default_rng(1)
    for _ in range(50):
        p = perturb(rng, prior_pct=0.5, eps_pct=0.3)
        assert (
            p["elasticity"]["spread_opposed"]["u_cms"] == 0.0
        )  # no flow term in Ruff 2021 → never invented
        assert 0.9 * 0.7 <= p["elasticity"]["spread_opposed"]["x_o2"] <= 0.9 * 1.3
        assert (
            p["m_phi"]["exact"] == 1.0
            and p["m_f"]["same_class_same_material"] == 1.0
            and p["q_prior"]["per_test_table"] == 1.0
        )
        assert 0.5 * 0.5 <= p["m_phi"]["related"] <= min(1.0, 0.5 * 1.5)
        assert all(0.01 <= v <= 1.0 for t in ("m_phi", "m_f", "q_prior") for v in p[t].values())


def test_deterministic_with_seed(evidence):
    a = rank_stability(S, evidence, n=50, seed=3)
    b = rank_stability(S, evidence, n=50, seed=3)
    assert a == b
    c = rank_stability(S, evidence, n=50, seed=4)
    assert c["base_order"] == a["base_order"]  # base ranking never depends on the seed


def test_p_topk_in_unit_interval_and_sums_to_k(evidence):
    r = rank_stability(S, evidence, n=200, seed=0)
    assert all(0.0 <= p <= 1.0 for p in r["p_topk"].values())
    assert sum(r["p_topk"].values()) == pytest.approx(r["k"])
    assert set(r["p_topk"]) == {
        e["evidence_id"] for e in evidence if e["gravity"] != "simulated_partial"
    }
    assert (
        -1.0 <= r["kendall_tau_ci"][0] <= r["kendall_tau_median"] <= r["kendall_tau_ci"][1] <= 1.0
    )


def test_zero_perturbation_reproduces_base_ranking_exactly(evidence):
    r = rank_stability(S, evidence, n=20, prior_pct=0.0, eps_pct=0.0)
    base = [x["evidence_id"] for x in rank(S, evidence)]
    assert r["base_order"] == base
    assert all(r["p_topk"][eid] == 1.0 for eid in base[:5])
    assert all(r["p_topk"][eid] == 0.0 for eid in base[5:])
    assert r["kendall_tau_median"] == pytest.approx(1.0)
    assert all(r["rank_min"][eid] == r["rank_max"][eid] == i for i, eid in enumerate(base, start=1))


def test_stable_flag_uses_threshold(evidence):
    r = rank_stability(S, evidence, n=100)
    for eid, p in r["p_topk"].items():
        assert r["stable"][eid] == (p >= config.STABLE_P_TOPK)
    # In the seed registry the top record is far ahead on R → stable under ±30%/±50% perturbation.
    assert r["stable"][r["base_order"][0]] is True


def test_cache_roundtrip(tmp_path, evidence):
    r1, hit1 = cached_rank_stability(S, evidence, cache_dir=tmp_path, n=30)
    r2, hit2 = cached_rank_stability(S, evidence, cache_dir=tmp_path, n=30)
    assert (hit1, hit2) == (False, True) and r1 == r2
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1 and json.loads(files[0].read_text())["n"] == 30
    # A different scenario or parameter set gets its own cache entry.
    _, hit3 = cached_rank_stability(dict(S, x_o2=0.21), evidence, cache_dir=tmp_path, n=30)
    _, hit4 = cached_rank_stability(S, evidence, cache_dir=tmp_path, n=31)
    assert hit3 is False and hit4 is False and len(list(tmp_path.glob("*.json"))) == 3


def test_collapse_keeps_best_record_per_investigation(evidence):
    from ember.engine.score import collapse

    full = rank(S, evidence)
    grouped = collapse(full)
    invs = [r["investigation"] for r in grouped]
    assert len(invs) == len(set(invs))
    assert [r["rank"] for r in grouped] == list(range(1, len(grouped) + 1))
    assert sum(r["n_group"] for r in grouped) == len(full)
    first = {}
    for r in full:
        first.setdefault(r["investigation"], r["evidence_id"])
    assert all(first[r["investigation"]] == r["evidence_id"] for r in grouped)


def test_grouped_stability_is_keyed_by_investigation(evidence):
    r = rank_stability(S, evidence, n=40, group_by="investigation")
    invs = {e["investigation"] for e in evidence if e["gravity"] != "simulated_partial"}
    assert set(r["p_topk"]) == invs
    assert sum(r["p_topk"].values()) == pytest.approx(r["k"])
    assert r["params"]["group_by"] == "investigation"
