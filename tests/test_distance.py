from math import exp

import pytest

from ember.engine.distance import interval_log_distance, transfer_distance
from tests.conftest import ev


def test_inside_interval_is_zero():
    assert interval_log_distance(0.2, 0.136, 0.222) == 0.0
    assert interval_log_distance(0.136, 0.136, 0.222) == 0.0  # edges inclusive
    assert interval_log_distance(0.222, 0.136, 0.222) == 0.0


def test_outside_interval_is_log_distance_to_nearest_edge():
    assert interval_log_distance(0.34, 0.136, 0.222) == pytest.approx(
        abs(__import__("math").log(0.34 / 0.222))
    )
    assert interval_log_distance(0.10, 0.136, 0.222) == pytest.approx(
        abs(__import__("math").log(0.10 / 0.136))
    )


def test_nonpositive_values_raise():
    with pytest.raises(ValueError):
        interval_log_distance(0.0, 0.1, 0.2)


# ---- Worked example (spec §10.8), hand-calculated; must be reproduced -------------------------


def test_worked_example_bass2_opposed(exploration_scenario, bass2_point):
    D, lb, parts = transfer_distance(exploration_scenario, bass2_point, "spread_opposed")
    assert D == pytest.approx(0.463, abs=0.002)
    assert exp(D) == pytest.approx(1.59, abs=0.01)
    assert lb is False
    assert parts["x_o2"] == pytest.approx(0.4336, abs=0.001)
    assert parts["p_kpa"] == pytest.approx(0.0290, abs=0.001)
    assert "u_cms" not in parts  # ε_u = 0 for opposed spread → dimension skipped


def test_worked_example_bass2_concurrent_ignoring_u(exploration_scenario, bass2_point):
    s = dict(exploration_scenario, phenomenon="spread_concurrent")  # u_cms None → ignored
    D, lb, parts = transfer_distance(s, bass2_point, "spread_concurrent")
    assert D == pytest.approx(0.772, abs=0.002)
    assert exp(D) == pytest.approx(2.16, abs=0.01)
    assert lb is False


def test_worked_example_saffire6_point(exploration_scenario, saffire6_point):
    D, _, _ = transfer_distance(exploration_scenario, saffire6_point, "spread_opposed")
    assert D == pytest.approx(0.085, abs=0.002)
    assert exp(D) == pytest.approx(1.09, abs=0.01)


def test_worked_example_saffire6_interval(exploration_scenario, saffire6_interval):
    D, _, _ = transfer_distance(exploration_scenario, saffire6_interval, "spread_opposed")
    assert D == pytest.approx(0.084, abs=0.002)


def test_u_floor_for_quiescent_tests():
    s = {"x_o2": 0.21, "p_kpa": 101.3, "u_cms": 0.0, "phenomenon": "spread_concurrent"}
    e = ev(
        x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.3, p_kpa_max=101.3, u_cms_min=0.0, u_cms_max=0.0
    )
    D, lb, parts = transfer_distance(s, e, "spread_concurrent")
    assert D == 0.0 and parts["u_cms"] == 0.0  # both floored to U_FLOOR → no log(0)


def test_unknown_phenomenon_uses_uniform_weights():
    s = {"x_o2": 0.34, "p_kpa": 56.5, "u_cms": None, "phenomenon": "ignition"}
    e = ev(x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.0, p_kpa_max=101.0)
    D, _, parts = transfer_distance(s, e, "ignition")
    assert parts["x_o2"] == pytest.approx(0.4818, abs=0.001)
    assert parts["p_kpa"] == pytest.approx(0.5809, abs=0.001)
