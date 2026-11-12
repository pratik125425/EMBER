"""Read access to the curated registry (Parquet) as pydantic models and engine dicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ember.curate.build_registry import TABLES, build, row_to_evidence
from ember.engine.score import evidence_to_dict
from ember.paths import CURATED_DIR
from ember.schemas import Claim, Evidence, Measurement, Relation, Source


@dataclass
class Registry:
    sources: list[Source] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)

    # -- lookups ---------------------------------------------------------------------------
    def evidence_by_id(self) -> dict[str, Evidence]:
        return {e.evidence_id: e for e in self.evidence}

    def source_by_id(self) -> dict[str, Source]:
        return {s.source_id: s for s in self.sources}

    def evidence_dicts(self) -> list[dict]:
        """Engine-shaped dicts for ranking (see ember.engine.score.rank)."""
        return [evidence_to_dict(e) for e in self.evidence]

    def claims_for(self, evidence_id: str) -> list[Claim]:
        return [c for c in self.claims if c.evidence_id == evidence_id]

    def measurements_for(self, evidence_id: str) -> list[Measurement]:
        return [m for m in self.measurements if m.evidence_id == evidence_id]


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: (None if _isnan(v) else v) for k, v in r.items()} for r in df.to_dict("records")]


def _isnan(v) -> bool:
    try:
        return v is None or (isinstance(v, float) and pd.isna(v))
    except (TypeError, ValueError):
        return False


def load_registry(curated_dir: Path = CURATED_DIR, build_if_missing: bool = True) -> Registry:
    paths = {t: curated_dir / f"{t}.parquet" for t in TABLES}
    if not all(p.exists() for p in paths.values()):
        if not build_if_missing:
            raise FileNotFoundError(f"curated registry not found in {curated_dir}")
        build(out_dir=curated_dir)
    frames = {t: pd.read_parquet(p) for t, p in paths.items()}
    return Registry(
        sources=[Source(**r) for r in _records(frames["sources"])],
        evidence=[row_to_evidence(r) for r in frames["evidence"].to_dict("records")],
        measurements=[Measurement(**r) for r in _records(frames["measurements"])],
        claims=[Claim(**r) for r in _records(frames["claims"])],
        relations=[Relation(**r) for r in _records(frames["relations"])],
        frames=frames,
    )
