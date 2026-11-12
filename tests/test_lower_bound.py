import pytest

from ember.engine.distance import transfer_distance
from tests.conftest import ev


def test_missing_o2_sets_lower_bound_and_excludes_dimension(exploration_scenario):
    e = ev(p_kpa_min=101.0, p_kpa_max=101.0)  # x_o2 unknown
    D, lb, parts = transfer_distance(exploration_scenario, e, "spread_opposed")
    assert lb is True
    assert parts["x_o2"] is None
    assert D == pytest.approx(0.05 * abs(__import__("math").log(101.0 / 56.5)), abs=1e-6)


def test_missing_scenario_dimension_is_not_a_lower_bound(bass2_point):
    # Scenario omits pressure → we simply don't ask about it; evidence completeness is unaffected.
    s = {"x_o2": 0.34, "p_kpa": None, "u_cms": None, "phenomenon": "spread_opposed"}
    D, lb, parts = transfer_distance(s, bass2_point, "spread_opposed")
    assert lb is False and "p_kpa" not in parts


def test_all_unknown_evidence_gives_zero_D_but_lower_bound(exploration_scenario):
    D, lb, parts = transfer_distance(exploration_scenario, ev(), "spread_opposed")
    assert D == 0.0 and lb is True
    assert parts == {"x_o2": None, "p_kpa": None}
