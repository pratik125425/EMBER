"""GapScope: graded coverage and priority over (X_O₂, P, u, g) (spec §10.6, ticket T09).

Coverage  C(x) = max_e exp(−D(x, e)) over evidence with the chosen phenomenon (and fuel class if
          chosen) at the same gravity regime. Only evidence whose *every weighted dimension* is
          known contributes: a record with an unknown pressure cannot cover a pressure range, so
          it is listed as "partial-condition evidence (not counted)" instead of silently covering
          the whole axis. For g ∉ {0, 1}: C = 0 everywhere (PSI holds no partial-g data).
Priority  π(x) = (1 − C(x)) · T(x), with T = 1 inside a tolerance box around a NASA target
          atmosphere and 0.25 elsewhere. π is a HEURISTIC for where new tests would help, not
          information gain.
Report    Templated text: absence of evidence, never "safe".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from math import exp, log

import numpy as np

from ember import config
from ember.engine.distance import elasticities_for, transfer_distance
from ember.engine.flags import flags_for

GRAVITY_REGIME = {config.G_MICRO: "microgravity", config.G_EARTH: "1g"}
GRAVITY_NAME = {
    config.G_MICRO: "microgravity (0 g)",
    config.G_MOON: "lunar (0.166 g)",
    config.G_MARS: "Mars (0.38 g)",
    config.G_EARTH: "Earth (1 g)",
}


def grid_axes(n_x: int | None = None, n_p: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    x0, x1, nx = config.GAP_X_O2
    p0, p1, npp = config.GAP_P_KPA
    return np.linspace(x0, x1, n_x or nx), np.geomspace(p0, p1, n_p or npp)


def _asked_dims(phen: str, u: float | None) -> list[str]:
    eps, _ = elasticities_for(phen)
    return [k for k in config.DIMS if abs(eps.get(k, 0.0)) > 0 and not (k == "u_cms" and u is None)]


def split_pool(
    evidence: list[dict],
    phen: str,
    fuel_class: str | None,
    g: float,
    u: float | None,
    psi_only: bool = False,
) -> tuple[list[dict], list[dict]]:
    """(complete, partial): records with the phenomenon/fuel/gravity, split by condition completeness."""
    regime = GRAVITY_REGIME.get(g)
    if regime is None:
        return [], []
    asked = _asked_dims(phen, u)
    complete, partial = [], []
    for e in evidence:
        if phen not in e["phenomena"] or e["gravity"] != regime:
            continue
        if fuel_class is not None and e["fuel_class"] != fuel_class:
            continue
        if psi_only and e.get("psi_id") is None:
            continue
        known = all(e.get(f"{k}_min") is not None and e.get(f"{k}_max") is not None for k in asked)
        (complete if known else partial).append(e)
    return complete, partial


@dataclass
class GapGrid:
    g: float
    X: np.ndarray
    P: np.ndarray
    C: np.ndarray  # shape (len(P), len(X))
    nearest: np.ndarray  # evidence_id per cell ("" when none)
    T: np.ndarray  # target weight per cell
    pool: list[dict]
    partial: list[dict]
    hatched: bool  # True when no PSI evidence can exist at this gravity
    params: dict = field(default_factory=dict)

    @property
    def priority(self) -> np.ndarray:
        return (1.0 - self.C) * self.T


def target_weight(x: float, p: float) -> tuple[float, str | None]:
    for name, tx, tp in config.TARGETS:
        if abs(x - tx) <= config.TARGET_TOL_X_O2 and abs(p - tp) <= tp * config.TARGET_TOL_P_FRAC:
            return 1.0, name
    return config.PRIORITY_OUTSIDE_TARGET, None


def coverage_at(
    x: float, p: float, pool: list[dict], phen: str, u: float | None
) -> tuple[float, dict | None, float]:
    """Coverage at one point: (C, nearest evidence dict or None, D_nearest)."""
    s = {"x_o2": x, "p_kpa": p, "u_cms": u, "phenomenon": phen}
    best, best_e, best_d = 0.0, None, float("inf")
    for e in pool:
        d = transfer_distance(s, e, phen)[0]
        if d < best_d:
            best_d, best_e, best = d, e, exp(-d)
    return best, best_e, best_d


def coverage_grid(
    evidence: list[dict],
    phen: str,
    fuel_class: str | None = None,
    u: float | None = None,
    g: float = 0.0,
    psi_only: bool = False,
    n_x: int | None = None,
    n_p: int | None = None,
) -> GapGrid:
    X, P = grid_axes(n_x, n_p)
    C = np.zeros((len(P), len(X)))
    nearest = np.full((len(P), len(X)), "", dtype=object)
    T = np.array([[target_weight(x, p)[0] for x in X] for p in P])
    params = {
        "phenomenon": phen,
        "fuel_class": fuel_class,
        "u_cms": u,
        "g": g,
        "psi_only": psi_only,
    }
    if g not in config.BRACKET_GRAVITIES:
        return GapGrid(g, X, P, C, nearest, T, [], [], hatched=True, params=params)
    pool, partial = split_pool(evidence, phen, fuel_class, g, u, psi_only)
    for i, p in enumerate(P):
        for j, x in enumerate(X):
            c, e, _ = coverage_at(float(x), float(p), pool, phen, u)
            C[i, j] = c
            nearest[i, j] = e["evidence_id"] if e else ""
    return GapGrid(g, X, P, C, nearest, T, pool, partial, hatched=False, params=params)


def all_gravities(evidence, phen, fuel_class=None, u=None, psi_only=False) -> dict[float, GapGrid]:
    return {g: coverage_grid(evidence, phen, fuel_class, u, g, psi_only) for g in config.GAP_G}


# ------------------------------------------------------------------------------------ report
def target_coverage(evidence, phen, fuel_class=None, u=None, psi_only=False) -> list[dict]:
    """Coverage at each NASA target centre for each gravity (grid-independent)."""
    rows = []
    for g in config.GAP_G:
        pool, partial = split_pool(evidence, phen, fuel_class, g, u, psi_only)
        for name, tx, tp in config.TARGETS:
            if g not in config.BRACKET_GRAVITIES:
                rows.append(
                    {
                        "target": name,
                        "x_o2": tx,
                        "p_kpa": tp,
                        "g": g,
                        "C": 0.0,
                        "nearest": None,
                        "D": None,
                        "expD": None,
                        "flags": ["NO_PARTIAL_G_DATA_IN_PSI"],
                        "n_pool": 0,
                        "n_partial": 0,
                    }
                )
                continue
            c, e, d = coverage_at(tx, tp, pool, phen, u)
            s = {"x_o2": tx, "p_kpa": tp, "u_cms": u, "gravity_g0": g, "phenomenon": phen}
            flags = [f.split(":", 1)[0] for f in flags_for(s, e, d, False)] if e else []
            rows.append(
                {
                    "target": name,
                    "x_o2": tx,
                    "p_kpa": tp,
                    "g": g,
                    "C": c,
                    "nearest": e["evidence_id"] if e else None,
                    "D": d if e else None,
                    "expD": exp(d) if e else None,
                    "flags": flags,
                    "n_pool": len(pool),
                    "n_partial": len(partial),
                }
            )
    return rows


def top_priority_cells(grids: dict[float, GapGrid], n: int = 10) -> list[dict]:
    cells = []
    for g, gg in grids.items():
        if gg.hatched:
            continue
        pi = gg.priority
        for i in range(len(gg.P)):
            for j in range(len(gg.X)):
                cells.append(
                    {
                        "g": g,
                        "x_o2": float(gg.X[j]),
                        "p_kpa": float(gg.P[i]),
                        "C": float(gg.C[i, j]),
                        "priority": float(pi[i, j]),
                        "nearest": gg.nearest[i, j] or None,
                        "D": (-log(gg.C[i, j]) if gg.C[i, j] > 0 else None),
                        "target": target_weight(float(gg.X[j]), float(gg.P[i]))[1],
                    }
                )
    cells.sort(key=lambda c: (-c["priority"], c["g"], c["p_kpa"], c["x_o2"]))
    return cells[:n]


def gap_report_markdown(
    evidence, phen, fuel_class=None, u=None, psi_only=False, top_n: int = 10
) -> str:
    """Templated gap report. Phrased as absence of evidence; the word 'safe' never appears."""
    grids = all_gravities(evidence, phen, fuel_class, u, psi_only)
    targets = target_coverage(evidence, phen, fuel_class, u, psi_only)
    cells = top_priority_cells(grids, top_n)
    fuel = fuel_class.replace("_", " ") if fuel_class else "any fuel class"
    flow = "flow not specified (flow dimension not scored)" if u is None else f"flow {u:g} cm/s"
    src = "PSI records only" if psi_only else "PSI records plus non-PSI NASA sources (flagged)"
    lines = [
        f"# EMBER gap report — {phen.replace('_', ' ')}, {fuel}, {flow}",
        f"Generated {dt.date.today().isoformat()} · evidence pool: {src}",
        "",
        "Coverage C = max exp(−D) over evidence whose every weighted condition is known. "
        "C = 1 means the point lies inside a tested envelope; C = 0.37 means the nearest test implies a "
        "response factor of about 2.7×. **Low coverage is absence of evidence, not evidence of hazard or of "
        "acceptability.** Priority π = (1 − C)·T is a heuristic, not information gain.",
        "",
        "## Partial gravity (lunar 0.166 g, Mars 0.38 g)",
        "No PSI investigation measured combustion at partial gravity, so coverage is 0 everywhere on these panels. "
        "µg and 1-g results are brackets, not bounds: NASA reports lunar-g flammability can exceed both "
        "(FM2 abstract, NTRS 20240015307; Ruff 2021, NTRS 20210021318). Non-PSI partial-g sources:",
    ]
    for ov in config.PARTIAL_G_OVERLAYS:
        lines.append(
            f"- {ov['name']}: X_O₂ {ov['x_o2']:.3f}, P {ov['p_kpa']:.1f} kPa, {ov['gravity_g0']:.3f} g — "
            f"{ov['status']} [{ov['source_id']}]"
        )
    lines += [
        "",
        "## NASA target atmospheres",
        "",
        "| Target | Gravity | C | Nearest evidence | D | exp(D) | Flags | Complete / partial records |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t in targets:
        d = "—" if t["D"] is None else f"{t['D']:.3f}"
        ed = "—" if t["expD"] is None else f"{t['expD']:.2f}×"
        lines.append(
            f"| {t['target']} ({t['x_o2']:.3f} / {t['p_kpa']:.1f} kPa) | {GRAVITY_NAME[t['g']]} | {t['C']:.2f} | "
            f"{t['nearest'] or 'none'} | {d} | {ed} | {', '.join(t['flags']) or '—'} | {t['n_pool']} / {t['n_partial']} |"
        )
    lines += [
        "",
        f"## Top {len(cells)} priority cells (µg and 1-g panels)",
        "",
        "| X_O₂ | P (kPa) | Gravity | C | π | Nearest evidence | D | In target box |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        d = "—" if c["D"] is None else f"{c['D']:.2f}"
        lines.append(
            f"| {c['x_o2']:.3f} | {c['p_kpa']:.1f} | {GRAVITY_NAME[c['g']]} | {c['C']:.2f} | {c['priority']:.2f} | "
            f"{c['nearest'] or 'none'} | {d} | {c['target'] or '—'} |"
        )
    partial_ids = sorted({e["evidence_id"] for gg in grids.values() for e in gg.partial})
    if partial_ids:
        lines += [
            "",
            "## Partial-condition evidence (not counted toward coverage)",
            "These records match the phenomenon but lack at least one weighted condition, so they cannot cover "
            "a region of condition space: " + ", ".join(partial_ids) + ".",
        ]
    lines += [
        "",
        "## Not covered by this report",
        "- Water-mist suppression: no PSI dataset found (gap, not modeled).",
        "- Rocket/propellant combustion: out of scope.",
    ]
    return "\n".join(lines)
