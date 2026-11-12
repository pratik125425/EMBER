"""Reciprocal rank fusion (spec §12.2 system 4; Cormack, Clarke & Büttcher 2009): score(d) = Σ 1/(k + rank)."""

from __future__ import annotations

RRF_K = 60


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    score: dict[str, float] = {}
    for ranking in rankings:
        for pos, d in enumerate(ranking, start=1):
            score[d] = score.get(d, 0.0) + 1.0 / (k + pos)
    return sorted(score, key=lambda d: (-score[d], d))
