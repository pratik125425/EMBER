"""Relevance score R = M_φ · M_f · Q · exp(−D) (spec §10.4) and ranking.

All of this is deterministic Python. The LLM never produces a ranking or a number (spec §0.2).
"""

from __future__ import annotations

from math import exp

from ember import config
from ember.engine.distance import elasticities_for, transfer_distance
from ember.engine.flags import flags_for
from ember.schemas import Evidence, Range, Scenario


# ---------------------------------------------------------------------------------- adapters
def _bounds(r: Range | None) -> tuple[float | None, float | None]:
    if r is None or r.status != "known":
        return None, None
    return r.min, r.max


def evidence_to_dict(e: Evidence) -> dict:
    """Flatten an Evidence model into the dict shape the engine consumes."""
    d = {
        "evidence_id": e.evidence_id,
        "investigation": e.investigation,
        "psi_id": e.psi_id,
        "hardware_family": e.hardware_family,
        "fuel_class": e.fuel_class.value,
        "fuel_name": e.fuel_name,
        "phenomena": [p.value for p in e.phenomena],
        "gravity": e.gravity.value,
        "o2_context": e.o2_context.value,
        "granularity": e.granularity.value,
        "tensions": list(e.tensions),
        "flow_direction": e.flow_direction,
        "enclosure_note": e.enclosure_note,
        "sources": list(e.sources),
    }
    for k, r in (("x_o2", e.x_o2), ("p_kpa", e.p_kpa), ("u_cms", e.u_cms)):
        d[f"{k}_min"], d[f"{k}_max"] = _bounds(r)
        d[f"{k}_status"] = r.status
    # Spec §0.5: burner/oxidizer-side oxygen (e.g. CFI-G inverse flames, up to 0.85) is not a cabin
    # atmosphere. It stays visible in the registry but never enters D, coverage or the O₂ axis:
    # for the engine the ambient O₂ of such a record is unknown (→ D is a lower bound).
    if e.o2_context.value == "burner_oxidizer_flow":
        d["x_o2_min"] = d["x_o2_max"] = None
        d["x_o2_status"] = "burner_side_not_ambient"
    return d


def scenario_to_dict(s: Scenario) -> dict:
    return {
        "name": s.name,
        "x_o2": s.x_o2,
        "p_kpa": s.p_kpa,
        "u_cms": s.u_cms,
        "gravity_g0": s.gravity_g0,
        "phenomenon": s.phenomenon.value,
        "fuel_class": s.fuel_class.value if s.fuel_class else None,
        "fuel_name": s.fuel_name,
        "flow_direction": s.flow_direction,
    }


# ------------------------------------------------------------------------------------ priors
def m_phi(q: str, ephens: list[str], related=None, priors: dict | None = None) -> float:
    related = config.RELATED if related is None else related
    pr = config.M_PHI if priors is None else priors
    if q in ephens:
        return pr["exact"]
    if any((q, p) in related or (p, q) in related for p in ephens):
        return pr["related"]
    return pr["other"]


def m_f(s_class, s_name, e_class, e_name, priors: dict | None = None) -> float:
    pr = config.M_F if priors is None else priors
    if s_class is None:
        return 1.0
    if s_class == e_class and s_name and e_name and s_name.lower() in e_name.lower():
        return pr["same_class_same_material"]
    if s_class == e_class:
        return pr["same_class"]
    return pr["different"]


# ------------------------------------------------------------------------------------- score
def completeness_tier(parts: dict) -> str:
    """Classify how much of the scenario's weighted condition space the evidence covers.

    ``parts`` maps each weighted dimension the scenario asked about to its D contribution, or
    None when the evidence lacks it. No weighted dimensions asked → "complete" (nothing missing).
    """
    asked = len(parts)
    known = sum(1 for v in parts.values() if v is not None)
    if asked == 0 or known == asked:
        return config.TIER_COMPLETE
    if known == 0:
        return config.TIER_NO_CONDITIONS
    return config.TIER_PARTIAL


def score(s: dict, e: dict, overrides: dict | None = None) -> dict:
    """Score one (scenario, evidence) pair.

    ``overrides`` may contain ``elasticity``, ``q_prior``, ``m_phi``, ``m_f`` to support
    Monte Carlo perturbation (spec §10.5); the defaults come from ``ember.config``.
    """
    ov = overrides or {}
    phen = s["phenomenon"]
    D, lb, parts = transfer_distance(
        s, e, phen, elasticity=ov.get("elasticity"), mode=ov.get("distance", "interval_log")
    )
    _, weighted = elasticities_for(phen, ov.get("elasticity"))
    q_prior = ov.get("q_prior", config.Q_PRIOR)
    mphi = m_phi(phen, e["phenomena"], priors=ov.get("m_phi"))
    mf = m_f(
        s.get("fuel_class"),
        s.get("fuel_name"),
        e["fuel_class"],
        e.get("fuel_name"),
        priors=ov.get("m_f"),
    )
    q = q_prior[e["granularity"]]
    R = mphi * mf * q * exp(-D)
    tier = completeness_tier(parts)
    return {
        "evidence_id": e.get("evidence_id"),
        "investigation": e.get("investigation"),
        "R": R,
        "D": D,
        "expD": exp(D),
        "D_lower_bound": lb,
        "tier": tier,
        "parts": parts,
        "priors": {"m_phi": mphi, "m_f": mf, "Q": q},
        "weighted": weighted,
        "flags": flags_for(s, e, D, lb, weighted=weighted),
    }


def rank(
    s: dict, evidence: list[dict], overrides: dict | None = None, include_partial_g: bool = False
) -> list[dict]:
    """Rank evidence records for a scenario, highest R first.

    Evidence with ``gravity == "simulated_partial"`` (e.g. LUCI overlay) is excluded from the
    ranking pool by default (spec Appendix A): it is an overlay, not PSI evidence.

    Ordering: records whose tier is "no_conditions" (none of the weighted dimensions known, so
    D = 0 carries no information) are placed after all others when
    ``config.DEMOTE_NO_CONDITION_EVIDENCE`` is set. Within each group, highest R first.
    Ties break on evidence_id for determinism.
    """
    pool = [e for e in evidence if include_partial_g or e.get("gravity") != "simulated_partial"]
    results = [score(s, e, overrides) for e in pool]
    demote = config.DEMOTE_NO_CONDITION_EVIDENCE

    def key(r):
        last = demote and r["tier"] == config.TIER_NO_CONDITIONS
        return (last, -r["R"], r["evidence_id"] or "")

    results.sort(key=key)
    for i, r in enumerate(results, start=1):
        r["rank"] = i
    return results


def collapse(results: list[dict], key: str = "investigation") -> list[dict]:
    """Keep the best-ranked record per ``key`` (default: investigation), in rank order.

    Per-test tables add hundreds of near-identical rows; this view shows one row per investigation.
    Each kept row is a copy with ``rank`` renumbered, the original position in ``test_rank`` and the
    number of records it stands for in ``n_group``. R, D and flags are the kept record's own values.
    """
    out: list[dict] = []
    index: dict[str, dict] = {}
    for r in results:
        g = r.get(key)
        if g in index:
            index[g]["n_group"] += 1
            continue
        row = dict(r, test_rank=r.get("rank"), n_group=1, group=g)
        index[g] = row
        out.append(row)
    for i, row in enumerate(out, start=1):
        row["rank"] = i
    return out
