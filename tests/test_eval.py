"""T14: metrics, gold tooling, ablations and the evaluation harness.

Labels used here are SYNTHETIC and live only in temporary folders; they test the machinery and say
nothing about EMBER's quality. The real annotator sheets are never written by tests.
"""

import csv
import math
import shutil

import numpy as np
import pytest
import yaml
from streamlit.testing.v1 import AppTest

from ember.engine.distance import dimension_distance, transfer_distance
from ember.engine.score import score
from ember.eval import gold_tools as G
from ember.eval.ablations import ABLATIONS
from ember.eval.metrics import (
    bootstrap_ci,
    evaluable,
    mrr,
    ndcg_at_k,
    paired_permutation,
    recall_at_k,
    weighted_kappa,
)
from ember.eval.run_eval import load_gold_queries, run
from ember.paths import ROOT
from ember.retrieval.systems import build_systems
from tests.conftest import ev

REAL_GOLD = ROOT / "ember" / "eval" / "gold"


# ------------------------------------------------------------------------------------- metrics
def test_ndcg_recall_mrr_hand_computed():
    rels = {"a": 3, "b": 2, "c": 0, "d": 1}
    ranked = ["c", "a", "d", "b"]
    dcg = 7 / math.log2(3) + 1 / math.log2(4) + 3 / math.log2(5)
    idcg = 7 / 1 + 3 / math.log2(3) + 1 / math.log2(4)
    assert ndcg_at_k(ranked, rels, 5) == pytest.approx(dcg / idcg)
    assert ndcg_at_k(["a", "b", "d", "c"], rels, 5) == pytest.approx(1.0)
    assert recall_at_k(ranked, rels, 2) == 0.5  # relevant = {a, b}; top-2 holds a
    assert mrr(ranked, rels) == 0.5
    assert ndcg_at_k(ranked, {"a": 0}, 5) == 0.0 and not evaluable({"a": 1}) and evaluable({"a": 2})


def test_bootstrap_and_permutation():
    m, lo, hi = bootstrap_ci([0.2, 0.4, 0.6, 0.8], seed=1)
    assert (
        m == pytest.approx(0.5)
        and lo <= m <= hi
        and bootstrap_ci([0.2, 0.4, 0.6, 0.8], seed=1) == (m, lo, hi)
    )
    same = paired_permutation([0.5] * 10, [0.5] * 10)
    assert same["mean_diff"] == 0 and same["p_value"] == pytest.approx(1.0)
    clear = paired_permutation([1.0] * 12, [0.0] * 12)
    assert clear["p_value"] < 0.01


def test_weighted_kappa():
    assert weighted_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == pytest.approx(1.0)
    a, b = [0, 1, 2, 3, 3, 0], [0, 2, 2, 3, 1, 0]
    assert weighted_kappa(a, b) == pytest.approx(weighted_kappa(b, a))
    assert weighted_kappa([0, 0, 3, 3], [3, 3, 0, 0]) < 0
    assert weighted_kappa(a, b, weights="quadratic") != weighted_kappa(a, b, weights="linear")


# ---------------------------------------------------------------------------------- ablations
def test_distance_modes_hand_computed():
    assert dimension_distance(0.34, 0.136, 0.222, "midpoint_log") == pytest.approx(
        abs(np.log(0.34 / 0.179))
    )
    assert dimension_distance(0.34, 0.136, 0.222, "interval_linear") == pytest.approx(
        (0.34 - 0.222) / 0.34
    )
    assert dimension_distance(0.2, 0.136, 0.222, "interval_linear") == 0.0
    assert (
        dimension_distance(0.2, 0.136, 0.222, "midpoint_log") > 0
    )  # midpoint never 0 inside a range
    s = {"x_o2": 0.34, "p_kpa": 56.5, "u_cms": None, "phenomenon": "spread_opposed"}
    e = ev(x_o2_min=0.21, x_o2_max=0.21, p_kpa_min=101.0, p_kpa_max=101.0)
    assert transfer_distance(s, e, "spread_opposed")[0] == pytest.approx(
        0.463, abs=0.002
    )  # default unchanged
    with pytest.raises(ValueError):
        dimension_distance(1, 1, 1, "bogus")


def test_ablation_overrides_change_what_they_claim():
    s = {
        "x_o2": 0.34,
        "p_kpa": 56.5,
        "u_cms": None,
        "gravity_g0": None,
        "phenomenon": "spread_opposed",
        "fuel_class": "thin_solid",
        "fuel_name": None,
    }
    paper = ev(
        "P",
        granularity="paper_only",
        fuel_class="thick_solid",
        phenomena=["extinction"],
        x_o2_min=0.21,
        x_o2_max=0.21,
        p_kpa_min=101.0,
        p_kpa_max=101.0,
    )
    base = score(s, paper)
    assert score(s, paper, ABLATIONS["no_Q"])["priors"]["Q"] == 1.0 and base["priors"]["Q"] == 0.3
    assert score(s, paper, ABLATIONS["no_Mf"])["priors"]["m_f"] == 1.0
    assert score(s, paper, ABLATIONS["no_Mphi"])["priors"]["m_phi"] == 1.0
    assert score(s, paper, ABLATIONS["uniform_eps"])["D"] == pytest.approx(
        0.4818 + 0.5809, abs=0.002
    )
    assert score(s, paper, ABLATIONS["midpoint"])["D"] == pytest.approx(
        base["D"]
    )  # point evidence: midpoint = edge


