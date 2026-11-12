import pytest
from pydantic import ValidationError

from ember.schemas import (
    Evidence,
    FuelClass,
    Granularity,
    GravityRegime,
    Measurement,
    O2Context,
    Phenomenon,
    Range,
    Scenario,
)


def test_known_range_without_provenance_raises():
    with pytest.raises(ValidationError):
        Range(min=0.2, max=0.3, status="known")


def test_known_range_with_provenance_ok():
    r = Range(min=0.2, max=0.3, status="known", source_id="PSI-25", source_locator="Table 1")
    assert r.is_known


def test_known_range_requires_min_le_max():
    with pytest.raises(ValidationError):
        Range(min=0.5, max=0.3, status="known", source_id="X", source_locator="Y")


def test_known_range_requires_both_bounds():
    with pytest.raises(ValidationError):
        Range(min=0.5, status="known", source_id="X", source_locator="Y")


def test_unknown_range_allows_partial_bounds():
    # "≤21%" → max known-ish but status stays unknown until the matrix is parsed
    r = Range(max=0.21, status="unknown")
    assert not r.is_known and r.min is None


def test_evidence_builds():
    e = Evidence(
        evidence_id="BASS-II:campaign",
        investigation="BASS-II",
        psi_id="PSI-25",
        hardware_family="MSG+SPICE-duct",
        fuel_class=FuelClass.thick_solid,
        phenomena=[Phenomenon.spread_opposed],
        gravity=GravityRegime.micro,
        x_o2=Range(min=0.136, max=0.222, status="known", source_id="PSI-25", source_locator="t"),
        o2_context=O2Context.ambient,
        p_kpa=Range.unknown(),
        u_cms=Range.unknown(),
        granularity=Granularity.per_test,
        sources=["PSI-25"],
    )
    assert e.measurements == [] and e.tensions == []


def test_evidence_requires_a_source():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="x",
            investigation="x",
            hardware_family="h",
            fuel_class=FuelClass.thin_solid,
            phenomena=[Phenomenon.ignition],
            gravity=GravityRegime.unknown,
            x_o2=Range.unknown(),
            p_kpa=Range.unknown(),
            u_cms=Range.unknown(),
            granularity=Granularity.paper_only,
            sources=[],
        )


def test_evidence_rejects_uncontrolled_measurement_name():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="x",
            investigation="x",
            hardware_family="h",
            fuel_class=FuelClass.thin_solid,
            phenomena=[Phenomenon.ignition],
            gravity=GravityRegime.unknown,
            x_o2=Range.unknown(),
            p_kpa=Range.unknown(),
            u_cms=Range.unknown(),
            granularity=Granularity.paper_only,
            measurements=["speed_of_fire"],
            sources=["PSI-1"],
        )


def test_propellant_is_not_a_fuel_class():
    # Spec §0.10 / §2: rockets/propellants are out of scope.
    with pytest.raises(ValueError):
        FuelClass("propellant")


def test_scenario_bounds():
    s = Scenario(x_o2=0.34, p_kpa=56.5, gravity_g0=0.166, phenomenon=Phenomenon.spread_opposed)
    assert s.name == "custom" and s.u_cms is None
    with pytest.raises(ValidationError):
        Scenario(x_o2=1.5, phenomenon=Phenomenon.spread_opposed)
    with pytest.raises(ValidationError):
        Scenario(p_kpa=0, phenomenon=Phenomenon.spread_opposed)


def test_measurement_vocab_enforced():
    with pytest.raises(ValidationError):
        Measurement(
            measurement_id="m1",
            evidence_id="e",
            quantity="not_a_quantity",
            value=1.0,
            unit="cm/s",
            value_kind="measured",
            source_id="s",
            source_locator="l",
        )
    m = Measurement(
        measurement_id="m1",
        evidence_id="e",
        quantity="loc_x_o2",
        value=0.17,
        unit="dimensionless",
        value_kind="measured",
        context="ambient",
        source_id="DOI:10.1038/s41598-017-18398-4",
        source_locator="TODO",
    )
    assert m.quantity == "loc_x_o2"
