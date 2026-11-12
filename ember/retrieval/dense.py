"""Dense baseline: sentence-transformers embeddings + FAISS inner-product search (spec §12.2 system 3;
Reimers & Gurevych 2019). Optional dependency: ``uv sync --extra retrieval``.

Documents are split into ~120-word passages; a document's score is its best passage's cosine
similarity (MiniLM truncates long inputs, so whole-document embedding would ignore most text).
If the extra is not installed, constructing the retriever raises ``DenseUnavailable``; callers report
the system as unavailable rather than substituting something else.
"""

from __future__ import annotations

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
PASSAGE_WORDS = 120


class DenseUnavailable(RuntimeError):
    pass


_MODELS: dict[str, object] = {}


def _model(name: str):
    if name not in _MODELS:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise DenseUnavailable(
                "sentence-transformers not installed (uv sync --extra retrieval)"
            ) from exc
        try:  # offline first (spec §0.8): use the local Hugging Face cache without touching the network
            _MODELS[name] = SentenceTransformer(name, local_files_only=True)
        except Exception:  # noqa: BLE001 - not cached yet → one-time download
            _MODELS[name] = SentenceTransformer(name)
    return _MODELS[name]


def passages(text: str, n: int = PASSAGE_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    step = n // 2  # 50 % overlap
    return [" ".join(words[i : i + n]) for i in range(0, max(1, len(words) - step), step)]


class DenseRetriever:
    name = "dense"

    def __init__(self, docs: list[dict], model_name: str = MODEL_NAME):
        self.model = _model(model_name)
        self.ids = [d["doc_id"] for d in docs]
        self.owner: list[int] = []
        texts: list[str] = []
        for i, d in enumerate(docs):
            for p in passages(d["text"]):
                texts.append(p)
                self.owner.append(i)
        emb = np.asarray(
            self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
            dtype="float32",
        )
        try:
            import faiss

            self.index = faiss.IndexFlatIP(emb.shape[1])
            self.index.add(emb)
            self.emb = None
        except ImportError:  # exact same math without FAISS
            self.index, self.emb = None, emb

    def scores(self, query: str) -> dict[str, float]:
        q = np.asarray(
            self.model.encode([query], normalize_embeddings=True, show_progress_bar=False),
            dtype="float32",
        )
        if self.index is not None:
            sims, idx = self.index.search(q, len(self.owner))
            pairs = zip(idx[0].tolist(), sims[0].tolist(), strict=True)
        else:
            sims = (self.emb @ q[0]).tolist()
            pairs = enumerate(sims)
        best = dict.fromkeys(range(len(self.ids)), -1.0)
        for j, s in pairs:
            o = self.owner[j]
            best[o] = max(best[o], float(s))
        return {self.ids[i]: v for i, v in best.items()}

    def rank(self, query: str) -> list[str]:
        sc = self.scores(query)
        return sorted(self.ids, key=lambda i: (-sc[i], i))
