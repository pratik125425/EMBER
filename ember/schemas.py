"""Pydantic data model for the EMBER registry (spec §8).

Rules encoded here (spec §0):
- A ``Range`` with ``status="known"`` must carry ``source_id`` and ``source_locator``.
  Values without provenance never enter the registry.
- Unknown values stay unknown (``status="unknown"``, ``min``/``max`` may be ``None``).
- Rocket/propellant combustion is out of scope and is not representable in ``FuelClass``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Phenomenon(StrEnum):
    ignition = "ignition"
    spread_opposed = "spread_opposed"
    spread_concurrent = "spread_concurrent"
    extinction = "extinction"
    loc = "limiting_oxygen"
    suppression = "suppression"
    soot_smoke_point = "soot_smoke_point"
    smoke_particles = "smoke_particles"
    detector_response = "detector_response"
    burning_rate = "burning_rate"
    cool_flame = "cool_flame"
    flame_structure = "flame_structure"


class FuelClass(StrEnum):
    thin_solid = "thin_solid"
    thick_solid = "thick_solid"
    droplet = "liquid_droplet"
    gas_jet = "gas_jet"
    gas_emulator = "gaseous_emulator"
    pyrolysis_source = "pyrolysis_source"
    ambient_dust = "ambient_dust"


class GravityRegime(StrEnum):
    micro = "microgravity"
    one_g = "1g"
    sim_partial = "simulated_partial"
    unknown = "unknown"


class O2Context(StrEnum):
    ambient = "ambient"
    burner = "burner_oxidizer_flow"
    unknown = "unknown"


class Granularity(StrEnum):
    """Drives the Q prior (spec §10.4)."""

    per_test = "per_test_table"
    per_campaign = "campaign_summary"
    paper_only = "paper_only"


class ClaimType(StrEnum):
    measured = "measured"
    derived = "derived"
    modeled = "modeled"
    author_interp = "author_interpretation"
    system_inference = "system_inference"


FlowDirection = Literal["opposed", "concurrent", "quiescent", "coflow", "unknown"]
RangeStatus = Literal["known", "unknown", "not_applicable"]

# Controlled vocabulary for CompareLab measurements (spec §8).
MEASUREMENT_VOCAB: tuple[str, ...] = (
    "flame_spread_rate_cm_s",
    "extinction_flow_cm_s",
    "loc_x_o2",
    "extinction_diameter_mm",
    "burning_rate_K_mm2_s",
    "smoke_point_length_mm",
    "soot_volume_fraction",
    "particle_count_per_cc",
    "mass_conc_mg_m3",
    "detector_signal_V",
    "geom_mean_diameter_nm",
    "heat_flux_kW_m2",
    "surface_temperature_K",
    "flame_standoff_mm",
    "liftoff_height_mm",
)

ValueKind = Literal["measured", "set_point", "range", "computed"]
MeasurementContext = Literal["ambient", "burner", "cabin", "duct", "unknown"]


class Range(BaseModel):
    """A tested interval for one condition. Ranges stay ranges (spec §0.7)."""

    min: float | None = None
    max: float | None = None
    status: RangeStatus = "unknown"
    source_id: str | None = None
    source_locator: str | None = None  # "Table 2 row 14", "p.5 ¶3", "file.csv:col"

    @model_validator(mode="after")
    def _check(self) -> Range:
        if self.status == "known":
            if self.min is None or self.max is None:
                raise ValueError("known Range needs both min and max")
            if self.min > self.max:
                raise ValueError("known Range needs min <= max")
            if not self.source_id or not self.source_locator:
                raise ValueError("known values need provenance (source_id and source_locator)")
        return self

    @property
    def is_known(self) -> bool:
        return self.status == "known"

    @classmethod
    def unknown(cls) -> Range:
        return cls(status="unknown")

    @classmethod
    def not_applicable(cls) -> Range:
        return cls(status="not_applicable")


class Source(BaseModel):
    source_id: str  # e.g. "PSI-25", "NTRS-20240002981", "DOI:10.1038/s41598-017-18398-4"
    kind: Literal["psi_record", "psi_file", "ntrs", "journal", "challenge", "other"]
    title: str
    year: int | None = None
    url: str
    doi: str | None = None
    in_psi: bool
    sha256: str | None = None
    retrieved_at: str | None = None


class Evidence(BaseModel):
    """One test, test series, or campaign-level condition envelope."""

    evidence_id: str  # "PSI-25:T014", "PSI-25:campaign", "SAFFIRE6:PMMA"
    investigation: str  # "BASS-II"
    psi_id: str | None = None  # None for non-PSI sources (e.g. Saffire VI)
    hardware_family: str
    fuel_class: FuelClass
    fuel_name: str | None = None
    geometry: str | None = None
    size_cm: Range | None = None
    phenomena: list[Phenomenon]
    gravity: GravityRegime
    x_o2: Range  # mole fraction 0–1
    o2_context: O2Context = O2Context.unknown
    p_kpa: Range
    u_cms: Range  # imposed flow velocity
    flow_direction: FlowDirection | None = "unknown"
    diluent: str | None = None  # N2/CO2/He/Xe
    enclosure_note: str | None = None  # e.g. "Saffire duct half-height 15 cm"
    granularity: Granularity
    measurements: list[str] = Field(default_factory=list)  # canonical quantity names
    tensions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(min_length=1)  # source_ids

    @model_validator(mode="after")
    def _check(self) -> Evidence:
        bad = [m for m in self.measurements if m not in MEASUREMENT_VOCAB]
        if bad:
            raise ValueError(f"measurements not in controlled vocabulary: {bad}")
        return self


class Measurement(BaseModel):
    """A measured/set/derived quantity attached to an evidence record (spec §8, §10.7)."""

    measurement_id: str
    evidence_id: str
    quantity: str  # one of MEASUREMENT_VOCAB
    value: float | None = None
    min: float | None = None
    max: float | None = None
    unit: str
    value_kind: ValueKind
    context: MeasurementContext = "unknown"
    source_id: str
    source_locator: str
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Measurement:
        if self.quantity not in MEASUREMENT_VOCAB:
            raise ValueError(f"quantity {self.quantity!r} not in controlled vocabulary")
        if self.value is None and (self.min is None or self.max is None):
            raise ValueError("Measurement needs a value or a min/max pair")
        return self


class Claim(BaseModel):
    claim_id: str
    evidence_id: str | None = None
    text: str
    claim_type: ClaimType
    source_id: str
    source_locator: str


class Relation(BaseModel):
    """Edge between registry entities (e.g. SAME ↔ DAFT instrument link, shared hardware)."""

    relation_id: str
    from_id: str
    to_id: str
    kind: Literal["shared_hardware", "instrument_link", "reflight", "related_study", "other"]
    source_id: str
    note: str | None = None


class Scenario(BaseModel):
    """Produced by the LLM parser or UI sliders; ALWAYS user-confirmed before ranking."""

    name: str = "custom"
    x_o2: float | None = Field(None, ge=0.0, le=1.0)
    p_kpa: float | None = Field(None, gt=0)
    u_cms: float | None = Field(None, ge=0)
    gravity_g0: float | None = Field(None, ge=0)  # 0, 0.166, 0.38, 1
    phenomenon: Phenomenon
    fuel_class: FuelClass | None = None
    fuel_name: str | None = None
    flow_direction: str | None = None
    notes: str | None = None
