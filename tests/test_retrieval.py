"""T13: retrieval baselines and the common system interface."""

import pytest

from ember.engine.score import collapse, rank
from ember.registry import load_registry
from ember.retrieval.additive import additive_score
from ember.retrieval.bm25 import BM25Retriever, tokenize
from ember.retrieval.corpus import load_corpus
from ember.retrieval.hybrid import rrf
from ember.retrieval.systems import Query, build_systems
from tests.conftest import ev


@pytest.fixture(scope="module")
def built():
    return build_systems()


def S(phen, x=None, p=None, fuel=None, g=0.0):
    return {
        "x_o2": x,
        "p_kpa": p,
        "u_cms": None,
        "gravity_g0": g,
        "phenomenon": phen,
        "fuel_class": fuel,
        "fuel_name": None,
    }


def test_corpus_one_doc_per_rankable_investigation_from_source_text_only():
    docs = load_corpus()
    pool = {
        e.investigation for e in load_registry().evidence if e.gravity.value != "simulated_partial"
    }
    assert {d["doc_id"] for d in docs} == pool
    for d in docs:
        assert d["text_sources"] and len(d["text"].split()) > 100, d["doc_id"]
        # Text baselines must not see EMBER's structured vocabulary.
        for token in ("spread_opposed", "limiting_oxygen", "per_test_table", "x_o2", "p_kpa"):
            assert token not in d["text"], (d["doc_id"], token)
    assert "LUCI (non-PSI)" not in pool


def test_tokenize_and_bm25():
    assert tokenize("The CO2 vs. helium droplet-flame") == ["co2", "vs", "helium", "droplet-flame"]
    r = BM25Retriever(load_corpus())
    assert (
        r.rank("CO2 vs helium as droplet flame suppressants.")[0] == "FLEX"
    )  # gold-set bank query 17
    assert r.rank("smoke particle size distribution pyrolysis")[0] == "SAME-R"


def test_rrf_math():
    assert rrf([["a", "b", "c"], ["b", "a", "c"]]) == [
        "a",
        "b",
        "c",
    ]  # a,b tie at 1/61+1/62 → name order
    assert rrf([["a", "b"], ["b", "c"]])[0] == "b"  # 1/62 + 1/61 beats 1/61


def test_additive_hand_computed():
    e = ev("E", x_o2_min=0.20, x_o2_max=0.22, p_kpa_min=100.0, p_kpa_max=102.0)
    r = additive_score(S("spread_opposed", 0.27, 56.5, "thick_solid"), e)
    # 35 phen + 25 fuel + 20·(1−0.05/0.10) + 10·(1−43.5/50) + 10 quality
    assert r["parts"] == pytest.approx(
        {"phenomenon": 35, "fuel": 25, "o2": 10.0, "pressure": 1.3, "quality": 10}
    )
    assert r["score"] == pytest.approx(81.3)
    unknown = additive_score(S("spread_opposed", 0.27, 56.5), ev("U"))
    assert unknown["parts"]["o2"] == 0 and unknown["parts"]["pressure"] == 0


def test_every_system_returns_a_permutation_of_the_pool(built):
    systems, unavailable = built
    pool = sorted(systems["random"].pool)
    q = Query(
        "Fabric flammability in a lunar habitat at 34% O2, 8.2 psia.",
        S("spread_concurrent", 0.34, 56.5, "thin_solid", 0.166),
    )
    for name, sys_ in systems.items():
        assert sorted(sys_.rank(q)) == pool, name
    assert set(systems) | set(unavailable) == {
        "random",
        "bm25",
        "dense",
        "hybrid",
        "additive",
        "ember",
    }


def test_random_is_seeded_and_query_dependent(built):
    r = built[0]["random"]
    a, b = Query("q one"), Query("q two")
    assert r.rank(a) == r.rank(a) and r.rank(a) != r.rank(b)


def test_ember_system_matches_collapsed_engine_ranking(built):
    systems, _ = built
    s = S("spread_opposed", 0.34, 56.5, "thin_solid", 0.166)
    expected = [r["investigation"] for r in collapse(rank(s, load_registry().evidence_dicts()))]
    assert systems["ember"].rank(Query("x", s)) == expected
    for name in ("ember", "additive"):
        with pytest.raises(ValueError):
            systems[name].rank(Query("text only"))


def test_dense_and_hybrid(built):
    systems, unavailable = built
    if "dense" in unavailable:
        pytest.skip(unavailable["dense"])
    q = Query("Smoke particle size from Kapton or Teflon pyrolysis.")
    assert systems["dense"].rank(q)[0] == "SAME-R"
    assert systems["hybrid"].rank(q)[0] == "SAME-R"
    assert systems["dense"].rank(Query("CO2 vs helium as droplet flame suppressants."))[0] == "FLEX"
