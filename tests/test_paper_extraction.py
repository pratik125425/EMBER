"""T12: paper proposals, span check, review CLI and application to the registry (all offline)."""

import json

import pytest

from ember.curate import review_cli as R
from ember.curate.build_registry import build, load_seed_models
from ember.ingest import extract_llm as X
from ember.ingest.parse_pdf import cached_pages
from ember.paths import MANIFEST_CSV, SEED_DIR

SAFFIRE_P3 = (
    "desired condition (Table 1).\n"
    "Table 1. Saffire IV-VI Sample Test Conditions considered in this paper.\n"
    "Flight/Sample IV-1 V-2 VI-2 VI-3 VI-4\n"
    "Sample Material PMMA PMMA SIBAL PMMA SIBAL\n"
    "Ambient Pressure (kPa) 100.0 70.7 54.1 54.6 55.2\n"
    "Oxygen Concentration (mol 22.0 26.2 31.0 30.3 28.8\n"
    "%)\n"
)
PROSE = (
    "The Exploration Atmosphere is 8.2 psia with 34% oxygen. The flow\nwas 30 cm/s in the duct. "
    "The burner delivered 85% O2 to the inverse flame.\n"
)


def _write_props(tmp_path, docs):
    return X.run("rules", out_path=tmp_path / "proposals.jsonl", docs=docs)


# ---------------------------------------------------------------------------------- span check
def test_verify_exact_whitespace_and_failures():
    pages = [
        "Ambient Pressure (kPa) 100.0 70.7 54.1 54.6 55.2",
        "The flow\nwas 30 cm/s in the duct.",
    ]
    base = {"source_id": "S", "quantity": "p_kpa", "unit_as_written": "kPa"}
    ok = X.verify(
        dict(
            base,
            page=1,
            min=54.1,
            max=54.1,
            quote="Ambient Pressure (kPa) 100.0 70.7 54.1 54.6 55.2",
        ),
        pages,
    )
    assert ok["verified"] and ok["match_mode"] == "exact"
    ws = X.verify(
        dict(
            base,
            quantity="u_cms",
            unit_as_written="cm/s",
            page=2,
            min=30,
            max=30,
            quote="The flow was 30 cm/s",
        ),
        pages,
    )
    assert ws["verified"] and ws["match_mode"] == "whitespace"
    wrong_page = X.verify(
        dict(base, page=2, min=54.1, max=54.1, quote="Ambient Pressure (kPa) 100.0"), pages
    )
    assert not wrong_page["verified"] and "not found" in wrong_page["reject_reason"]
    invented = X.verify(
        dict(
            base,
            page=1,
            min=56.5,
            max=56.5,
            quote="Ambient Pressure (kPa) 100.0 70.7 54.1 54.6 55.2",
        ),
        pages,
    )
    assert not invented["verified"] and "does not appear" in invented["reject_reason"]
    bad_unit = X.verify(
        dict(
            base,
            unit_as_written="furlongs",
            page=1,
            min=54.1,
            max=54.1,
            quote="Ambient Pressure (kPa) 100.0 70.7 54.1 54.6 55.2",
        ),
        pages,
    )
    assert not bad_unit["verified"] and "unit" in bad_unit["reject_reason"]
    assert not X.verify(dict(base, page=9, min=1, max=1, quote="x"), pages)["verified"]


# ------------------------------------------------------------------------------ rules proposer
def test_rules_proposer_reads_table_columns_and_split_units():
    props = X.rule_proposals("NTRS-20240002981", [SAFFIRE_P3])
    p = {(x["quantity"], x["column"]): x for x in props if x["kind"] == "table"}
    assert p[("p_kpa", "VI-2")]["min"] == 54.1 and p[("p_kpa", "VI-4")]["min"] == 55.2
    assert p[("p_kpa", "IV-1")]["min"] == 100.0
    assert p[("x_o2", "VI-4")]["min"] == 28.8 and p[("x_o2", "VI-4")]["unit_as_written"] == "mol %"
    assert p[("x_o2", "VI-2")]["header_quote"].startswith("Flight/Sample")
    assert all(X.verify(x, [SAFFIRE_P3])["verified"] for x in props)