# ------------------------------------------------------------------------------- gold tooling
def test_real_gold_queries_and_blank_sheets():
    qs = load_gold_queries(REAL_GOLD)
    assert len(qs) == 40 and len({q.qid for q in qs}) == 40
    assert sum(q.scenario is not None for q in qs) == 36
    rows = G.read_sheet(REAL_GOLD / "qrels_A.csv")
    docs = G.pool_docs()
    assert len(rows) == 40 * len(docs)
    assert [r["doc_id"] for r in rows[: len(docs)]] == sorted(
        docs
    )  # alphabetical, never ranked order
    assert G.read_sheet(REAL_GOLD / "qrels_B.csv") and (REAL_GOLD / "GUIDELINE.md").exists()


def _tmp_gold(tmp_path, n_queries=None):
    d = tmp_path / "gold"
    d.mkdir()
    qs = yaml.safe_load((REAL_GOLD / "queries.yaml").read_text())
    if n_queries:
        qs = qs[:n_queries]
    (d / "queries.yaml").write_text(yaml.safe_dump(qs, sort_keys=False))
    G.write_templates(d)
    return d


def _fill(path, fn):
    rows = G.read_sheet(path)
    for r in rows:
        r["label"] = str(fn(r))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=G.FIELDS)
        w.writeheader()
        w.writerows(rows)


def test_merge_adjudicate_freeze_and_tamper_detection(tmp_path):
    d = _tmp_gold(tmp_path, n_queries=3)
    with pytest.raises(G.GoldError, match="complete"):
        G.merge(d)
    _fill(d / "qrels_A.csv", lambda r: 3 if r["doc_id"] == "FLEX" else 0)
    _fill(
        d / "qrels_B.csv",
        lambda r: 1 if r["doc_id"] == "FLEX" else (1 if r["doc_id"] == "BASS" else 0),
    )
    with pytest.raises(G.GoldError, match="already has labels"):
        G.write_templates(d)
    m = G.merge(d)
    assert len(m["unresolved"]) == 3 and -1 <= m["kappa_linear"] <= 1  # FLEX 3 vs 1 in every query
    assert G.final_qrels(d) is None  # unresolved rows block final labels
    with pytest.raises(G.GoldError, match="unresolved"):
        G.freeze(d)
    rows = G.read_sheet(d / "qrels_final.csv")
    for r in rows:
        if r["doc_id"] == "FLEX":
            r["adjudicated"] = "2"
    with (d / "qrels_final.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=G.FINAL_FIELDS)
        w.writeheader()
        w.writerows(rows)
    m2 = G.merge(d)
    assert m2["unresolved"] == []
    q = G.final_qrels(d)
    assert all(v["FLEX"] == 2 and v["BASS"] == 0 for v in q.values())  # 0 vs 1 → lower label
    G.freeze(d)
    assert G.status(d)["frozen"]
    with (d / "qrels_final.csv").open("a") as f:
        f.write("Q99,FLEX,3,3,,3\n")
    with pytest.raises(G.GoldError, match="changed after freezing"):
        G.final_qrels(d)


# ------------------------------------------------------------------------------------ harness
@pytest.fixture(scope="module")
def systems_no_dense():
    return build_systems(include_dense=False)


def test_run_eval_pending_without_labels(tmp_path, systems_no_dense):
    d = _tmp_gold(tmp_path)
    r = run(
        d,
        out=None,
        systems=systems_no_dense[0],
        unavailable={"dense": "skipped in test", "hybrid": "skipped in test"},
    )
    assert r["status"] == "pending_labels" and "scenario_queries" not in r and "comparison" not in r
    assert set(r["rankings_top5"]["ember"]) == {q.qid for q in load_gold_queries(d) if q.scenario}
    assert set(r["rankings_top5"]["bm25"]) == {q.qid for q in load_gold_queries(d)}
    assert "ember:uniform_eps" in r["rankings_top5"]


def test_run_eval_complete_with_synthetic_labels(tmp_path, systems_no_dense):
    systems, _ = systems_no_dense
    d = _tmp_gold(tmp_path)
    queries = {q.qid: q for q in load_gold_queries(d)}
    top1 = {qid: systems["ember"].rank(q)[0] for qid, q in queries.items() if q.scenario}
    gap = "Q23"  # no doc ≥ 2 → gap query

    def lab(r):
        if r["qid"] == gap:
            return 1 if r["doc_id"] == "FLEX" else 0
        if r["qid"] in top1:
            return 3 if r["doc_id"] == top1[r["qid"]] else 0
        return 2 if r["doc_id"] == "SAME-R" else 0

    _fill(d / "qrels_A.csv", lab)
    shutil.copy(d / "qrels_A.csv", d / "qrels_B.csv")
    assert G.merge(d)["kappa_linear"] == pytest.approx(1.0)
    G.freeze(d)
    r = run(d, out=None, systems=systems, unavailable={})
    assert r["status"] == "complete"
    assert gap in r["gap_queries"] and gap not in r["scenario_queries"]["qids"]
    em = r["scenario_queries"]["metrics"]["ember"]
    assert em["ndcg@5"]["mean"] == pytest.approx(1.0) and em["mrr"]["mean"] == pytest.approx(1.0)
    assert set(r["ablation_metrics"]) == {"ember", *[f"ember:{k}" for k in ABLATIONS]}
    assert r["comparison"]["best_baseline"] in {"bm25", "additive"} and r["comparison"][
        "verdict"
    ] in {"ember_better", "not_better"}
    assert set(r["text_only_queries"]["metrics"]) == {"random", "bm25"}


def test_validation_page_shows_pending_not_numbers():
    at = AppTest.from_file(str(ROOT / "app" / "pages" / "6_Validation.py"), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Validation"
    assert any("Pending" in w.value for w in at.warning)
    abl = next(d.value for d in at.dataframe if "nDCG@5" in d.value.columns)
    assert set(abl["nDCG@5"]) == {"pending"}
    heads = [h.value for h in at.subheader]
    assert heads.index("Measured now") < heads.index("Ranking benchmark: built, waiting for labels")
