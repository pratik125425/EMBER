"""EMBER configuration: elasticities, priors, grids, target atmospheres (spec §3, §10, §13).

Every numeric constant here is either (a) a published correlation exponent with its source,
(b) a NASA target atmosphere with its source, or (c) a disclosed ordinal prior / UI grid choice
that is explicitly labeled as such and is sensitivity-tested (spec §10.5).
"""

from __future__ import annotations

# --------------------------------------------------------------------------------------------
# Elasticities ε = ∂lnY/∂lnx. Source: Ruff, "Technology Development for Spacecraft Fire
# Safety", NASA 2021, NTRS 20210021318 (microgravity flame-spread correlations).
#   opposed-flow spread:     V_f ∝ X_O2^0.9 · P^0.05
#   concurrent-flow spread:  V_f ∝ X_O2 · u · P^0.5
# Opposed spread keeps ε_u = 0 because the published correlation has no flow term; BASS-II
# shows a non-monotonic u dependence (Link et al. 2018, doi:10.1038/s41598-017-18398-4),
# so a constant elasticity would be wrong there anyway. The UI shows a tooltip about this.
# --------------------------------------------------------------------------------------------
DIMS: tuple[str, ...] = ("x_o2", "p_kpa", "u_cms")

ELASTICITY: dict[str, dict[str, float]] = {
    "spread_opposed": {"x_o2": 0.9, "p_kpa": 0.05, "u_cms": 0.0},
    "spread_concurrent": {"x_o2": 1.0, "p_kpa": 0.5, "u_cms": 1.0},
}
ELASTICITY_SOURCE = "NTRS-20210021318"

# Phenomena without a published correlation use uniform weights and get an "unweighted"
# badge in the UI (spec §10.2). This is a disclosed choice, not physics.
UNIFORM: dict[str, float] = {"x_o2": 1.0, "p_kpa": 1.0, "u_cms": 1.0}

# Floor for flow velocity to avoid log(0) for quiescent tests (spec §10.1). Documented choice.
U_FLOOR_CMS: float = 0.1

# --------------------------------------------------------------------------------------------
# Relevance priors (spec §10.4). Disclosed ordinal priors, NOT physics. Sensitivity-tested in
# robustness.py by perturbing them ±PRIOR_PCT.
# --------------------------------------------------------------------------------------------
M_PHI: dict[str, float] = {"exact": 1.0, "related": 0.5, "other": 0.1}
M_F: dict[str, float] = {"same_class_same_material": 1.0, "same_class": 0.6, "different": 0.3}
Q_PRIOR: dict[str, float] = {"per_test_table": 1.0, "campaign_summary": 0.6, "paper_only": 0.3}

# Phenomenon pairs considered "related" (symmetric). Spec §10.4.
RELATED: frozenset[tuple[str, str]] = frozenset(
    {
        ("spread_opposed", "spread_concurrent"),
        ("spread_opposed", "extinction"),
        ("spread_concurrent", "extinction"),
        ("smoke_particles", "detector_response"),
        ("extinction", "suppression"),
        ("limiting_oxygen", "spread_opposed"),
        ("limiting_oxygen", "extinction"),
        ("cool_flame", "extinction"),
    }
)

# Flag thresholds (spec §10.5).
D_ENVELOPE_THRESHOLD: float = 1.0  # exp(D) > e ≈ 2.7× → BEYOND_TESTED_ENVELOPE
STABLE_P_TOPK: float = 0.8  # "stable" badge if in top-k in ≥80% of perturbations

# Monte Carlo defaults (spec §10.5).
MC_N: int = 1000
MC_PRIOR_PCT: float = 0.5
MC_EPS_PCT: float = 0.3
MC_K: int = 5
MC_SEED: int = 0

# --------------------------------------------------------------------------------------------
# Gravity (spec §3.6, Appendix C). Gravity is a FLAG, never a distance term.
# --------------------------------------------------------------------------------------------
G_MICRO: float = 0.0
G_MOON: float = 0.166
G_MARS: float = 0.38
G_EARTH: float = 1.0
BRACKET_GRAVITIES: tuple[float, float] = (G_MICRO, G_EARTH)  # the only regimes with PSI data

