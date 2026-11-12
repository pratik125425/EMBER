"""T09: GapScope coverage, priority and report."""

import numpy as np
import pytest

from ember import config
from ember.engine.gapscope import (
    all_gravities,
    coverage_at,
    coverage_grid,
    gap_report_markdown,
    split_pool,
    target_coverage,
    target_weight,
    top_priority_cells,
)
from ember.registry import load_registry


@pytest.fixture(scope="module")
def ev():
    return load_registry().evidence_dicts()


def test_partial_gravity_is_all_zero_and_hatched(ev):
    for g in (config.G_MOON, config.G_MARS):
        gg = coverage_grid(ev, "spread_opposed", g=g)
        assert gg.hatched and not gg.C.any() and gg.pool == []
    assert not coverage_grid(ev, "spread_opposed", g=0.0).hatched


def test_coverage_is_one_at_an_evidence_point(ev):
    gg = coverage_grid(ev, "spread_opposed", g=0.0)
    # Saffire VI box: X 0.288–0.310, P 54.1–55.2 → any grid cell inside has C = 1.
    c, e, d = coverage_at(0.30, 55.0, gg.pool, "spread_opposed", None)
    assert c == 1.0 and d == 0.0 and e["evidence_id"].startswith("SAFFIRE6")
    assert gg.C.max() == pytest.approx(1.0)
    assert gg.C.shape == (config.GAP_P_KPA[2], config.GAP_X_O2[2]) == (20, 26)


def test_partial_condition_records_do_not_cover(ev):
    pool, partial = split_pool(ev, "spread_opposed", None, 0.0, None)
    ids = {e["evidence_id"] for e in pool}
    assert ids == {"SAFFIRE6:SIBAL", "SAFFIRE6:PMMA"}
    assert "BASS-II:campaign" in {e["evidence_id"] for e in partial}  # O2 known, P unknown
    assert "BASS:campaign" in {e["evidence_id"] for e in partial}


def test_flow_dimension_only_counts_when_specified(ev):
    # Concurrent spread weights flow; Saffire VI has unknown flow → complete only if flow is unspecified.
    pool_u_none, _ = split_pool(ev, "spread_concurrent", None, 0.0, None)
    pool_u_10, partial_u_10 = split_pool(ev, "spread_concurrent", None, 0.0, 10.0)
    assert {e["evidence_id"] for e in pool_u_none} == {"SAFFIRE6:SIBAL", "SAFFIRE6:PMMA"}
    assert pool_u_10 == [] and "SAFFIRE6:SIBAL" in {e["evidence_id"] for e in partial_u_10}


def test_recovers_nasa_documented_gaps(ev):
    rows = {(r["target"], r["g"]): r for r in target_coverage(ev, "spread_opposed", psi_only=True)}
    # (1) Partial gravity: zero coverage at every target.
    for name, _, _ in config.TARGETS:
        for g in (config.G_MOON, config.G_MARS):
            assert rows[(name, g)]["C"] == 0.0 and rows[(name, g)]["nearest"] is None
    # (2) Exploration atmospheres with PSI-only evidence: no complete µg record → coverage 0.
    assert rows[("Exploration Atm 8.2/34", 0.0)]["C"] == 0.0
    assert rows[("10.2 psia option", 0.0)]["C"] == 0.0
    # (3) Including the non-PSI Saffire VI paper, the 8.2/34 point is covered only by a flagged source.
    r = {(x["target"], x["g"]): x for x in target_coverage(ev, "spread_opposed", psi_only=False)}[
        ("Exploration Atm 8.2/34", 0.0)
    ]
    assert r["C"] == pytest.approx(np.exp(-0.0843), abs=0.002)
    assert r["nearest"].startswith("SAFFIRE6") and {"NON_PSI_SOURCE", "TENSION"} <= set(r["flags"])


def test_priority_uses_target_boxes(ev):
    assert target_weight(0.34, 56.5) == (1.0, "Exploration Atm 8.2/34")
    assert target_weight(0.34, 56.5 * 1.049)[0] == 1.0
    assert target_weight(0.34, 56.5 * 1.06)[0] == config.PRIORITY_OUTSIDE_TARGET
    assert target_weight(0.36, 56.5)[0] == config.PRIORITY_OUTSIDE_TARGET
    gg = coverage_grid(ev, "spread_opposed", g=0.0, psi_only=True)
    assert np.allclose(gg.priority, (1 - gg.C) * gg.T)
    assert gg.priority.max() == 1.0  # an uncovered target cell
    cells = top_priority_cells(all_gravities(ev, "spread_opposed", psi_only=True), n=5)
    assert all(c["priority"] == 1.0 and c["target"] is not None for c in cells)
    assert all(
        c["g"] in config.BRACKET_GRAVITIES for c in cells
    )  # hatched panels never produce cells


def test_grid_resolution_sensitivity(ev):
    coarse = coverage_grid(ev, "spread_opposed", g=0.0)
    fine = coverage_grid(ev, "spread_opposed", g=0.0, n_x=52, n_p=40)
    for _name, tx, tp in config.TARGETS:
        ci = coarse.C[np.abs(coarse.P - tp).argmin(), np.abs(coarse.X - tx).argmin()]
        fi = fine.C[np.abs(fine.P - tp).argmin(), np.abs(fine.X - tx).argmin()]
        exact = coverage_at(tx, tp, coarse.pool, "spread_opposed", None)[0]
        assert abs(ci - exact) < 0.05 and abs(fi - exact) < 0.03


def test_gap_report_wording(ev):
    md = gap_report_markdown(ev, "spread_opposed", fuel_class=None, u=None, psi_only=True)
    assert "safe" not in md.lower().replace("unsafe", "")
    assert "absence of evidence" in md
    assert "No PSI investigation measured combustion at partial gravity" in md
    assert "LUCI" in md and "FM2" in md and "Water-mist" in md
    assert "| Exploration Atm 8.2/34" in md and "heuristic" in md
    assert "BASS-II:campaign" in md  # listed as partial-condition evidence, not counted
