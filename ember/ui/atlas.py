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
from ember.demo import air_fields, lunar_fields, scenario_dict
from ember.engine.gapscope import GRAVITY_NAME, target_coverage
from ember.engine.score import collapse, rank, scenario_to_dict
from ember.export import tables
from ember.llm.templates import format_range
from ember.registry import load_registry
from ember.schemas import Scenario
from ember.ui.evidence_map import P_RANGE, PPO2_ISOLINES_KPA, X_RANGE, classify
from ember.ui.layout import tokens
from ember.ui.scenario import GRAVITY_OPTIONS, PHENOMENON_LABELS, apply_parsed
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
    # Records per gravity regime, for the dark-sky section. Moon and Mars stay at zero: PSI holds no
    # partial-gravity fire test, and the one simulated partial-g record is outside PSI.
    regime = Counter(e.gravity.value for e in ev)
    sim = sorted({e.investigation for e in ev if e.gravity.value == "simulated_partial"})
    gravity = [
        {
            "label": "Orbit (0 g)",
            "n": regime["microgravity"],
            "note": "Where NASA's fire tests were run.",
        },
        {
            "label": "Moon (0.166 g)",
            "n": 0,
            "note": "No PSI test."
            + (
                f" {regime['simulated_partial']} simulated record outside PSI ({', '.join(sim)})."
                if sim
                else ""
            ),
        },
        {"label": "Mars (0.38 g)", "n": 0, "note": "No PSI test."},
        {"label": "Earth (1 g)", "n": regime["1g"], "note": "Ground comparison runs."},
    ]
    return {
        "gravity": gravity,
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
    return _ranked_rows(scenario_to_dict(scenario), k)


def _ranked_rows(s: dict, k: int) -> list[dict]:
    reg = _registry()
    results = collapse(rank(s, reg.evidence_dicts()), "investigation")
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
        srcs = reg.source_by_id()
        flags = r["flags"] if isinstance(r["flags"], list) else []
        detail = {
            "fuel": e.fuel_name or (e.fuel_class.value if e.fuel_class else "unknown"),
            "gravity": e.gravity.value,
            "o2_context": e.o2_context.value,
            "conds": [
                ["Oxygen, X_O₂", format_range(e.x_o2, "{:.3g}"), _loc(e.x_o2)],
                ["Pressure, kPa", format_range(e.p_kpa, "{:.4g}"), _loc(e.p_kpa)],
                ["Flow, cm/s", format_range(e.u_cms, "{:.3g}"), _loc(e.u_cms)],
            ],
            # each dimension's share of D; None means the record did not report it (D is a lower bound)
            "parts": {k: (None if v is None else round(v, 4)) for k, v in r["parts"].items()},
            "priors": r.get("priors", {}),
            "flags": [str(f).split(":")[0] for f in flags],
            "sources": [
                {
                    "id": sid,
                    "title": srcs[sid].title if sid in srcs else "unknown",
                    "doi": (srcs[sid].doi or "") if sid in srcs else "",
                    "url": (srcs[sid].url or "") if sid in srcs else "",
                    "psi": bool(srcs[sid].in_psi) if sid in srcs else False,
                }
                for sid in e.sources
            ],
        }
        out.append(
            {
                "detail": detail,
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


def _loc(rng) -> str:
    """Where a reported condition comes from: source id and locator, or why there is none."""
    if rng is None or rng.status != "known":
        return "not reported"
    return f"{rng.source_id or ''} · {rng.source_locator or ''}".strip(" ·") or "no locator"


@st.cache_data(show_spinner=False)
def atmosphere_pair() -> dict:
    """The demo's two real endpoints, ranked by the engine with gravity held fixed: Earth-normal air
    and the lunar habitat atmosphere of the demo question. Nothing between them is ranked."""
    lunar = lunar_fields()
    air = air_fields(lunar)

    def side(name: str, f: dict) -> dict:
        rows = _ranked_rows(scenario_dict(f), 8)
        keep = ("rank", "inv", "id", "D", "expD", "lb", "n")
        return {
            "name": name,
            "x": f["x_o2"],
            "p": f["p_kpa"],
            "ranked": [{k: r[k] for k in keep} | {"flags": r["detail"]["flags"]} for r in rows],
        }

    return {
        "g": lunar["gravity_g0"],
        "g_label": GRAVITY_NAME.get(lunar["gravity_g0"], f"{lunar['gravity_g0']:g} g"),
        "phenomenon": PHENOMENON_LABELS.get(lunar["phenomenon"], lunar["phenomenon"]),
        "fuel": (lunar.get("fuel_class") or "unspecified fuel").replace("_", " "),
        "a": side("Earth-normal air", air),
        "b": side("Lunar habitat atmosphere", lunar),
    }


@st.cache_data(show_spinner=False)
def gap_chapter(phen: str, fuel: str | None, u: float | None) -> dict:
    """GapScope coverage at every NASA target for every gravity regime EMBER supports, plus where
    the charted tests sit in each regime (orbit and Earth only: PSI holds no partial-g fire test)."""
    reg = _registry()
    rows = target_coverage(reg.evidence_dicts(), phen, fuel, u)
    regime_g = {"microgravity": config.G_MICRO, "1g": config.G_EARTH}
    stars: dict[tuple, dict] = {}
    for e in classify(reg.evidence).plotted:
        g = regime_g.get(e.gravity.value)
        if g is None:
            continue
        x, p = _center(e)
        k = (g, round(x, 3), round(p, 1))
        stars.setdefault(k, {"g": g, "x": x, "p": p, "n": 0})["n"] += 1
    return {
        "phenomenon": PHENOMENON_LABELS.get(phen, phen),
        "fuel": (fuel or "any fuel").replace("_", " "),
        "regimes": [
            {
                "g": g,
                "label": GRAVITY_NAME[g],
                "bracket": g in config.BRACKET_GRAVITIES,
                "rows": [r for r in rows if r["g"] == g],
            }
            for g in config.GAP_G
        ],
        "stars": list(stars.values()),
    }


PAGES = {
    "demo": "pages/0_Demo.py",
    "ask": "pages/1_Ask.py",
    "evidence-map": "pages/2_Evidence_Map.py",
    "compare": "pages/3_Compare.py",
    "gaps": "pages/4_Gaps.py",
    "registry": "pages/5_Registry.py",
    "sources": "pages/7_Sources.py",
    "validation": "pages/6_Validation.py",
}


def _on_drop() -> None:
    """The overview reported an action: copy it into the scenario before the widgets render."""
    v = st.session_state.get(KEY)
    if not isinstance(v, dict):
        return
    ss = st.session_state
    if v.get("preset") == "lunar":  # the demo question's scenario, as the parser reads it
        apply_parsed(lunar_fields())
        return
    if v.get("nav") in PAGES:
        ss["_atlas_nav"] = PAGES[v["nav"]]
        return
    if v.get("gravity") in GRAVITY_OPTIONS:
        ss["preset"] = "Custom"
        ss["gravity_label"] = v["gravity"]
        return
    if "x_o2" not in v:
        return
    x_pct = min(max(round(float(v["x_o2"]) * 200) / 2, 10.0), 60.0)
    p = min(max(round(float(v["p_kpa"]) * 2) / 2, P_RANGE[0]), P_RANGE[1])
    ss["preset"] = "Custom"
    ss["x_o2_pct"] = x_pct
    ss["p_kpa"] = p
    ss["p_psi"] = min(max(round(kpa_to_psi(p), 1), 3.0), 30.0)


# The overview backdrop follows the scenario's explicit gravity setting (illustrative context only).
# It is never inferred from oxygen or pressure; an unknown gravity shows a neutral starfield.
BACKDROP = {
    config.G_EARTH: "earth",
    config.G_MICRO: "orbit",
    config.G_MOON: "moon",
    config.G_MARS: "mars",
}


def framing_key(scenario: Scenario) -> str:
    """Names the habitat atmosphere for the backdrop's small framing change on the same body: the
    chosen preset, or the NASA target the scenario sits on, or "custom"."""
    preset = st.session_state.get("preset")
    if preset and preset != "Custom":
        return str(preset)
    for name, x, p in config.TARGETS:
        if abs(scenario.x_o2 - x) < 0.0026 and abs(scenario.p_kpa - p) < 0.6:
            return name
    return "custom"


def atlas(scenario: Scenario, pages: list[dict]) -> None:
    g = next((k for k, v in GRAVITY_OPTIONS.items() if v == scenario.gravity_g0), "")
    fc = scenario.fuel_class.value if scenario.fuel_class else None
    _component(
        sky=sky(),
        scenario={
            "x": scenario.x_o2,
            "p": scenario.p_kpa,
            "gravity": g,
            "partial_g": scenario.gravity_g0 not in config.BRACKET_GRAVITIES,
            "phenomenon": PHENOMENON_LABELS.get(scenario.phenomenon.value, ""),
            "flow": scenario.u_cms,
            "backdrop": BACKDROP.get(scenario.gravity_g0, "none"),
            "framing": framing_key(scenario),
        },
        gravity_backdrop={k: BACKDROP.get(v, "none") for k, v in GRAVITY_OPTIONS.items()},
        ranked=ranked(scenario),
        pair=atmosphere_pair(),
        gaps=gap_chapter(scenario.phenomenon.value, fc, scenario.u_cms),
        envelope=config.D_ENVELOPE_THRESHOLD,
        gravity_options=list(GRAVITY_OPTIONS),
        pages=pages,
        theme=tokens(),
        key=KEY,
        on_change=_on_drop,
        default=None,
    )