# --------------------------------------------------------------------------------------------
# NASA target atmospheres (spec §3.5, §10.6). Sources:
#   ISS/Earth: sea-level air, 21% / 101.3 kPa.
#   10.2 psia option: 26.5% O2 at 10.2 psia (70.3 kPa)  [NASA/TP-2010-216134]
#   Exploration Atmosphere: 34% O2 at 8.2 psia (56.5 kPa), control box 33.5–35%
#       [NASA/TP-2010-216134; HRP ExpAtm evidence report]
# --------------------------------------------------------------------------------------------
TARGETS: list[tuple[str, float, float]] = [
    ("ISS/Earth", 0.21, 101.3),
    ("10.2 psia option", 0.265, 70.3),
    ("Exploration Atm 8.2/34", 0.34, 56.5),
]
TARGET_SOURCE = "NASA/TP-2010-216134"
# Tolerance box around each target used by the priority heuristic π (spec §10.6). The O2 half-
# width follows the 33.5–35% control box (±0.0075 ≈ ±0.75 pct-points); pressure ±5% is a UI
# choice. π is labeled a heuristic, not information gain.
TARGET_TOL_X_O2: float = 0.0075
TARGET_TOL_P_FRAC: float = 0.05
PRIORITY_OUTSIDE_TARGET: float = 0.25

# GapScope grid (spec §10.6).
GAP_X_O2 = (0.15, 0.40, 26)  # linspace(min, max, n)
GAP_P_KPA = (30.0, 105.0, 20)  # geomspace(min, max, n)
GAP_U_CMS: tuple[float, ...] = (0.0, 1.0, 5.0, 10.0, 20.0, 40.0)
GAP_G: tuple[float, ...] = (G_MICRO, G_MOON, G_MARS, G_EARTH)

# --------------------------------------------------------------------------------------------
# Scenario presets (spec §13). [A] marks an assumption shown in the UI.
# --------------------------------------------------------------------------------------------
PRESETS: dict[str, dict] = {
    "ISS": {"x_o2": 0.21, "p_kpa": 101.3, "gravity_g0": G_MICRO, "source": "sea-level air"},
    "Exploration Atmosphere (Moon)": {
        "x_o2": 0.34,
        "p_kpa": 56.5,
        "gravity_g0": G_MOON,
        "source": TARGET_SOURCE,
    },
    "10.2 psia option": {
        "x_o2": 0.265,
        "p_kpa": 70.3,
        "gravity_g0": G_MOON,
        "source": TARGET_SOURCE,
    },
    "Mars habitat [user-entered]": {
        "x_o2": None,
        "p_kpa": None,
        "gravity_g0": G_MARS,
        "source": "[A] no NASA target atmosphere seeded; user enters values",
    },
    "Pressurized rover [A]": {
        "x_o2": 0.34,
        "p_kpa": 56.5,
        "gravity_g0": G_MOON,
        "source": "[A] assumed = Exploration Atmosphere",
    },
}

# Non-PSI partial-gravity overlays for GapScope (spec §10.6). Facts only; not ranking evidence.
PARTIAL_G_OVERLAYS: list[dict] = [
    {
        "name": "LUCI (New Shepard centrifuge)",
        "gravity_g0": 0.165,
        "x_o2": 0.209,  # "air" per NTRS 20250010653; confirm before promoting to registry
        "p_kpa": 101.3,  # "normal pressure" per NTRS 20250010653; confirm
        "status": "non-PSI, flown",
        "source_id": "NTRS-20250010653",
    },
    {
        "name": "FM2 (Flammability of Materials on the Moon)",
        "gravity_g0": G_MOON,
        "x_o2": 0.34,
        "p_kpa": 56.5,
        "status": "non-PSI, planned (CLPS CP-21, late 2026), data pending",
        "source_id": "NTRS-20240015307",
    },
]

# --------------------------------------------------------------------------------------------
# Ranking tiers (disclosed ranking rule, decided 2026-11-11). Unknown dimensions contribute 0
# to D, so a record with NO known conditions would tie D = 0 with a perfect match. Records
# where none of the scenario's weighted dimensions are known are therefore placed BELOW every
# record that has at least one known condition. R itself is untouched; the tier is shown.
# --------------------------------------------------------------------------------------------
DEMOTE_NO_CONDITION_EVIDENCE: bool = True
TIER_COMPLETE = "complete"  # every weighted dimension the scenario asked about is known
TIER_PARTIAL = "partial"  # some known, some unknown → D is a lower bound
TIER_NO_CONDITIONS = "no_conditions"  # none known → D carries no information

# UI palette for the "why" bars (one hue per distance dimension; validated colorblind-safe).
WHY_BAR_COLORS: dict[str, str] = {"x_o2": "#2a78d6", "p_kpa": "#eb6834", "u_cms": "#1baf7a"}
SCENARIO_ACCENT: str = "#6250d6"
