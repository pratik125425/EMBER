import numpy as np
import pytest

from ember import config
from ember.engine.score import evidence_to_dict, m_f, m_phi, rank, scenario_to_dict, score
from ember.schemas import (
    Evidence,
    FuelClass,
    Granularity,
    GravityRegime,
    Phenomenon,
    Range,
    Scenario,
)
from tests.conftest import ev

E = ev("E", x_o2_min=0.20, x_o2_max=0.22, p_kpa_min=100.0, p_kpa_max=102.0)


def S(x, p, phen="spread_opposed", **kw):
    base = {
        "x_o2": x,
        "p_kpa": p,
        "u_cms": None,
        "gravity_g0": None,
        "phenomenon": phen,
        "fuel_class": None,
        "fuel_name": None,
    }
    base.update(kw)
    return base


def test_monotonic_moving_toward_evidence_never_lowers_R():
    # Walk O2 from 0.40 down to the evidence interval; R must be non-decreasing.
    Rs = [score(S(x, 101.0), E)["R"] for x in np.linspace(0.40, 0.21, 40)]
    assert all(b >= a - 1e-12 for a, b in zip(Rs, Rs[1:], strict=False))
    # Same for pressure, from 40 kPa up to the interval.
    Rs = [score(S(0.21, p), E)["R"] for p in np.linspace(40.0, 101.0, 40)]
    assert all(b >= a - 1e-12 for a, b in zip(Rs, Rs[1:], strict=False))


def test_R_is_one_inside_envelope_with_exact_match():
    r = score(S(0.21, 101.0), E)
    assert r["D"] == 0.0 and r["R"] == pytest.approx(1.0)


def test_q_prior_applied():
    paper = ev(
        "P",
        granularity="paper_only",
        x_o2_min=0.20,
        x_o2_max=0.22,
        p_kpa_min=100.0,
        p_kpa_max=102.0,
    )
    assert score(S(0.21, 101.0), paper)["R"] == pytest.approx(config.Q_PRIOR["paper_only"])


def test_m_phi_values():
    assert m_phi("spread_opposed", ["spread_opposed"]) == 1.0
    assert m_phi("spread_opposed", ["extinction"]) == 0.5  # related
    assert m_phi("limiting_oxygen", ["spread_opposed"]) == 0.5  # symmetric
    assert m_phi("smoke_particles", ["spread_opposed"]) == 0.1


def test_m_f_values():
    assert m_f(None, None, "thick_solid", "PMMA") == 1.0  # scenario silent on fuel
    assert m_f("thick_solid", "PMMA", "thick_solid", "PMMA rod") == 1.0
    assert m_f("thick_solid", "PMMA", "thick_solid", "Nomex") == 0.6
    assert m_f("thick_solid", None, "thick_solid", "PMMA") == 0.6
    assert m_f("thin_solid", "SIBAL", "liquid_droplet", "heptane") == 0.3


def test_score_combines_priors_and_distance():
    e = ev(
        "X",
        phenomena=["extinction"],
        fuel_class="thin_solid",
        fuel_name="SIBAL",
        granularity="campaign_summary",
        x_o2_min=0.20,
        x_o2_max=0.22,
        p_kpa_min=100.0,
        p_kpa_max=102.0,
    )
    r = score(S(0.21, 101.0, fuel_class="thick_solid"), e)
    assert r["R"] == pytest.approx(0.5 * 0.3 * 0.6)
    assert r["priors"] == {"m_phi": 0.5, "m_f": 0.3, "Q": 0.6}


def test_rank_orders_by_R_and_excludes_partial_g_overlay(
    exploration_scenario, bass2_point, saffire6_point
):
    luci = ev(
        "LUCI",
        gravity="simulated_partial",
        psi_id=None,
        x_o2_min=0.34,
        x_o2_max=0.34,
        p_kpa_min=56.5,
        p_kpa_max=56.5,
    )
    ranked = rank(exploration_scenario, [bass2_point, saffire6_point, luci])
    ids = [r["evidence_id"] for r in ranked]
    assert "LUCI" not in ids
    # Saffire VI is closer in D but paper_only (Q=0.3) vs per-test (Q=1.0): exp(-0.085)*0.3 < exp(-0.463)*1.0
    assert ids == ["BASS-II-like", "SAFFIRE6-pt"]
    assert [r["rank"] for r in ranked] == [1, 2]
    assert "NON_PSI_SOURCE" in [f.split(":")[0] for f in ranked[1]["flags"]]
    assert len(rank(exploration_scenario, [luci], include_partial_g=True)) == 1


def test_rank_is_deterministic_on_ties():
    a = ev("B", x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.0, p_kpa_max=101.0)
    b = ev("A", x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.0, p_kpa_max=101.0)
    assert [r["evidence_id"] for r in rank(S(0.21, 101.0), [a, b])] == ["A", "B"]


def test_adapters_from_pydantic_models():
    e = Evidence(
        evidence_id="BASS-II:campaign",
        investigation="BASS-II",
        psi_id="PSI-25",
        hardware_family="MSG+SPICE-duct",
        fuel_class=FuelClass.thick_solid,
        fuel_name="PMMA",
        phenomena=[Phenomenon.spread_opposed],
        gravity=GravityRegime.micro,
        x_o2=Range(min=0.136, max=0.222, status="known", source_id="PSI-25", source_locator="t"),
        p_kpa=Range.unknown(),
        u_cms=Range(max=40, status="unknown"),
        granularity=Granularity.per_test,
        sources=["PSI-25"],
    )
    d = evidence_to_dict(e)
    assert d["x_o2_min"] == 0.136 and d["x_o2_max"] == 0.222 and d["x_o2_status"] == "known"
    assert (
        d["p_kpa_min"] is None and d["u_cms_max"] is None
    )  # unknown ranges never leak partial bounds
    s = scenario_to_dict(
        Scenario(x_o2=0.34, p_kpa=56.5, gravity_g0=0.166, phenomenon=Phenomenon.spread_opposed)
    )
    r = score(s, d)
    assert r["D_lower_bound"] is True  # pressure unknown in evidence
    assert any(f.startswith("GRAVITY_EXTRAPOLATION") for f in r["flags"])
    assert r["parts"]["x_o2"] == pytest.approx(0.9 * np.log(0.34 / 0.222), abs=1e-6)
