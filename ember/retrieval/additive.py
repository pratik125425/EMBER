"""Competitor-style additive score (spec §5.1, §12.2 system 5): linear, hand-set points out of 100.

    35 phenomenon (exact match) + 25 fuel class + 20 O₂ match + 10 pressure match + 10 data quality

O₂ and pressure "match" decay linearly with ABSOLUTE distance outside the tested range (EMBER uses
elasticity-weighted log distance instead); unknown conditions score 0. Tolerances are hand-set:
"""

from __future__ import annotations

W_PHEN, W_FUEL, W_O2, W_P, W_QUAL = 35.0, 25.0, 20.0, 10.0, 10.0
O2_TOL = 0.10  # mole fraction: full points inside the range, 0 at ≥ 0.10 away
P_TOL_KPA = 50.0  # kPa: full points inside the range, 0 at ≥ 50 kPa away
QUALITY = {"per_test_table": 1.0, "campaign_summary": 0.6, "paper_only": 0.3}


def _match(x: float | None, lo: float | None, hi: float | None, tol: float) -> float:
    if x is None or lo is None or hi is None:
        return 0.0
    gap = 0.0 if lo <= x <= hi else min(abs(x - lo), abs(x - hi))
    return max(0.0, 1.0 - gap / tol)


def additive_score(s: dict, e: dict) -> dict:
    phen = W_PHEN if s["phenomenon"] in e["phenomena"] else 0.0
    fuel = (
        W_FUEL if (s.get("fuel_class") is None or s.get("fuel_class") == e["fuel_class"]) else 0.0
    )
    o2 = W_O2 * _match(s.get("x_o2"), e.get("x_o2_min"), e.get("x_o2_max"), O2_TOL)
    p = W_P * _match(s.get("p_kpa"), e.get("p_kpa_min"), e.get("p_kpa_max"), P_TOL_KPA)
    q = W_QUAL * QUALITY[e["granularity"]]
    return {
        "score": phen + fuel + o2 + p + q,
        "parts": {"phenomenon": phen, "fuel": fuel, "o2": o2, "pressure": p, "quality": q},
    }


def additive_rank(s: dict, evidence: list[dict]) -> list[dict]:
    rows = [
        dict(evidence_id=e["evidence_id"], investigation=e["investigation"], **additive_score(s, e))
        for e in evidence
    ]
    rows.sort(key=lambda r: (-r["score"], r["evidence_id"]))
    return rows
