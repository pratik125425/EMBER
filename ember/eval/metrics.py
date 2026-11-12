"""Ranking metrics, uncertainty and agreement (spec §12.1, §12.3; ticket T14).

nDCG@k uses graded gains 2^rel − 1 (Järvelin & Kekäläinen 2002). Recall@k and MRR count a document
as relevant when its label is ≥ 2 ("relevant" or "directly applicable"). Queries with no relevant
document in the pool have undefined recall/MRR (and zero ideal DCG); ``evaluable`` says so and the
harness reports them separately as gap queries instead of averaging zeros in.
"""

from __future__ import annotations

import numpy as np

REL_THRESHOLD = 2


def ndcg_at_k(ranked: list[str], rels: dict[str, int], k: int = 5) -> float:
    gains = [(2 ** rels.get(d, 0) - 1) / np.log2(i + 2) for i, d in enumerate(ranked[:k])]
    ideal = sorted(rels.values(), reverse=True)[:k]
    idcg = sum((2**r - 1) / np.log2(i + 2) for i, r in enumerate(ideal))
    return float(sum(gains) / idcg) if idcg > 0 else 0.0


def recall_at_k(ranked: list[str], rels: dict[str, int], k: int = 5) -> float:
    relevant = {d for d, r in rels.items() if r >= REL_THRESHOLD}
    if not relevant:
        return 0.0
    return len(relevant & set(ranked[:k])) / len(relevant)


def mrr(ranked: list[str], rels: dict[str, int]) -> float:
    for i, d in enumerate(ranked, start=1):
        if rels.get(d, 0) >= REL_THRESHOLD:
            return 1.0 / i
    return 0.0


def evaluable(rels: dict[str, int]) -> bool:
    return any(r >= REL_THRESHOLD for r in rels.values())


def bootstrap_ci(
    values: list[float], n: int = 1000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float, float]:
    """(mean, lo, hi) with a percentile bootstrap over queries."""
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, v.size, size=(n, v.size))].mean(axis=1)
    return (
        float(v.mean()),
        float(np.percentile(means, 100 * alpha / 2)),
        float(np.percentile(means, 100 * (1 - alpha / 2))),
    )


def paired_permutation(a: list[float], b: list[float], n: int = 10000, seed: int = 0) -> dict:
    """Two-sided paired sign-flip permutation test on per-query differences a − b."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if d.size == 0:
        return {"mean_diff": float("nan"), "p_value": float("nan"), "n": 0}
    obs = abs(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n, d.size))
    perm = np.abs((signs * d).mean(axis=1))
    p = (np.sum(perm >= obs - 1e-12) + 1) / (n + 1)
    return {"mean_diff": float(d.mean()), "p_value": float(p), "n": int(d.size)}


def weighted_kappa(
    a: list[int], b: list[int], labels: tuple[int, ...] = (0, 1, 2, 3), weights: str = "linear"
) -> float:
    """Cohen's weighted κ for ordinal labels (linear or quadratic disagreement weights)."""
    if len(a) != len(b) or not a:
        raise ValueError("need two equal-length, non-empty label lists")
    idx = {lab: i for i, lab in enumerate(labels)}
    k = len(labels)
    obs = np.zeros((k, k))
    for x, y in zip(a, b, strict=True):
        obs[idx[x], idx[y]] += 1
    obs /= obs.sum()
    exp = np.outer(obs.sum(axis=1), obs.sum(axis=0))
    i, j = np.indices((k, k))
    w = np.abs(i - j) / (k - 1) if weights == "linear" else ((i - j) / (k - 1)) ** 2
    denom = (w * exp).sum()
    return 1.0 if denom == 0 else float(1.0 - (w * obs).sum() / denom)
