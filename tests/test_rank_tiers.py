"""Ranking tiers: data-free records go below records with at least one known condition."""

from ember import config
from ember.engine.score import completeness_tier, rank, score
from tests.conftest import ev

S = {
    "x_o2": 0.34,
    "p_kpa": 56.5,
    "u_cms": None,
    "gravity_g0": None,
    "phenomenon": "spread_opposed",
    "fuel_class": None,
    "fuel_name": None,
}


def test_tier_classification():
    assert completeness_tier({"x_o2": 0.1, "p_kpa": 0.0}) == config.TIER_COMPLETE
    assert completeness_tier({"x_o2": 0.1, "p_kpa": None}) == config.TIER_PARTIAL
    assert completeness_tier({"x_o2": None, "p_kpa": None}) == config.TIER_NO_CONDITIONS
    assert completeness_tier({}) == config.TIER_COMPLETE  # scenario asked nothing


def test_score_reports_tier():
    assert score(S, ev())["tier"] == config.TIER_NO_CONDITIONS
    assert score(S, ev(x_o2_min=0.3, x_o2_max=0.3))["tier"] == config.TIER_PARTIAL


def test_data_free_record_ranks_below_records_with_data_despite_higher_R():
    empty = ev("EMPTY")  # D = 0 → R = 1.0, but nothing is known
    far = ev("FAR", x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.0, p_kpa_max=101.0)  # R ≈ 0.63
    partial = ev("PARTIAL", x_o2_min=0.21, x_o2_max=0.21)  # R ≈ 0.65, pressure unknown
    ranked = rank(S, [empty, far, partial])
    assert [r["evidence_id"] for r in ranked] == ["PARTIAL", "FAR", "EMPTY"]
    assert ranked[-1]["R"] == 1.0  # R is untouched; only the position changes
    assert ranked[-1]["tier"] == config.TIER_NO_CONDITIONS


def test_partial_and_complete_rank_together_by_R():
    # A partial record with real data is NOT demoted below a complete but irrelevant one.
    partial_good = ev("P", x_o2_min=0.34, x_o2_max=0.34)  # D=0 on O2, P unknown → R=1.0
    complete_far = ev("C", x_o2_min=0.15, x_o2_max=0.15, p_kpa_min=101.0, p_kpa_max=101.0)
    assert [r["evidence_id"] for r in rank(S, [complete_far, partial_good])] == ["P", "C"]


def test_demotion_can_be_disabled(monkeypatch):
    monkeypatch.setattr(config, "DEMOTE_NO_CONDITION_EVIDENCE", False)
    empty, far = (
        ev("EMPTY"),
        ev("FAR", x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.0, p_kpa_max=101.0),
    )
    assert [r["evidence_id"] for r in rank(S, [empty, far])] == ["EMPTY", "FAR"]
