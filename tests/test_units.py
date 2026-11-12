import pytest

from ember import units


def test_psi_to_kpa_exploration_atmosphere():
    # NASA/TP-2010-216134: 8.2 psia ≈ 56.5 kPa
    assert units.psi_to_kpa(8.2) == pytest.approx(56.54, abs=0.01)


def test_psi_to_kpa_10_2_option():
    assert units.psi_to_kpa(10.2) == pytest.approx(70.33, abs=0.01)


def test_percent_to_fraction():
    assert units.o2_to_fraction(34, "%") == pytest.approx(0.34)
    assert units.o2_to_fraction(21.0, "percent") == pytest.approx(0.21)


def test_bar_to_kpa():
    assert units.to_kpa(2, "bar") == pytest.approx(200.0)


def test_atm_to_kpa():
    assert units.to_kpa(1, "atm") == pytest.approx(101.325)


def test_mm_s_to_cm_s():
    assert units.to_cms(50, "mm/s") == pytest.approx(5.0)
    assert units.to_cms(0.1, "m/s") == pytest.approx(10.0)


def test_kpa_roundtrip_psi():
    assert units.kpa_to_psi(units.psi_to_kpa(14.7)) == pytest.approx(14.7)


def test_normalize_known():
    n = units.normalize(8.2, "psia", "p_kpa")
    assert n.status == "known"
    assert n.value == pytest.approx(56.54, abs=0.01)
    assert n.unit == "kPa"


def test_normalize_unknown_unit_does_not_raise():
    n = units.normalize(5, "blorps per zib", "u_cms")
    assert n.status == "unknown"
    assert n.value is None
    assert n.unit_as_written == "blorps per zib"


def test_normalize_wrong_dimension_is_unknown():
    n = units.normalize(5, "kPa", "u_cms")
    assert n.status == "unknown"


def test_normalize_missing_value():
    assert units.normalize(None, "kPa", "p_kpa").status == "unknown"


def test_normalize_unitless_o2_fraction_assumed():
    n = units.normalize(0.34, None, "x_o2")
    assert n.status == "known" and n.value == pytest.approx(0.34)
    # A unitless 34 is ambiguous (percent?) → unknown, never guessed.
    assert units.normalize(34, None, "x_o2").status == "unknown"


def test_ppo2():
    assert units.ppo2_kpa(0.34, 56.5) == pytest.approx(19.21)
