from ember.engine.flags import flag_code, flags_for
from ember.engine.score import score
from tests.conftest import ev


def codes(flags):
    return {flag_code(f) for f in flags}


def test_partial_gravity_sets_gravity_flag():
    s = {"gravity_g0": 0.166}
    assert "GRAVITY_EXTRAPOLATION" in codes(flags_for(s, ev(), D=0.0, lb=False))
    assert "GRAVITY_EXTRAPOLATION" in codes(flags_for({"gravity_g0": 0.38}, ev(), 0.0, False))


def test_bracket_gravities_do_not_flag():
    assert "GRAVITY_EXTRAPOLATION" not in codes(flags_for({"gravity_g0": 0.0}, ev(), 0.0, False))
    assert "GRAVITY_EXTRAPOLATION" not in codes(flags_for({"gravity_g0": 1.0}, ev(), 0.0, False))
    assert "GRAVITY_EXTRAPOLATION" not in codes(flags_for({"gravity_g0": None}, ev(), 0.0, False))


def test_burner_context_flags_burner_side_o2():
    e = ev(o2_context="burner_oxidizer_flow")
    assert "BURNER_SIDE_O2" in codes(flags_for({}, e, 0.0, False))
    assert "BURNER_SIDE_O2" not in codes(flags_for({}, ev(o2_context="ambient"), 0.0, False))


def test_envelope_flag_when_D_exceeds_one():
    assert "BEYOND_TESTED_ENVELOPE" in codes(flags_for({}, ev(), 1.01, False))
    assert "BEYOND_TESTED_ENVELOPE" not in codes(flags_for({}, ev(), 1.0, False))


def test_lower_bound_flag():
    assert "INCOMPLETE_CONDITIONS" in codes(flags_for({}, ev(), 0.0, True))


def test_non_psi_and_tension_flags():
    e = ev(psi_id=None, tensions=["Spread higher than model predicted"])
    f = flags_for({}, e, 0.0, False)
    assert "NON_PSI_SOURCE" in codes(f)
    assert any(x.startswith("TENSION: Spread higher") for x in f)


def test_unweighted_flag_through_score():
    s = {"x_o2": 0.21, "p_kpa": 101.3, "u_cms": None, "gravity_g0": 0.0, "phenomenon": "ignition"}
    r = score(
        s,
        ev(phenomena=["ignition"], x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.3, p_kpa_max=101.3),
    )
    assert r["weighted"] is False and "UNWEIGHTED" in codes(r["flags"])
    r2 = score(
        dict(s, phenomenon="spread_opposed"),
        ev(x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.3, p_kpa_max=101.3),
    )
    assert r2["weighted"] is True and "UNWEIGHTED" not in codes(r2["flags"])
