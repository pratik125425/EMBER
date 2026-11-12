"""T07: evidence map figure builder and page."""

from streamlit.testing.v1 import AppTest

from ember.engine.score import rank, scenario_to_dict
from ember.paths import ROOT
from ember.registry import load_registry
from ember.schemas import Phenomenon, Scenario
from ember.ui.evidence_map import classify, evidence_map, family_for

PAGE = str(ROOT / "app" / "pages" / "2_Evidence_Map.py")


def _reg():
    return load_registry()


def test_classify_is_honest_about_unknowns():
    reg = _reg()
    pl = classify(reg.evidence)
    plotted = {e.evidence_id for e in pl.plotted}
    strip = {e.evidence_id for e in pl.p_unknown}
    nope = {e.evidence_id for e, _ in pl.not_plottable}
    assert {"SAFFIRE6:SIBAL", "SAFFIRE6:PMMA", "CFIG:coolflame_2bar"} <= plotted
    assert {"BASS-II:campaign", "BASS-II:LOC", "BASS-II:LOC_1g"} <= strip  # O2 known, P unknown
    assert {
        "BASS:campaign",
        "CFIG:burner85",
        "SAMER:runs",
        "LUCI:overlay",
        "SAFFIRE1:SIBAL",
    } <= nope
    assert plotted.isdisjoint(strip) and plotted.isdisjoint(nope) and strip.isdisjoint(nope)
    assert len(plotted) + len(strip) + len(nope) == len(reg.evidence)
    reasons = dict((e.evidence_id, r) for e, r in pl.not_plottable)
    assert (
        reasons["SAMER:runs"] == "X_O₂ not applicable"
        and reasons["BASS:campaign"] == "X_O₂ unknown"
    )


def test_family_follows_scenario_phenomenon_when_covered():
    reg = _reg()
    s6 = reg.evidence_by_id()["SAFFIRE6:SIBAL"]
    assert family_for(s6, "spread_opposed") == "Flame spread"
    cf = reg.evidence_by_id()["CFIG:coolflame_2bar"]
    assert (
        family_for(cf, "spread_opposed") == "Cool flames & structure"
    )  # falls back to its own first phenomenon


def test_figure_contains_star_boxes_isolines_and_targets():
    reg = _reg()
    s = Scenario(x_o2=0.34, p_kpa=56.5, gravity_g0=0.166, phenomenon=Phenomenon.spread_opposed)
    results = rank(scenario_to_dict(s), reg.evidence_dicts(), include_partial_g=True)
    fig, pl = evidence_map(reg.evidence, s, results)
    names = [t.name for t in fig.data]
    assert "Your scenario" in names
    star = next(t for t in fig.data if t.name == "Your scenario")
    assert star.x == (0.34,) and star.y == (56.5,)
    assert sum(1 for n in names if n.startswith("ppO₂")) == 4
    # Boxes are batched per family as None-separated closed outlines.
    boxes = [seg for t in fig.data if t.fill == "toself" for seg in _segments(t)]
    # Saffire VI box (0.288–0.310 × 54.1–55.2 kPa).
    assert any(
        min(xs) == 0.288 and max(xs) == 0.31 and min(ys) == 54.1 and max(ys) == 55.2
        for xs, ys in boxes
    )
    # CFI-G cool-flame envelope from the normal-flame table (0.3855–0.3993 at 202.66 kPa) is a box too.
    assert any(
        min(xs) == 0.385474447 and max(xs) == 0.3993 and min(ys) == max(ys) == 202.66
        for xs, ys in boxes
    )
    # FLEX per-test points are markers placed at their sourced (X_O₂, P).
    flex = _marker("PSI-69:T001", fig)
    assert flex is not None and flex[0] == 0.21
    # Target rectangles: 3 boxes + 1 challenge region.
    rects = [sh for sh in fig.layout.shapes if sh.type == "rect"]
    assert len(rects) == 4
    # Hover text carries D for ranked records.
    _, _, hover = _marker("SAFFIRE6:SIBAL", fig)
    assert "D = 0.084" in hover and "non-PSI" in hover
    # Burner-side O₂ records (CFI-G inverse flames) are never placed on the ambient O₂ axis.
    assert _marker("PSI-159:I:21196A1", fig) is None


def _segments(trace):
    xs, ys, out = [], [], []
    for x, y in zip(trace.x, trace.y, strict=True):
        if x is None:
            out.append((xs, ys))
            xs, ys = [], []
        else:
            xs.append(x)
            ys.append(y)
    if xs:
        out.append((xs, ys))
    return out


def _marker(evidence_id, fig):
    for t in fig.data:
        if t.mode == "markers" and t.customdata is not None and evidence_id in t.customdata:
            i = list(t.customdata).index(evidence_id)
            return t.x[i], t.y[i], t.hovertext[i]
    return None


def test_toggles_remove_layers():
    reg = _reg()
    fig, _ = evidence_map(
        reg.evidence, None, None, show_ppo2=False, show_targets=False, show_challenge_region=False
    )
    assert not any(t.name.startswith("ppO₂") for t in fig.data)
    assert len(fig.layout.shapes) == 0
    assert not any(t.name == "Your scenario" for t in fig.data)


def test_family_filter_hides_other_families():
    reg = _reg()
    fig, _ = evidence_map(reg.evidence, None, None, families={"Flame spread"})
    plotted_ids = {t.customdata[0] for t in fig.data if t.customdata}
    assert "CFIG:coolflame_2bar" not in plotted_ids and "SAFFIRE6:SIBAL" in plotted_ids


def test_evidence_map_page_renders_and_toggles():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Evidence map"
    assert len(at.dataframe) == 2  # nearest table + not-on-map table
    nearest = at.dataframe[0].value
    assert list(nearest["#"])[:3] == [1, 2, 3]
    assert "LUCI:overlay" not in set(nearest["Evidence"])
    at.checkbox[0].uncheck().run()  # ppO₂ isolines off
    assert not at.exception
    at.sidebar.selectbox(key="preset").select("ISS").run()
    assert not at.exception
