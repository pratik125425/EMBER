"""Shared pytest fixtures."""

import pytest


def ev(evidence_id="E", **kw):
    """Minimal engine-shaped evidence dict with sensible defaults."""
    base = {
        "evidence_id": evidence_id,
        "investigation": evidence_id,
        "psi_id": "PSI-0",
        "hardware_family": "test",
        "fuel_class": "thick_solid",
        "fuel_name": "PMMA",
        "phenomena": ["spread_opposed"],
        "gravity": "microgravity",
        "o2_context": "ambient",
        "granularity": "per_test_table",
        "tensions": [],
        "x_o2_min": None,
        "x_o2_max": None,
        "p_kpa_min": None,
        "p_kpa_max": None,
        "u_cms_min": None,
        "u_cms_max": None,
    }
    base.update(kw)
    return base


@pytest.fixture
def exploration_scenario():
    """Opposed-flow spread at the NASA Exploration Atmosphere (spec §10.8)."""
    return {
        "x_o2": 0.34,
        "p_kpa": 56.5,
        "u_cms": None,
        "gravity_g0": None,
        "phenomenon": "spread_opposed",
        "fuel_class": None,
        "fuel_name": None,
    }


@pytest.fixture
def bass2_point():
    return ev("BASS-II-like", x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.0, p_kpa_max=101.0)


@pytest.fixture
def saffire6_point():
    return ev(
        "SAFFIRE6-pt",
        psi_id=None,
        x_o2_min=0.31,
        x_o2_max=0.31,
        p_kpa_min=54.1,
        p_kpa_max=54.1,
        phenomena=["spread_concurrent", "spread_opposed"],
        fuel_class="thin_solid",
        fuel_name="SIBAL",
        granularity="paper_only",
        tensions=["Flame spread higher than in Saffire IV although prior model predicted lower"],
    )


@pytest.fixture
def saffire6_interval():
    return ev(
        "SAFFIRE6-iv",
        psi_id=None,
        x_o2_min=0.288,
        x_o2_max=0.310,
        p_kpa_min=54.1,
        p_kpa_max=55.2,
        phenomena=["spread_concurrent", "spread_opposed"],
        fuel_class="thin_solid",
        granularity="paper_only",
    )


@pytest.fixture(autouse=True)
def _no_live_llm(monkeypatch):
    """Tests never call a live LLM: only cached answers or deterministic fallbacks."""
    monkeypatch.setenv("EMBER_LLM_OFFLINE", "1")
