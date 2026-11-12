"""Investigation text corpus for the text baselines (spec §9.8, §12.2, ticket T13).

The retrieval unit for evaluation is the INVESTIGATION (per-test rows are far too many to label).
One document per rankable investigation in the registry (the partial-gravity overlay is excluded,
as it is from EMBER's ranking). Document text is SOURCE TEXT ONLY, so the text baselines never see
EMBER's structured fields (phenomena labels, numeric conditions):
  - the PSI record's description, objective, approach and hypothesis (psi_id of the group's rows);
  - NTRS abstracts of the group's non-PSI sources (e.g. the Saffire VI paper);
  - curated claim sentences attached to the group's evidence (each sourced).

    uv run python -m ember.retrieval.corpus      # writes data/corpus/investigations.jsonl (committed)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ember.paths import DATA_DIR, RAW_DIR

CORPUS_DIR = DATA_DIR / "corpus"
CORPUS = CORPUS_DIR / "investigations.jsonl"
RECORD_FIELDS = ("description", "objective", "approach", "hypothesis")


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def rankable_investigations(evidence) -> dict[str, list]:
    groups: dict[str, list] = {}
    for e in evidence:
        if e.gravity.value == "simulated_partial":
            continue
        groups.setdefault(e.investigation, []).append(e)
    return groups


def build_corpus(raw_dir: Path = RAW_DIR, out: Path = CORPUS) -> list[dict]:
    from ember.registry import load_registry

    reg = load_registry()
    docs = []
    for inv, evs in sorted(rankable_investigations(reg.evidence).items()):
        parts, used = [inv], []
        for psi_id in sorted({e.psi_id for e in evs if e.psi_id}):
            rec = raw_dir / psi_id / f"{psi_id}_record.json"
            if rec.exists():
                d = json.loads(rec.read_text())
                parts += [_clean(d.get(k)) for k in RECORD_FIELDS if d.get(k)]
                used.append(f"{psi_id} record")
        if not any(e.psi_id for e in evs):
            for sid in sorted({s for e in evs for s in e.sources if s.startswith("NTRS-")}):
                cit = raw_dir / sid / f"{sid}_citation.json"
                if cit.exists():
                    d = json.loads(cit.read_text())
                    parts += [d.get("title") or "", _clean(d.get("abstract"))]
                    used.append(f"{sid} abstract")
        ids = {e.evidence_id for e in evs}
        for c in reg.claims:
            if c.evidence_id in ids:
                parts.append(c.text)
                used.append(c.claim_id)
        docs.append(
            {
                "doc_id": inv,
                "text": " ".join(p for p in parts if p),
                "text_sources": used,
                "n_evidence": len(evs),
                "psi_ids": sorted({e.psi_id for e in evs if e.psi_id}),
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs))
    return docs


def load_corpus(path: Path = CORPUS) -> list[dict]:
    if not path.exists():
        return build_corpus(out=path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


if __name__ == "__main__":
    for d in build_corpus():
        print(
            f"{d['doc_id']:<28} words={len(d['text'].split()):>5}  from {', '.join(d['text_sources'])}"
        )
