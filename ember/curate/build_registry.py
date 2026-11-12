"""Build the curated registry from seeds (+ parsed/accepted tables later) into Parquet + DuckDB.

Spec §9.7 / ticket T05. Everything written here has passed pydantic validation (§8), so no
``known`` value lacks a source and locator. Integrity checks (dangling source ids, duplicate
ids, sources missing from the manifest) fail the build loudly rather than being patched.

Usage:
    uv run python -m ember.curate.build_registry [--seed-dir DIR] [--out-dir DIR] [--manifest CSV]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from ember.ingest.extract_llm import REVIEW_DIR
from ember.ingest.extract_psi import EXTRACTED_DIR, load_extracted
from ember.paths import CURATED_DIR, MANIFEST_CSV, SEED_DIR
from ember.schemas import Claim, Evidence, Measurement, Range, Relation, Source

RANGE_FIELDS = ("x_o2", "p_kpa", "u_cms", "size_cm")
TABLES = ("sources", "evidence", "measurements", "claims", "relations")
TODO_MARKERS = ("todo", "verify")


class RegistryIntegrityError(Exception):
    pass


# ------------------------------------------------------------------------------- loading seeds
def _load_yaml_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        data = yaml.safe_load(f) or []
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a YAML list")
    return data


def load_seed_models(seed_dir: Path = SEED_DIR) -> dict[str, list]:
    """Load and validate every seed file. Raises pydantic ValidationError on bad rows."""
    return {
        "sources": [Source(**r) for r in _load_yaml_list(seed_dir / "sources_seed.yaml")],
        "evidence": [Evidence(**r) for r in _load_yaml_list(seed_dir / "evidence_seed.yaml")],
        "measurements": [
            Measurement(**r) for r in _load_yaml_list(seed_dir / "measurements_seed.yaml")
        ],
        "claims": [Claim(**r) for r in _load_yaml_list(seed_dir / "claims_seed.yaml")],
        "relations": [Relation(**r) for r in _load_yaml_list(seed_dir / "relations_seed.yaml")],
    }


def read_manifest(path: Path = MANIFEST_CSV) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------------- flattening
def _flatten_range(prefix: str, r: Range | None) -> dict:
    if r is None:
        r = Range(status="not_applicable")
    return {
        f"{prefix}_min": r.min,
        f"{prefix}_max": r.max,
        f"{prefix}_status": r.status,
        f"{prefix}_source_id": r.source_id,
        f"{prefix}_source_locator": r.source_locator,
    }


def evidence_to_row(e: Evidence) -> dict:
    row = {
        "evidence_id": e.evidence_id,
        "investigation": e.investigation,
        "psi_id": e.psi_id,
        "hardware_family": e.hardware_family,
        "fuel_class": e.fuel_class.value,
        "fuel_name": e.fuel_name,
        "geometry": e.geometry,
        "phenomena": [p.value for p in e.phenomena],
        "gravity": e.gravity.value,
        "o2_context": e.o2_context.value,
        "flow_direction": e.flow_direction,
        "diluent": e.diluent,
        "enclosure_note": e.enclosure_note,
        "granularity": e.granularity.value,
        "measurements": list(e.measurements),
        "tensions": list(e.tensions),
        "sources": list(e.sources),
    }
    for k in RANGE_FIELDS:
        row.update(_flatten_range(k, getattr(e, k)))
    return row


def row_to_evidence(row: dict) -> Evidence:
    """Inverse of evidence_to_row (handles numpy arrays / NaN coming back from Parquet)."""

    def clean(v):
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    def as_list(v):
        if v is None:
            return []
        return [str(x) for x in list(v)]

    def rng(prefix: str) -> dict | None:
        status = clean(row.get(f"{prefix}_status"))
        if status is None:
            return None
        return {
            "min": clean(row.get(f"{prefix}_min")),
            "max": clean(row.get(f"{prefix}_max")),
            "status": status,
            "source_id": clean(row.get(f"{prefix}_source_id")),
            "source_locator": clean(row.get(f"{prefix}_source_locator")),
        }

    size = rng("size_cm")
    return Evidence(
        evidence_id=row["evidence_id"],
        investigation=row["investigation"],
        psi_id=clean(row.get("psi_id")),
        hardware_family=row["hardware_family"],
        fuel_class=row["fuel_class"],
        fuel_name=clean(row.get("fuel_name")),
        geometry=clean(row.get("geometry")),
        size_cm=None
        if size is None or size["status"] == "not_applicable" and size["min"] is None
        else size,
        phenomena=as_list(row.get("phenomena")),
        gravity=row["gravity"],
        x_o2=rng("x_o2"),
        o2_context=row["o2_context"],
        p_kpa=rng("p_kpa"),
        u_cms=rng("u_cms"),
        flow_direction=clean(row.get("flow_direction")) or "unknown",
        diluent=clean(row.get("diluent")),
        enclosure_note=clean(row.get("enclosure_note")),
        granularity=row["granularity"],
        measurements=as_list(row.get("measurements")),
        tensions=as_list(row.get("tensions")),
        sources=as_list(row.get("sources")),
    )


def models_to_frames(models: dict[str, list]) -> dict[str, pd.DataFrame]:
    frames = {
        "sources": pd.DataFrame([m.model_dump() for m in models["sources"]]),
        "evidence": pd.DataFrame([evidence_to_row(e) for e in models["evidence"]]),
        "measurements": pd.DataFrame([m.model_dump() for m in models["measurements"]]),
        "claims": pd.DataFrame([m.model_dump() for m in models["claims"]]),
        "relations": pd.DataFrame([m.model_dump() for m in models["relations"]]),
    }
    # Keep column sets stable even when a table is empty.
    for name, model in (
        ("sources", Source),
        ("measurements", Measurement),
        ("claims", Claim),
        ("relations", Relation),
    ):
        if frames[name].empty:
            frames[name] = pd.DataFrame(columns=list(model.model_fields))
    return frames


# ------------------------------------------------------------------------------------ integrity
def check_integrity(models: dict[str, list], manifest: list[dict]) -> list[str]:
    """Return a list of integrity problems (empty list = OK)."""
    problems: list[str] = []
    source_ids = [s.source_id for s in models["sources"]]
    sset = set(source_ids)
    manifest_ids = {r["source_id"] for r in manifest}

    def dup(ids: list[str], label: str):
        seen, d = set(), set()
        for i in ids:
            (d if i in seen else seen).add(i)
        for i in sorted(d):
            problems.append(f"duplicate {label} id: {i}")

    dup(source_ids, "source")
    dup([e.evidence_id for e in models["evidence"]], "evidence")
    dup([m.measurement_id for m in models["measurements"]], "measurement")
    dup([c.claim_id for c in models["claims"]], "claim")
    dup([r.relation_id for r in models["relations"]], "relation")

    for sid in sorted(sset - manifest_ids):
        problems.append(f"source not in manifest: {sid}")

    eids = {e.evidence_id for e in models["evidence"]}
    for e in models["evidence"]:
        if not e.sources:
            problems.append(f"{e.evidence_id}: no sources")
        for sid in e.sources:
            if sid not in sset:
                problems.append(f"{e.evidence_id}: unknown source {sid}")
        for k in RANGE_FIELDS:
            r = getattr(e, k)
            if r is not None and r.source_id and r.source_id not in sset:
                problems.append(f"{e.evidence_id}.{k}: unknown source {r.source_id}")
            if r is not None and r.status == "known" and (not r.source_id or not r.source_locator):
                problems.append(f"{e.evidence_id}.{k}: known value without provenance")
    for m in models["measurements"]:
        if m.evidence_id not in eids:
            problems.append(f"{m.measurement_id}: unknown evidence {m.evidence_id}")
        if m.source_id not in sset:
            problems.append(f"{m.measurement_id}: unknown source {m.source_id}")
    for c in models["claims"]:
        if c.evidence_id is not None and c.evidence_id not in eids:
            problems.append(f"{c.claim_id}: unknown evidence {c.evidence_id}")
        if c.source_id not in sset:
            problems.append(f"{c.claim_id}: unknown source {c.source_id}")
    for r in models["relations"]:
        if r.source_id not in sset:
            problems.append(f"{r.relation_id}: unknown source {r.source_id}")
    return problems


def review_todos(models: dict[str, list]) -> list[dict]:
    """Every provenance locator still marked TODO/verify. These block a 'reviewed' registry."""
    out = []

    def is_todo(loc: str | None) -> bool:
        return bool(loc) and any(m in loc.lower() for m in TODO_MARKERS)

    for e in models["evidence"]:
        for k in RANGE_FIELDS:
            r = getattr(e, k)
            if r is not None and is_todo(r.source_locator):
                out.append(
                    {
                        "table": "evidence",
                        "id": e.evidence_id,
                        "field": k,
                        "status": r.status,
                        "source_id": r.source_id,
                        "source_locator": r.source_locator,
                    }
                )
    for m in models["measurements"]:
        if is_todo(m.source_locator):
            out.append(
                {
                    "table": "measurements",
                    "id": m.measurement_id,
                    "field": m.quantity,
                    "status": m.value_kind,
                    "source_id": m.source_id,
                    "source_locator": m.source_locator,
                }
            )
    for c in models["claims"]:
        if is_todo(c.source_locator):
            out.append(
                {
                    "table": "claims",
                    "id": c.claim_id,
                    "field": "text",
                    "status": c.claim_type.value,
                    "source_id": c.source_id,
                    "source_locator": c.source_locator,
                }
            )
    return out


# --------------------------------------------------------------------------------------- build
def apply_reviews(evidence: list[Evidence], records: list[dict]) -> tuple[list[str], list[str]]:
    """Write human-accepted paper values (data/review/accepted.jsonl) onto evidence, in place.

    Only records with ``reviewed_by`` arrive here. The accepted range replaces the field, keeps the
    reviewer and date in the locator, and adds the paper to the record's sources.
    Returns (applied review ids, problems).
    """
    index = {e.evidence_id: i for i, e in enumerate(evidence)}
    applied, problems = [], []
    for r in records:
        i = index.get(r["evidence_id"])
        if i is None:
            problems.append(f"review {r.get('review_id')}: unknown evidence {r['evidence_id']}")
            continue
        e = evidence[i]
        rng = Range(
            min=r["min"],
            max=r["max"],
            status="known",
            source_id=r["source_id"],
            source_locator=f"{r['source_locator']} · reviewed by {r['reviewed_by']} {r['reviewed_at'][:10]}",
        )
        sources = e.sources if r["source_id"] in e.sources else [*e.sources, r["source_id"]]
        evidence[i] = e.model_copy(update={r["field"]: rng, "sources": sources})
        applied.append(r.get("review_id", "?"))
    return applied, problems


def load_all_models(
    seed_dir: Path = SEED_DIR,
    extracted_dir: Path | None = EXTRACTED_DIR,
    review_dir: Path | None = None,
) -> dict[str, list]:
    """Seeds (hand-entered, sourced) + rows extracted from PSI tables (data/extracted/*.jsonl),
    optionally with human-accepted paper values applied (``review_dir``)."""
    models = load_seed_models(seed_dir)
    ev, ms = load_extracted(extracted_dir) if extracted_dir is not None else ([], [])
    models["evidence"] = models["evidence"] + ev
    models["measurements"] = models["measurements"] + ms
    if review_dir is not None:
        from ember.curate.review_cli import accepted_records

        apply_reviews(models["evidence"], accepted_records(review_dir))
    return models


def build(
    seed_dir: Path = SEED_DIR,
    out_dir: Path = CURATED_DIR,
    manifest_path: Path = MANIFEST_CSV,
    extracted_dir: Path | None = EXTRACTED_DIR,
    review_dir: Path | None = REVIEW_DIR,
) -> dict:
    n_seed = len(load_seed_models(seed_dir)["evidence"])
    models = load_all_models(seed_dir, extracted_dir)
    applied, review_problems = [], []
    if review_dir is not None:
        from ember.curate.review_cli import accepted_records

        applied, review_problems = apply_reviews(models["evidence"], accepted_records(review_dir))
    manifest = read_manifest(manifest_path)
    problems = review_problems + check_integrity(models, manifest)
    if problems:
        raise RegistryIntegrityError("\n".join(problems))

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = models_to_frames(models)
    for name in TABLES:
        frames[name].to_parquet(out_dir / f"{name}.parquet", index=False)

    todos = review_todos(models)
    pd.DataFrame(
        todos, columns=["table", "id", "field", "status", "source_id", "source_locator"]
    ).to_csv(out_dir / "review_todo.csv", index=False)

    db_path = out_dir / "ember.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    try:
        for name in TABLES:
            con.execute(
                f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_parquet(?)",
                [str(out_dir / f"{name}.parquet")],
            )
    finally:
        con.close()

    summary = {
        "counts": {name: len(models[name]) for name in TABLES},
        "known_ranges": sum(
            1
            for e in models["evidence"]
            for k in RANGE_FIELDS
            if getattr(e, k) is not None and getattr(e, k).status == "known"
        ),
        "review_todos": len(todos),
        "evidence_from_seed": n_seed,
        "evidence_from_tables": len(models["evidence"]) - n_seed,
        "reviews_applied": len(applied),
        "out_dir": str(out_dir),
    }
    (out_dir / "build_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--seed-dir", type=Path, default=SEED_DIR)
    ap.add_argument("--out-dir", type=Path, default=CURATED_DIR)
    ap.add_argument("--manifest", type=Path, default=MANIFEST_CSV)
    ap.add_argument("--seed-only", action="store_true", help="ignore data/extracted")
    args = ap.parse_args(argv)
    try:
        summary = build(
            args.seed_dir, args.out_dir, args.manifest, None if args.seed_only else EXTRACTED_DIR
        )
    except RegistryIntegrityError as exc:
        print("Registry integrity problems:\n" + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
