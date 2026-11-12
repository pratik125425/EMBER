"""Gold-set tooling: annotator sheets, agreement, merge and freeze (spec §12.1, ticket T14).

    uv run python -m ember.eval.gold_tools template   # (re)write blank qrels_A.csv / qrels_B.csv
    uv run python -m ember.eval.gold_tools status     # progress per annotator, frozen or not
    uv run python -m ember.eval.gold_tools merge      # κ, disagreements, qrels_final.csv
    uv run python -m ember.eval.gold_tools freeze     # FROZEN.json with SHA-256 of queries + final labels

Merge rule: equal labels are kept; labels one apart take the LOWER label (conservative); labels two or
more apart must be resolved by a human in the ``adjudicated`` column of qrels_final.csv.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

import yaml

from ember.eval.metrics import weighted_kappa
from ember.paths import ROOT

GOLD_DIR = ROOT / "ember" / "eval" / "gold"
QUERIES = GOLD_DIR / "queries.yaml"
FIELDS = ["qid", "doc_id", "label", "notes"]
FINAL_FIELDS = ["qid", "doc_id", "label_A", "label_B", "adjudicated", "label"]


class GoldError(Exception):
    pass


def load_queries(path: Path = QUERIES) -> list[dict]:
    return yaml.safe_load(path.read_text())


def pool_docs() -> list[str]:
    from ember.retrieval.corpus import load_corpus

    return sorted(d["doc_id"] for d in load_corpus())


def write_templates(
    gold_dir: Path = GOLD_DIR, docs: list[str] | None = None, overwrite: bool = False
) -> list[Path]:
    docs = docs or pool_docs()
    qs = load_queries(gold_dir / "queries.yaml")
    out = []
    for who in ("A", "B"):
        p = gold_dir / f"qrels_{who}.csv"
        if p.exists() and not overwrite and any(r["label"].strip() for r in read_sheet(p)):
            raise GoldError(
                f"{p.name} already has labels; refusing to overwrite (pass overwrite=True)"
            )
        with p.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for q in qs:
                for d in docs:  # alphabetical, never ranked order
                    w.writerow({"qid": q["qid"], "doc_id": d, "label": "", "notes": ""})
        out.append(p)
    return out


def read_sheet(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def labels(rows: list[dict]) -> dict[tuple[str, str], int]:
    out = {}
    for r in rows:
        v = (r.get("label") or "").strip()
        if v == "":
            continue
        if v not in {"0", "1", "2", "3"}:
            raise GoldError(f"invalid label {v!r} for {r['qid']}/{r['doc_id']} (use 0–3)")
        out[(r["qid"], r["doc_id"])] = int(v)
    return out


def status(gold_dir: Path = GOLD_DIR) -> dict:
    a, b = read_sheet(gold_dir / "qrels_A.csv"), read_sheet(gold_dir / "qrels_B.csv")
    final = read_sheet(gold_dir / "qrels_final.csv")
    frozen = (gold_dir / "FROZEN.json").exists()
    return {
        "n_queries": len(load_queries(gold_dir / "queries.yaml")),
        "pairs": len(a),
        "labeled_A": len(labels(a)),
        "labeled_B": len(labels(b)),
        "final": sum(1 for r in final if (r.get("label") or "").strip() != ""),
        "frozen": frozen,
        "frozen_info": json.loads((gold_dir / "FROZEN.json").read_text()) if frozen else None,
    }


def merge(gold_dir: Path = GOLD_DIR) -> dict:
    a = labels(read_sheet(gold_dir / "qrels_A.csv"))
    b = labels(read_sheet(gold_dir / "qrels_B.csv"))
    keys = sorted(set(a) | set(b))
    missing = [k for k in keys if k not in a or k not in b]
    pairs = len(read_sheet(gold_dir / "qrels_A.csv"))
    if not keys or missing or len(keys) < pairs:
        raise GoldError(
            f"both sheets must be complete before merging ({len(a)}/{pairs} A, {len(b)}/{pairs} B)"
        )
    prev = {
        (r["qid"], r["doc_id"]): (r.get("adjudicated") or "").strip()
        for r in read_sheet(gold_dir / "qrels_final.csv")
    }
    rows, unresolved = [], []
    for k in keys:
        la, lb = a[k], b[k]
        adj = prev.get(k, "")
        if adj:
            final = int(adj)
        elif abs(la - lb) >= 2:
            final = None
            unresolved.append(k)
        else:
            final = min(la, lb)
        rows.append(
            {
                "qid": k[0],
                "doc_id": k[1],
                "label_A": la,
                "label_B": lb,
                "adjudicated": adj,
                "label": "" if final is None else final,
            }
        )
    with (gold_dir / "qrels_final.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FINAL_FIELDS)
        w.writeheader()
        w.writerows(rows)
    la_all, lb_all = [a[k] for k in keys], [b[k] for k in keys]
    return {
        "kappa_linear": weighted_kappa(la_all, lb_all, weights="linear"),
        "kappa_quadratic": weighted_kappa(la_all, lb_all, weights="quadratic"),
        "exact_agreement": sum(x == y for x, y in zip(la_all, lb_all, strict=True)) / len(keys),
        "unresolved": [f"{q}/{d}" for q, d in unresolved],
        "n": len(keys),
    }


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze(gold_dir: Path = GOLD_DIR) -> dict:
    final = read_sheet(gold_dir / "qrels_final.csv")
    if not final or any((r.get("label") or "").strip() == "" for r in final):
        raise GoldError(
            "qrels_final.csv is missing or has unresolved rows; run merge and adjudicate first"
        )
    info = {
        "frozen_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "queries_sha256": _sha(gold_dir / "queries.yaml"),
        "qrels_final_sha256": _sha(gold_dir / "qrels_final.csv"),
        "note": "tag this commit gold-v1 before any tuning",
    }
    (gold_dir / "FROZEN.json").write_text(json.dumps(info, indent=1))
    return info


def final_qrels(gold_dir: Path = GOLD_DIR) -> dict[str, dict[str, int]] | None:
    """Final labels by query, or None if there are none. Raises if frozen files were changed."""
    path = gold_dir / "qrels_final.csv"
    rows = read_sheet(path)
    if not rows:
        return None
    if (gold_dir / "FROZEN.json").exists():
        info = json.loads((gold_dir / "FROZEN.json").read_text())
        if info["qrels_final_sha256"] != _sha(path) or info["queries_sha256"] != _sha(
            gold_dir / "queries.yaml"
        ):
            raise GoldError(
                "gold set changed after freezing (hash mismatch); restore the frozen files or re-freeze deliberately"
            )
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        if (r.get("label") or "").strip() == "":
            return None
        out.setdefault(r["qid"], {})[r["doc_id"]] = int(r["label"])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("cmd", choices=["template", "status", "merge", "freeze"])
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "template":
            for p in write_templates(overwrite=a.overwrite):
                print(f"wrote {p}")
        elif a.cmd == "status":
            print(json.dumps(status(), indent=1))
        elif a.cmd == "merge":
            print(json.dumps(merge(), indent=1))
        else:
            print(json.dumps(freeze(), indent=1))
    except GoldError as exc:
        print(f"error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
