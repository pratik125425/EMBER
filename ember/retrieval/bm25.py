"""BM25 baseline over investigation source text (spec §12.2 system 2; Robertson & Zaragoza 2009)."""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

STOP = frozenset(
    "a an and are as at be by for from has have in into is it its of on or that the their this to was were which with "
    "what which who how why when where does do can could would should will i we you they my our your".split()
)


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text.lower())
    return [t for t in toks if t not in STOP]


class BM25Retriever:
    name = "bm25"

    def __init__(self, docs: list[dict]):
        self.ids = [d["doc_id"] for d in docs]
        self.model = BM25Okapi([tokenize(d["text"]) for d in docs])

    def scores(self, query: str) -> dict[str, float]:
        s = self.model.get_scores(tokenize(query))
        return {i: float(v) for i, v in zip(self.ids, s, strict=True)}

    def rank(self, query: str) -> list[str]:
        sc = self.scores(query)
        return sorted(self.ids, key=lambda i: (-sc[i], i))
