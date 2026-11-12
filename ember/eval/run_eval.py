"""Evaluation harness (spec §12, ticket T14): all systems × all gold queries → results.json.

    uv run python -m ember.eval.run_eval

Without final human labels (ember/eval/gold/qrels_final.csv) the harness still runs every system and
records each ranking, but writes ``status: "pending_labels"`` and NO metrics: the Validation page then
shows "pending" instead of placeholder numbers (spec §13). With labels it reports, per system, mean
nDCG@5, Recall@5 and MRR with 95% bootstrap CIs over queries, a paired permutation test of EMBER
against the best baseline, the ablations, and the spec §12.5 falsification verdict.

Query sets:
  scenario queries  have a confirmed Scenario; every system is scored on them (the paired comparison).
  text-only queries scenario: null; only text systems can answer them; reported separately.
  gap queries       no investigation labelled ≥ 2; excluded from the means and listed (expected for
                    partial gravity, water mist, 8.2-psia smoke data).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import yaml

from ember.eval.ablations import ABLATIONS
from ember.eval.gold_tools import GOLD_DIR, GoldError, final_qrels, status
from ember.eval.metrics import (
    bootstrap_ci,
    evaluable,
    mrr,
    ndcg_at_k,
    paired_permutation,
    recall_at_k,
)
from ember.paths import ROOT
from ember.retrieval.systems import EmberSystem, Query, build_systems

RESULTS = ROOT / "ember" / "eval" / "results.json"
BASELINES = ("bm25", "dense", "hybrid", "additive")
METRICS = {
    "ndcg@5": lambda r, q: ndcg_at_k(r, q, 5),
    "recall@5": lambda r, q: recall_at_k(r, q, 5),
    "mrr": mrr,
}


def scenario_dict(sc: dict | None) -> dict | None:
    if sc is None:
        return None
    base = {
        "x_o2": None,
        "p_kpa": None,
        "u_cms": None,
        "gravity_g0": None,
        "fuel_class": None,
        "fuel_name": None,
        "flow_direction": None,
    }
    return {**base, **sc}


def load_gold_queries(gold_dir: Path = GOLD_DIR) -> list[Query]:
    qs = yaml.safe_load((gold_dir / "queries.yaml").read_text())
    return [
        Query(text=q["text"], scenario=scenario_dict(q.get("scenario")), qid=q["qid"]) for q in qs
    ]


def summarize(values: list[float]) -> dict:
    m, lo, hi = bootstrap_ci(values)
    return {"mean": m, "ci95": [lo, hi], "n": len(values)}


def run(
    gold_dir: Path = GOLD_DIR,
    out: Path | None = RESULTS,
    systems: dict | None = None,
    unavailable: dict | None = None,
) -> dict:
    queries = load_gold_queries(gold_dir)
    if systems is None:
        systems, unavailable = build_systems()
    unavailable = dict(unavailable or {})
    ember = systems["ember"]
    variants = {
        f"ember:{k}": EmberSystem(ember.ev, ember.pool, overrides=ov, name=f"ember:{k}")
        for k, ov in ABLATIONS.items()
    }
    all_systems = {**systems, **variants}

    rankings: dict[str, dict[str, list[str]]] = {name: {} for name in all_systems}
    for q in queries:
        for name, s in all_systems.items():
            if s.needs == "scenario" and q.scenario is None:
                continue
            rankings[name][q.qid] = s.rank(q)

    gold_status = status(gold_dir)
    result: dict = {
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "pool": sorted(ember.pool),
        "n_queries": len(queries),
        "n_scenario_queries": sum(q.scenario is not None for q in queries),
        "gold": gold_status,
        "unavailable": unavailable,
        "systems": sorted(systems),
        "ablations": sorted(ABLATIONS),
        "rankings_top5": {
            name: {qid: r[:5] for qid, r in by_q.items()} for name, by_q in rankings.items()
        },
    }
    try:
        qrels = final_qrels(gold_dir)
    except GoldError as exc:
        result.update(status="error", error=str(exc))
        qrels = None
    if qrels is None:
        result.setdefault("status", "pending_labels")
        result["message"] = (
            "No final human labels yet: rankings are recorded, metrics are not computed. "
            "Label qrels_A.csv and qrels_B.csv per GUIDELINE.md, then merge and freeze."
        )
        if out:
            out.write_text(json.dumps(result, indent=1))
        return result

    scen_q = [q.qid for q in queries if q.scenario is not None and evaluable(qrels.get(q.qid, {}))]
    text_q = [q.qid for q in queries if q.scenario is None and evaluable(qrels.get(q.qid, {}))]
    gap_q = [q.qid for q in queries if not evaluable(qrels.get(q.qid, {}))]
    per_query: dict[str, dict[str, dict[str, float]]] = {}
    for name, by_q in rankings.items():
        per_query[name] = {
            qid: {m: f(r, qrels[qid]) for m, f in METRICS.items()}
            for qid, r in by_q.items()
            if qid in qrels
        }

    def table(names, qids):
        return {
            n: {
                m: summarize([per_query[n][q][m] for q in qids if q in per_query[n]])
                for m in METRICS
            }
            for n in names
        }

    main_names = [n for n in ("random", *BASELINES, "ember") if n in systems]
    result["scenario_queries"] = {"qids": scen_q, "metrics": table(main_names, scen_q)}
    result["text_only_queries"] = {
        "qids": text_q,
        "metrics": table([n for n in main_names if systems[n].needs == "text"], text_q),
    }
    result["gap_queries"] = gap_q
    result["ablation_metrics"] = table(["ember", *variants], scen_q)

    avail = [b for b in BASELINES if b in systems]
    best = (
        max(avail, key=lambda b: result["scenario_queries"]["metrics"][b]["ndcg@5"]["mean"])
        if avail and scen_q
        else None
    )
    if best:
        e = result["scenario_queries"]["metrics"]["ember"]["ndcg@5"]
        bm = result["scenario_queries"]["metrics"][best]["ndcg@5"]
        perm = paired_permutation(
            [per_query["ember"][q]["ndcg@5"] for q in scen_q],
            [per_query[best][q]["ndcg@5"] for q in scen_q],
        )
        overlap = not (e["ci95"][0] > bm["ci95"][1])
        better = e["mean"] > bm["mean"] and not overlap
        result["comparison"] = {
            "best_baseline": best,
            "ember_ndcg5": e,
            "baseline_ndcg5": bm,
            "permutation": perm,
            "ci_overlap": overlap,
            "verdict": "ember_better" if better else "not_better",
            "statement": (
                f"EMBER beats the best baseline ({best}) on nDCG@5 with non-overlapping 95% CIs."
                if better
                else f"EMBER does NOT beat the best baseline ({best}) on nDCG@5 (CIs overlap or mean not higher). "
                "Per spec §12.5 the claim narrows to interpretability + gap mapping."
            ),
        }
    result["status"] = "complete"
    result["per_query"] = per_query
    if out:
        out.write_text(json.dumps(result, indent=1))
    return result


def comparelab_validation() -> dict:
    """CompareLab on the labeled pair set (separate from the gold set)."""
    from ember.engine.comparelab import (
        compare_evidence,
        compare_measurements,
        false_comparable_rate,
    )
    from ember.registry import load_registry

    reg = load_registry()
    E, M = reg.evidence_by_id(), {m.measurement_id: m for m in reg.measurements}
    pairs = yaml.safe_load((ROOT / "ember" / "eval" / "comparelab_pairs.yaml").read_text())
    res = []
    for p in pairs:
        if p["kind"] == "evidence":
            r = compare_evidence(E[p["a"]], E[p["b"]])
        else:
            r = compare_measurements(
                M[p["a"]], E[M[p["a"]].evidence_id], M[p["b"]], E[M[p["b"]].evidence_id]
            )
        res.append((r["verdict"], p["label"]))
    return {
        **false_comparable_rate(res),
        "target_pairs": 60,
        "labelled_by": "starter set from spec statements; second annotator pending",
    }


def main() -> int:
    r = run()
    r_cl = comparelab_validation()
    data = json.loads(RESULTS.read_text())
    data["comparelab"] = r_cl
    from ember.eval.adversarial import run_adversarial  # noqa: PLC0415 - keeps eval import light

    r_adv = run_adversarial()
    data["adversarial"] = r_adv
    RESULTS.write_text(json.dumps(data, indent=1))
    print(
        f"status: {r['status']}  ({r['n_queries']} queries, {r['n_scenario_queries']} with scenarios; systems {r['systems']})"
    )
    if r.get("unavailable"):
        print(f"unavailable: {r['unavailable']}")
    g = r["gold"]
    print(
        f"gold labels: A {g['labeled_A']}/{g['pairs']}, B {g['labeled_B']}/{g['pairs']}, final {g['final']}, frozen={g['frozen']}"
    )
    if r["status"] == "complete":
        for n, ms in r["scenario_queries"]["metrics"].items():
            x = ms["ndcg@5"]
            print(f"  {n:<9} nDCG@5 {x['mean']:.3f} [{x['ci95'][0]:.3f}, {x['ci95'][1]:.3f}]")
        if "comparison" in r:
            print(r["comparison"]["statement"])
    else:
        print(r.get("message") or r.get("error"))
    print(
        f"Adversarial: prompts {r_adv['prompt_pass_rate']:.0%} of {r_adv['n_prompts']}, "
        f"probes {r_adv['probe_pass_rate']:.0%} of {r_adv['n_probes']} ({', '.join(r_adv['narrator_modes'])})"
    )
    print(
        f"CompareLab: {r_cl['false_comparable']} false-comparable of {r_cl['n']} pairs (target 60 pairs)"
    )
    print(f"→ {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