def test_rules_proposer_inline_and_burner_context():
    props = X.rule_proposals("S", [PROSE])
    got = {(x["quantity"], x["min"], x.get("o2_context")) for x in props}
    assert ("p_kpa", 8.2, None) in got and ("u_cms", 30.0, None) in got
    assert ("x_o2", 34.0, "ambient") in got  # "Exploration Atmosphere" sentence
    assert ("x_o2", 85.0, "burner_oxidizer_flow") in got
    assert all(X.verify(x, [PROSE])["verified"] for x in props)


def test_llm_proposer_hallucinated_quote_is_auto_rejected(tmp_path):
    def fake_complete(system, user):
        assert "Never infer" in system and "page 1" in user
        return json.dumps(
            [
                {
                    "investigation": "Saffire-VI",
                    "quantity": "p_kpa",
                    "min": 54.1,
                    "max": 55.2,
                    "unit_as_written": "kPa",
                    "o2_context": "unknown",
                    "quote": "Ambient Pressure (kPa) 100.0 70.7 54.1 54.6 55.2",
                    "page": 1,
                },
                {
                    "investigation": "Saffire-VI",
                    "quantity": "x_o2",
                    "min": 34,
                    "max": 34,
                    "unit_as_written": "%",
                    "o2_context": "ambient",
                    "quote": "Saffire VI ran at 34% oxygen",
                    "page": 1,
                },
            ]
        )

    rep = X.run(
        "llm",
        out_path=tmp_path / "proposals.jsonl",
        complete=fake_complete,
        docs=[("NTRS-20240002981", [SAFFIRE_P3])],
    )
    assert rep["n"] == 2 and rep["verified"] == 1
    rows = [json.loads(line) for line in (tmp_path / "proposals.jsonl").read_text().splitlines()]
    bad = next(r for r in rows if r["quantity"] == "x_o2")
    assert bad["verified"] is False and bad["reject_reason"] == "quote not found on the stated page"


# --------------------------------------------------------------------------------- review flow
@pytest.fixture
def review_dir(tmp_path):
    _write_props(tmp_path, [("NTRS-20240002981", [SAFFIRE_P3]), ("S", [PROSE])])
    return tmp_path


def _ids(review_dir, quantity, cols):
    props = R.load_proposals(review_dir).values()
    return [
        p["proposal_id"] for p in props if p["quantity"] == quantity and p.get("column") in cols
    ]


def _index():
    return {e.evidence_id: e for e in load_seed_models(SEED_DIR)["evidence"]}


def test_accept_merges_columns_into_canonical_envelope(review_dir):
    ids = _ids(review_dir, "x_o2", {"VI-2", "VI-3", "VI-4"})
    rec = R.accept(
        ids, "SAFFIRE6:SIBAL", "A. Reviewer", review_dir=review_dir, evidence_index=_index()
    )
    assert (rec["min"], rec["max"]) == (0.288, 0.31)  # mol % → mole fraction via pint
    assert (
        rec["field"] == "x_o2"
        and rec["source_id"] == "NTRS-20240002981"
        and rec["reviewed_by"] == "A. Reviewer"
    )
    assert "column VI-2" in rec["source_locator"] and "p.1" in rec["source_locator"]
    assert all(R.status_of(i, review_dir) == "accepted" for i in ids)
    with pytest.raises(R.ReviewError, match="already accepted"):
        R.accept(
            ids[:1], "SAFFIRE6:SIBAL", "A. Reviewer", review_dir=review_dir, evidence_index=_index()
        )


def test_accept_guards(review_dir):
    idx = _index()
    p_ids = _ids(review_dir, "p_kpa", {"VI-2"})
    with pytest.raises(R.ReviewError, match="reviewer name"):
        R.accept(p_ids, "SAFFIRE6:SIBAL", "  ", review_dir=review_dir, evidence_index=idx)
    with pytest.raises(R.ReviewError, match="unknown evidence"):
        R.accept(p_ids, "NOPE", "A", review_dir=review_dir, evidence_index=idx)
    mixed = p_ids + _ids(review_dir, "x_o2", {"VI-2"})
    with pytest.raises(R.ReviewError, match="mix quantities"):
        R.accept(mixed, "SAFFIRE6:SIBAL", "A", review_dir=review_dir, evidence_index=idx)
    burner = [
        p["proposal_id"]
        for p in R.load_proposals(review_dir).values()
        if p.get("o2_context") == "burner_oxidizer_flow"
    ]
    with pytest.raises(R.ReviewError, match="burner"):
        R.accept(burner, "BASS-II:campaign", "A", review_dir=review_dir, evidence_index=idx)
    with pytest.raises(R.ReviewError, match="does not appear"):
        R.accept(
            p_ids,
            "SAFFIRE6:SIBAL",
            "A",
            new_min=56.5,
            new_max=56.5,
            review_dir=review_dir,
            evidence_index=idx,
        )
    edited = R.accept(
        _ids(review_dir, "p_kpa", {"VI-2", "VI-4"}),
        "SAFFIRE6:SIBAL",
        "A",
        new_min=54.1,
        new_max=55.2,
        review_dir=review_dir,
        evidence_index=idx,
    )
    assert edited["edited"] and (edited["min"], edited["max"]) == (54.1, 55.2)


