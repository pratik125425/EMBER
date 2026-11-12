"""Transfer distance D (spec §10.1–10.3).

Flame responses follow power laws, so distances are computed in log space. The distance to a
tested *interval* [lo, hi] is 0 inside the interval and the log distance to the nearest edge
outside it. D sums per-dimension distances weighted by |ε_k| for the scenario's phenomenon.

If Y ∝ Π x_k^{ε_k}, then |Δ ln Y| ≤ D, so exp(D) is the largest response factor the
correlation implies between the evidence and the scenario.

Unknown evidence dimensions contribute 0 and set ``lower_bound=True`` (spec §0.1: never impute).
Gravity is NOT a dimension here (spec §0.4): it is handled by flags.
"""

from __future__ import annotations

from math import log

from ember.config import DIMS, ELASTICITY, U_FLOOR_CMS, UNIFORM


def interval_log_distance(x: float, lo: float, hi: float) -> float:
    """Log-space distance from x to the interval [lo, hi]; 0 inside."""
    if x <= 0 or lo <= 0 or hi <= 0:
        raise ValueError(f"interval_log_distance needs positive values (got {x!r}, {lo!r}, {hi!r})")
    if lo <= x <= hi:
        return 0.0
    return min(abs(log(x / lo)), abs(log(x / hi)))


def elasticities_for(
    phen: str, elasticity: dict[str, dict[str, float]] | None = None
) -> tuple[dict[str, float], bool]:
    """Return (ε vector, weighted) for a phenomenon. ``weighted`` is False when UNIFORM is used."""
    table = ELASTICITY if elasticity is None else elasticity
    if phen in table:
        return table[phen], True
    return UNIFORM, False


DISTANCE_MODES = ("interval_log", "midpoint_log", "interval_linear")


def dimension_distance(x: float, lo: float, hi: float, mode: str = "interval_log") -> float:
    """Unweighted per-dimension distance. EMBER uses ``interval_log``; the other two exist only for
    the spec §12.4 ablations:
      midpoint_log     |ln(x / midpoint)|  (collapses the tested range to its midpoint; never 0 inside)
      interval_linear  |x − nearest edge| / x  (fractional deviation instead of a log ratio)
    """
    if mode == "interval_log":
        return interval_log_distance(x, lo, hi)
    if mode == "midpoint_log":
        return abs(log(x / ((lo + hi) / 2.0)))
    if mode == "interval_linear":
        if lo <= x <= hi:
            return 0.0
        return min(abs(x - lo), abs(x - hi)) / x
    raise ValueError(f"unknown distance mode {mode!r}; expected one of {DISTANCE_MODES}")


def transfer_distance(
    s: dict,
    e: dict,
    phen: str,
    elasticity: dict[str, dict[str, float]] | None = None,
    mode: str = "interval_log",
) -> tuple[float, bool, dict[str, float | None]]:
    """Compute D(s, e) for phenomenon ``phen``.

    ``s`` keys: x_o2, p_kpa, u_cms (each float or None).
    ``e`` keys: x_o2_min, x_o2_max, p_kpa_min, p_kpa_max, u_cms_min, u_cms_max (float or None).

    Returns (D, lower_bound, parts). ``parts[k]`` is the weighted contribution of dimension k,
    or None when the evidence lacks that dimension (feeds the UI "why" bars).
    """
    eps, _ = elasticities_for(phen, elasticity)
    D, lower_bound, parts = 0.0, False, {}
    for k in DIMS:
        w = abs(eps.get(k, 0.0))
        if s.get(k) is None or w == 0:
            continue
        lo, hi = e.get(f"{k}_min"), e.get(f"{k}_max")
        if lo is None or hi is None:
            lower_bound = True
            parts[k] = None
            continue
        x = s[k]
        if k == "u_cms":
            x, lo, hi = max(x, U_FLOOR_CMS), max(lo, U_FLOOR_CMS), max(hi, U_FLOOR_CMS)
        d = w * dimension_distance(x, lo, hi, mode)
        parts[k] = d
        D += d
    return D, lower_bound, parts
