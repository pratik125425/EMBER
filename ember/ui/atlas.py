"""The Evidence Sky Atlas: every NASA test as a star on an oxygen–pressure plate, with the scenario as
a draggable reticle (overview first viewport).

The frontend (``atlas_frontend/index.html``) is a self-contained, offline bidirectional Streamlit
component. It only draws and reports where the reticle was dropped. Every number about relevance
(rank, D, exp(D)) comes from the engine here in Python, through ``rank``/``collapse``, exactly as
on the Ask page. Placement follows the Evidence Map's honesty rules (``classify``): a star is drawn
only when both O₂ and pressure are known; O₂-only records appear on their investigation's O₂ strip;
everything else is counted as uncharted with its reason, never placed at a guessed position.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ember import config
from ember.engine.score import collapse, rank, scenario_to_dict
from ember.export import tables
from ember.registry import load_registry
from ember.schemas import Scenario
from ember.ui.evidence_map import P_RANGE, PPO2_ISOLINES_KPA, X_RANGE, classify
from ember.ui.layout import tokens
from ember.ui.scenario import GRAVITY_OPTIONS, PHENOMENON_LABELS
from ember.units import kpa_to_psi

_component = components.declare_component(
    "ember_atlas", path=str(Path(__file__).parent / "atlas_frontend")
)
KEY = "atlas_reticle"


def _norm(x: float, p: float) -> tuple[float, float]:
    """Plate coordinates in [0, 1]² (O₂ linear, pressure log), for constellation lines."""
    nx = (x - X_RANGE[0]) / (X_RANGE[1] - X_RANGE[0])
    ny = math.log(p / P_RANGE[0]) / math.log(P_RANGE[1] / P_RANGE[0])
    return nx, ny


def _mst(nodes: list[tuple[float, float]]) -> list[tuple[int, int]]:
    """Prim's minimum spanning tree over plate coordinates: the investigation's constellation."""
    n = len(nodes)
    if n < 2:
        return []
    pts = [_norm(x, p) for x, p in nodes]
    inside, edges = {0}, []
    best = {j: (math.dist(pts[0], pts[j]), 0) for j in range(1, n)}
    while best:
        j = min(best, key=lambda k: best[k][0])
        edges.append((best.pop(j)[1], j))
        inside.add(j)
        for k in best:
            d = math.dist(pts[j], pts[k])
            if d < best[k][0]:
                best[k] = (d, j)
    return edges


def _center(e) -> tuple[float, float]:
    return (e.x_o2.min + e.x_o2.max) / 2, (e.p_kpa.min * e.p_kpa.max) ** 0.5


@st.cache_data(show_spinner=False)
def sky() -> dict:
    """Everything static about the plate, counted live from the registry."""
    reg = load_registry()
    ev = reg.evidence
    placement = classify(ev)
    t = tables(reg)

    stars: dict[tuple, dict] = {}
    nebulae: dict[tuple, dict] = {}
    for e in placement.plotted:
        x0, x1, p0, p1 = e.x_o2.min, e.x_o2.max, e.p_kpa.min, e.p_kpa.max
        if x0 == x1 and p0 == p1:
            k = (e.investigation, round(x0, 4), round(p0, 2))
            stars.setdefault(k, {"inv": e.investigation, "x": x0, "p": p0, "n": 0})["n"] += 1
        else:
            k = (e.investigation, round(x0, 4), round(x1, 4), round(p0, 2), round(p1, 2))
            nebulae.setdefault(
                k, {"inv": e.investigation, "x0": x0, "x1": x1, "p0": p0, "p1": p1, "n": 0}
            )["n"] += 1

    by_inv: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for s in stars.values():
        by_inv[s["inv"]].append((s["x"], s["p"]))
    for nb in nebulae.values():
        by_inv[nb["inv"]].append(((nb["x0"] + nb["x1"]) / 2, (nb["p0"] * nb["p1"]) ** 0.5))
    constellations = []
    for inv, nodes in by_inv.items():
        lines = [[*nodes[a], *nodes[b]] for a, b in _mst(nodes)]
        # Label sits above the constellation's westernmost star, as on a printed plate.
        lx, lp = min(nodes, key=lambda n: (n[0], -n[1]))
        constellations.append({"inv": inv, "lines": lines, "label": [lx, lp]})

    # One index cell per investigation: counts and its O₂ coverage on an identical 10–60% ruler.
    charted = Counter(e.investigation for e in placement.plotted)
    o2_only = Counter(e.investigation for e in placement.p_unknown)
    uncharted = Counter(e.investigation for e, _ in placement.not_plottable)
    segs: dict[str, set] = defaultdict(set)
    for e in [*placement.plotted, *placement.p_unknown]:
        segs[e.investigation].add((round(e.x_o2.min, 4), round(e.x_o2.max, 4)))
    total = Counter(e.investigation for e in ev)
    index = [
        {
            "inv": inv,
            "total": n,
            "charted": charted[inv],
            "o2_only": o2_only[inv],
            "uncharted": uncharted[inv],
            "o2": sorted(segs[inv]),
        }
        for inv, n in total.most_common()
    ]
    plain = {
        "O₂ is burner/oxidizer-side, not ambient": "with burner-side, not cabin, oxygen",
        "X_O₂ unknown": "with oxygen not reported",
        "X_O₂ not applicable": "where an oxygen level does not apply",
    }
    reasons = Counter(plain.get(r, r) for _, r in placement.not_plottable)
    files = t["files"]
    return {
        "stars": list(stars.values()),
        "nebulae": list(nebulae.values()),
        "constellations": constellations,
        "index": index,
        "targets": [{"name": n, "x": x, "p": p} for n, x, p in config.TARGETS],
        "target_tol": [config.TARGET_TOL_X_O2, config.TARGET_TOL_P_FRAC],
        "ppo2": list(PPO2_ISOLINES_KPA),
        "x_range": list(X_RANGE),
        "p_range": list(P_RANGE),
        "counts": {
            "records": len(ev),
            "investigations": len(total),
            "charted": len(placement.plotted),
            "o2_only": len(placement.p_unknown),
            "uncharted": len(placement.not_plottable),
            "reasons": reasons.most_common(),
            "sources": len(t["sources"]),
            "mirrored": int(files["sha256"].notna().sum()),
            "files": len(files),
        },
    }


@st.cache_resource
def _registry():
    return load_registry()


def ranked(scenario: Scenario, k: int = 5) -> list[dict]:
    """The engine's ranking, one row per investigation, with each row's plate position if charted."""
    reg = _registry()
    results = collapse(rank(scenario_to_dict(scenario), reg.evidence_dicts()), "investigation")
    by_id = reg.evidence_by_id()
    out = []
    for r in results[:k]:
        e = by_id[r["evidence_id"]]
        pos = o2 = None
        if e.o2_context.value != "burner_oxidizer_flow" and e.x_o2.status == "known":
            if e.p_kpa.status == "known":
                pos = list(_center(e))
            else:  # pressure not reported: a meridian at its O₂, never a guessed point
                o2 = [e.x_o2.min, e.x_o2.max]
        out.append(
            {
                "rank": r["rank"],
                "inv": r["investigation"],
                "id": r["evidence_id"],
                "D": r["D"],
                "expD": r["expD"],
                "R": r["R"],
                "lb": bool(r["D_lower_bound"]),
                "n": r["n_group"],
                "pos": pos,
                "o2": o2,
            }
        )
    return out


def _on_drop() -> None:
    """Reticle dropped: copy it into the sidebar scenario before the widgets render."""
    v = st.session_state.get(KEY)
    if not isinstance(v, dict) or "x_o2" not in v:
        return
    ss = st.session_state
    x_pct = min(max(round(float(v["x_o2"]) * 200) / 2, 10.0), 60.0)
    p = min(max(round(float(v["p_kpa"]) * 2) / 2, P_RANGE[0]), P_RANGE[1])
    ss["preset"] = "Custom"
    ss["x_o2_pct"] = x_pct
    ss["p_kpa"] = p
    ss["p_psi"] = min(max(round(kpa_to_psi(p), 1), 3.0), 30.0)


def atlas(scenario: Scenario) -> None:
    g = next((k for k, v in GRAVITY_OPTIONS.items() if v == scenario.gravity_g0), "")
    _component(
        sky=sky(),
        scenario={
            "x": scenario.x_o2,
            "p": scenario.p_kpa,
            "gravity": g,
            "partial_g": scenario.gravity_g0 not in config.BRACKET_GRAVITIES,
            "phenomenon": PHENOMENON_LABELS.get(scenario.phenomenon.value, ""),
            "flow": scenario.u_cms,
        },
        ranked=ranked(scenario),
        envelope=config.D_ENVELOPE_THRESHOLD,
        theme=tokens(),
        key=KEY,
        on_change=_on_drop,
        default=None,
    )