def test_reject_and_failed_proposals_cannot_be_accepted(review_dir):
    pid = _ids(review_dir, "p_kpa", {"IV-1"})[0]
    R.reject(pid, "A", "Saffire IV column", review_dir=review_dir)
    assert R.status_of(pid, review_dir) == "rejected"
    props = R.load_proposals(review_dir)
    bad = dict(
        next(iter(props.values())),
        proposal_id="Pbad",
        verified=False,
        reject_reason="quote not found",
    )
    with (review_dir / "proposals.jsonl").open("a") as f:
        f.write(json.dumps(bad) + "\n")
    with pytest.raises(R.ReviewError, match="span check"):
        R.accept(["Pbad"], "SAFFIRE6:SIBAL", "A", review_dir=review_dir, evidence_index=_index())


def test_build_applies_only_reviewed_values(review_dir, tmp_path):
    out = tmp_path / "curated"
    s0 = build(SEED_DIR, out, MANIFEST_CSV, extracted_dir=None, review_dir=review_dir)
    assert s0["reviews_applied"] == 0
    todos0 = s0["review_todos"]
    R.accept(
        _ids(review_dir, "p_kpa", {"VI-2", "VI-3", "VI-4"}),
        "SAFFIRE6:SIBAL",
        "A. Reviewer",
        review_dir=review_dir,
        evidence_index=_index(),
    )
    # A record without reviewed_by is ignored by the build.
    with (review_dir / "accepted.jsonl").open("a") as f:
        f.write(
            json.dumps(
                {
                    "review_id": "Rx",
                    "proposal_ids": [],
                    "evidence_id": "SAFFIRE6:PMMA",
                    "field": "p_kpa",
                    "min": 1.0,
                    "max": 1.0,
                    "source_id": "NTRS-20240002981",
                    "source_locator": "x",
                }
            )
            + "\n"
        )
    s1 = build(SEED_DIR, out, MANIFEST_CSV, extracted_dir=None, review_dir=review_dir)
    assert s1["reviews_applied"] == 1 and s1["review_todos"] == todos0 - 1
    from ember.registry import load_registry

    ev = load_registry(out, build_if_missing=False).evidence_by_id()
    p = ev["SAFFIRE6:SIBAL"].p_kpa
    assert (
        (p.min, p.max) == (54.1, 55.2)
        and "reviewed by A. Reviewer" in p.source_locator
        and "TODO" not in p.source_locator
    )
    assert ev["SAFFIRE6:PMMA"].p_kpa.min == 54.1  # untouched seed value, not the unreviewed 1.0


# ------------------------------------------------------------------------ real mirrored papers
def test_real_saffire_vi_paper_yields_the_table_values():
    pages = cached_pages("NTRS-20240002981")
    if pages is None:
        pytest.skip("Saffire VI page text not cached (run ember.ingest.extract_llm)")
    props = [X.verify(p, pages) for p in X.rule_proposals("NTRS-20240002981", pages)]
    vi_p = {
        p["column"]: p["min"]
        for p in props
        if p["quantity"] == "p_kpa" and str(p.get("column", "")).startswith("VI")
    }
    vi_o = {
        p["column"]: p["min"]
        for p in props
        if p["quantity"] == "x_o2" and str(p.get("column", "")).startswith("VI")
    }
    assert vi_p == {"VI-2": 54.1, "VI-3": 54.6, "VI-4": 55.2}
    assert vi_o == {"VI-2": 31.0, "VI-3": 30.3, "VI-4": 28.8}
    assert all(p["verified"] for p in props if p.get("column", "").startswith("VI"))
