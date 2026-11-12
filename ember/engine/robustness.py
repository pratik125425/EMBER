"""Monte Carlo rank stability (spec §10.5, ticket T08).

The elasticities are published exponents and the priors (M_φ, M_f, Q) are disclosed ordinal
choices. To show how much the ranking depends on them, every weight is perturbed by an
independent uniform factor (±eps_pct for elasticities, ±prior_pct for priors) and the ranking is
recomputed n times. For each record we report the fraction of draws in which it stays in the
top-k (``p_topk``); the UI shows a "stable" badge when p_topk ≥ config.STABLE_P_TOPK. Kendall's τ
between the base ranking and each perturbed ranking summarizes overall order stability.

What is NOT perturbed, on purpose:
- zero elasticities stay zero (e.g. flow for opposed spread: the published correlation has no
  flow term, so perturbing it would invent one);
- the anchor priors fixed at 1.0 (exact phenomenon match, same fuel + material, per-test table)
  stay at 1.0: the priors are relative, so only the lower rungs move.

Results are deterministic for a given seed and cached per (scenario, evidence set, parameters).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau

from ember import config
from ember.engine.score import collapse, rank
from ember.paths import CACHE_DIR

ANCHOR = 1.0
PRIOR_FLOOR = 0.01


def perturb(rng: np.random.Generator, prior_pct: float, eps_pct: float) -> dict:
    """One random draw of overrides for ``ember.engine.score.score``."""

    def jitter(v: float, pct: float) -> float:
        return float(v * rng.uniform(1.0 - pct, 1.0 + pct))

    elasticity = {
        phen: {k: (jitter(w, eps_pct) if w != 0.0 else 0.0) for k, w in eps.items()}
        for phen, eps in config.ELASTICITY.items()
    }

    def priors(table: dict[str, float]) -> dict[str, float]:
        return {
            k: (
                ANCHOR if v == ANCHOR else float(np.clip(jitter(v, prior_pct), PRIOR_FLOOR, ANCHOR))
            )
            for k, v in table.items()
        }

    return {
        "elasticity": elasticity,
        "m_phi": priors(config.M_PHI),
        "m_f": priors(config.M_F),
        "q_prior": priors(config.Q_PRIOR),
    }


def _positions(order: list[str], ref: list[str]) -> list[int]:
    pos = {eid: i for i, eid in enumerate(order)}
    return [pos[eid] for eid in ref]


def rank_stability(
    scenario: dict,
    evidence: list[dict],
    n: int = config.MC_N,
    prior_pct: float = config.MC_PRIOR_PCT,
    eps_pct: float = config.MC_EPS_PCT,
    k: int = config.MC_K,
    seed: int = config.MC_SEED,
    group_by: str | None = None,
) -> dict:
    """Monte Carlo rank stability for one scenario over an evidence pool.

    Returns a JSON-serializable dict:
      p_topk[eid]            fraction of draws with eid in the top-k
      rank_median/min/max    per-eid rank distribution (1-based)
      kendall_tau_median     median τ(base, perturbed); kendall_tau_ci = [2.5th, 97.5th] pct
      base_order             evidence ids in the unperturbed ranking
      params                 the inputs, so a cached result is self-describing

    With ``group_by="investigation"`` every ranking is first collapsed to its best record per
    investigation (``ember.engine.score.collapse``) and all statistics are keyed by investigation,
    matching the "one row per investigation" view.
    """
    rng = np.random.default_rng(seed)

    def order_of(results: list[dict]) -> list[str]:
        if group_by:
            return [r["group"] for r in collapse(results, group_by)]
        return [r["evidence_id"] for r in results]

    base = order_of(rank(scenario, evidence))
    if not base:
        return {
            "p_topk": {},
            "rank_median": {},
            "rank_min": {},
            "rank_max": {},
            "stable": {},
            "kendall_tau_median": None,
            "kendall_tau_ci": None,
            "base_order": [],
            "n": n,
            "k": k,
            "params": {
                "prior_pct": prior_pct,
                "eps_pct": eps_pct,
                "seed": seed,
                "group_by": group_by,
            },
        }
    k_eff = min(k, len(base))
    topk_counts = dict.fromkeys(base, 0)
    ranks = {eid: [] for eid in base}
    taus: list[float] = []
    base_pos = list(range(len(base)))
    for _ in range(n):
        pert = perturb(rng, prior_pct, eps_pct)
        order = order_of(rank(scenario, evidence, overrides=pert))
        for eid in order[:k_eff]:
            topk_counts[eid] += 1
        for i, eid in enumerate(order, start=1):
            ranks[eid].append(i)
        if len(base) > 1:
            tau = kendalltau(base_pos, _positions(order, base)).statistic
            taus.append(1.0 if np.isnan(tau) else float(tau))
        else:
            taus.append(1.0)
    p_topk = {eid: c / n for eid, c in topk_counts.items()}
    return {
        "p_topk": p_topk,
        "stable": {eid: p >= config.STABLE_P_TOPK for eid, p in p_topk.items()},
        "rank_median": {eid: float(np.median(v)) for eid, v in ranks.items()},
        "rank_min": {eid: int(min(v)) for eid, v in ranks.items()},
        "rank_max": {eid: int(max(v)) for eid, v in ranks.items()},
        "kendall_tau_median": float(np.median(taus)),
        "kendall_tau_ci": [float(np.percentile(taus, 2.5)), float(np.percentile(taus, 97.5))],
        "base_order": base,
        "n": n,
        "k": k_eff,
        "params": {
            "prior_pct": prior_pct,
            "eps_pct": eps_pct,
            "seed": seed,
            "stable_threshold": config.STABLE_P_TOPK,
            "group_by": group_by,
        },
    }


# ------------------------------------------------------------------------------------- cache
def _cache_key(scenario: dict, evidence: list[dict], params: dict) -> str:
    payload = {
        "scenario": scenario,
        "evidence": sorted(
            json.dumps({k: v for k, v in e.items()}, sort_keys=True, default=str) for e in evidence
        ),
        "params": params,
        "config": {
            "ELASTICITY": config.ELASTICITY,
            "M_PHI": config.M_PHI,
            "M_F": config.M_F,
            "Q_PRIOR": config.Q_PRIOR,
            "RELATED": sorted(config.RELATED),
            "DEMOTE": config.DEMOTE_NO_CONDITION_EVIDENCE,
            "STABLE": config.STABLE_P_TOPK,
            "U_FLOOR": config.U_FLOOR_CMS,
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[
        :24
    ]


def cached_rank_stability(
    scenario: dict,
    evidence: list[dict],
    cache_dir: Path = CACHE_DIR / "robustness",
    **params,
) -> tuple[dict, bool]:
    """rank_stability with a JSON file cache keyed by scenario + evidence + params + config.

    Returns (result, was_cached). Offline-safe: the cache is plain files under ``cache/``.
    """
    full = {
        "n": config.MC_N,
        "prior_pct": config.MC_PRIOR_PCT,
        "eps_pct": config.MC_EPS_PCT,
        "k": config.MC_K,
        "seed": config.MC_SEED,
        "group_by": None,
    }
    full.update(params)
    key = _cache_key(scenario, evidence, full)
    path = cache_dir / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text()), True
        except json.JSONDecodeError:
            path.unlink()
    result = rank_stability(scenario, evidence, **full)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1))
    return result, False
