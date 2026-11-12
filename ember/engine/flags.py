"""Flags attached to each (scenario, evidence) result (spec §10.5)."""

from __future__ import annotations

from ember.config import BRACKET_GRAVITIES, D_ENVELOPE_THRESHOLD

GRAVITY_EXTRAPOLATION = (
    "GRAVITY_EXTRAPOLATION: evidence is µg/1-g; partial-g behavior may lie OUTSIDE both "
    "(FM2 abstract NTRS 20240015307; Ruff 2021 NTRS 20210021318)."
)
BEYOND_TESTED_ENVELOPE = "BEYOND_TESTED_ENVELOPE: implied response factor exp(D) > e ≈ 2.7×."
INCOMPLETE_CONDITIONS = "INCOMPLETE_CONDITIONS: one or more conditions unknown; D is a lower bound."
BURNER_SIDE_O2 = "BURNER_SIDE_O2: oxygen value is burner/oxidizer flow, not ambient atmosphere."
NON_PSI_SOURCE = "NON_PSI_SOURCE"
UNWEIGHTED = "UNWEIGHTED: no published correlation for this phenomenon; uniform weights used."


def flag_code(flag: str) -> str:
    """'GRAVITY_EXTRAPOLATION: ...' -> 'GRAVITY_EXTRAPOLATION'."""
    return flag.split(":", 1)[0]


def flags_for(s: dict, e: dict, D: float, lb: bool, weighted: bool = True) -> list[str]:
    f: list[str] = []
    g = s.get("gravity_g0")
    if g is not None and g not in BRACKET_GRAVITIES:
        f.append(GRAVITY_EXTRAPOLATION)
    if D > D_ENVELOPE_THRESHOLD:
        f.append(BEYOND_TESTED_ENVELOPE)
    if lb:
        f.append(INCOMPLETE_CONDITIONS)
    if e.get("o2_context") == "burner_oxidizer_flow":
        f.append(BURNER_SIDE_O2)
    if e.get("psi_id") is None:
        f.append(NON_PSI_SOURCE)
    if e.get("tensions"):
        f.append("TENSION: " + "; ".join(e["tensions"]))
    if not weighted:
        f.append(UNWEIGHTED)
    return f
