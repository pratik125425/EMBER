"""All ranking systems behind one interface, at the investigation level (ticket T13; used by T14).

    Query(text, scenario)  →  system.rank(query)  →  ordered list of investigation names (the pool)

Systems: random · bm25 · dense · hybrid (BM25 + dense, RRF k=60) · additive · ember.
Every system returns a permutation of the same pool: the rankable investigations in the registry
(the partial-gravity overlay is excluded, as in EMBER's own ranking). Scenario-based systems collapse
their per-record ranking to the best record per investigation.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

from ember.engine.score import collapse, rank
from ember.retrieval.additive import additive_rank
from ember.retrieval.bm25 import BM25Retriever
from ember.retrieval.corpus import load_corpus
from ember.retrieval.hybrid import rrf


@dataclass(frozen=True)
class Query:
    text: str
    scenario: dict | None = None
    qid: str = ""


class System:
    name = "system"
    needs = "text"  # or "scenario"

    def rank(self, q: Query) -> list[str]:  # pragma: no cover - interface
        raise NotImplementedError


def _complete(order: list[str], pool: list[str]) -> list[str]:
    seen = [d for d in order if d in pool]
    return seen + [d for d in sorted(pool) if d not in seen]


class RandomSystem(System):
    name = "random"

    def __init__(self, pool: list[str], seed: int = 0):
        self.pool, self.seed = sorted(pool), seed

    def rank(self, q: Query) -> list[str]:
        rng = np.random.default_rng([self.seed, zlib.crc32(q.text.encode())])
        return [self.pool[i] for i in rng.permutation(len(self.pool))]


class BM25System(System):
    name = "bm25"

    def __init__(self, docs: list[dict], pool: list[str]):
        self.r, self.pool = BM25Retriever([d for d in docs if d["doc_id"] in pool]), pool

    def rank(self, q: Query) -> list[str]:
        return _complete(self.r.rank(q.text), self.pool)


class DenseSystem(System):
    name = "dense"

    def __init__(self, docs: list[dict], pool: list[str]):
        from ember.retrieval.dense import DenseRetriever

        self.r, self.pool = DenseRetriever([d for d in docs if d["doc_id"] in pool]), pool

    def rank(self, q: Query) -> list[str]:
        return _complete(self.r.rank(q.text), self.pool)


class HybridSystem(System):
    name = "hybrid"

    def __init__(self, bm25: BM25System, dense: DenseSystem):
        self.bm25, self.dense, self.pool = bm25, dense, bm25.pool

    def rank(self, q: Query) -> list[str]:
        return _complete(rrf([self.bm25.rank(q), self.dense.rank(q)]), self.pool)


class AdditiveSystem(System):
    name = "additive"
    needs = "scenario"

    def __init__(self, evidence: list[dict], pool: list[str]):
        self.ev, self.pool = [e for e in evidence if e["investigation"] in pool], pool

    def rank(self, q: Query) -> list[str]:
        if q.scenario is None:
            raise ValueError("additive needs a scenario")
        order = list(dict.fromkeys(r["investigation"] for r in additive_rank(q.scenario, self.ev)))
        return _complete(order, self.pool)


class EmberSystem(System):
    name = "ember"
    needs = "scenario"

    def __init__(
        self,
        evidence: list[dict],
        pool: list[str],
        overrides: dict | None = None,
        name: str = "ember",
    ):
        self.ev, self.pool, self.overrides, self.name = evidence, pool, overrides, name

    def rank(self, q: Query) -> list[str]:
        if q.scenario is None:
            raise ValueError("ember needs a scenario")
        return _complete(
            [r["investigation"] for r in collapse(rank(q.scenario, self.ev, self.overrides))],
            self.pool,
        )


def build_systems(include_dense: bool = True) -> tuple[dict[str, System], dict[str, str]]:
    """Returns (systems by name, unavailable systems with the reason)."""
    from ember.registry import load_registry

    reg = load_registry()
    ev = reg.evidence_dicts()
    pool = sorted({e["investigation"] for e in ev if e["gravity"] != "simulated_partial"})
    docs = load_corpus()
    missing = set(pool) - {d["doc_id"] for d in docs}
    if missing:
        raise RuntimeError(
            f"corpus lacks documents for {sorted(missing)}; rebuild with ember.retrieval.corpus"
        )
    systems: dict[str, System] = {"random": RandomSystem(pool), "bm25": BM25System(docs, pool)}
    unavailable: dict[str, str] = {}
    if include_dense:
        try:
            systems["dense"] = DenseSystem(docs, pool)
            systems["hybrid"] = HybridSystem(systems["bm25"], systems["dense"])
        except Exception as exc:  # noqa: BLE001 - optional extra / model download
            unavailable["dense"] = unavailable["hybrid"] = f"{type(exc).__name__}: {exc}"
    systems["additive"] = AdditiveSystem(ev, pool)
    systems["ember"] = EmberSystem(ev, pool)
    return systems, unavailable
