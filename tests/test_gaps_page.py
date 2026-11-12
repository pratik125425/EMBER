"""T09: Gaps page and panel figure."""

from streamlit.testing.v1 import AppTest

from ember import config
from ember.engine.gapscope import all_gravities
from ember.paths import ROOT
from ember.registry import load_registry
from ember.schemas import Phenomenon, Scenario
from ember.ui.gaps_chart import gap_panels

PAGE = str(ROOT / "app" / "pages" / "4_Gaps.py")


def test_gap_panels_hatch_partial_g_and_overlay_luci_fm2():
    grids = all_gravities(load_registry().evidence_dicts(), "spread_opposed")
    s = Scenario(
        x_o2=0.34, p_kpa=56.5, gravity_g0=config.G_MOON, phenomenon=Phenomenon.spread_opposed
    )
    fig = gap_panels(grids, "coverage", s)
    heatmaps = [t for t in fig.data if t.type == "heatmap"]
    hatched = [t for t in fig.data if t.type == "scatter" and t.fill == "toself"]
    assert len(heatmaps) == 2 and len(hatched) == 2  # µg + 1-g heatmaps; Moon + Mars hatched
    texts = " ".join(" ".join(t.text) for t in fig.data if t.type == "scatter" and t.text)
    assert "LUCI" in texts and "FM2" in texts and "not in PSI" in texts
    assert any(t.name == "Your scenario" for t in fig.data)  # star on the Moon panel
    assert all(
        "No PSI evidence" in a.text for a in fig.layout.annotations if "No PSI" in (a.text or "")
    )


def test_gaps_page_renders_and_offers_report():
    at = AppTest.from_file(PAGE, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Gaps"
    assert len(at.dataframe) >= 3
    targets = at.dataframe[0].value
    moon = targets[(targets["Gravity"].str.startswith("lunar"))]
    assert (moon["C"] == 0).all() and (moon["Nearest evidence"] == "none").all()
    assert any("Download gap report" in b.label for b in at.get("download_button"))
    at.checkbox[1].check().run()  # PSI records only
    assert not at.exception
    targets = at.dataframe[0].value
    exp_ug = targets[
        (targets["Target"] == "Exploration Atm 8.2/34")
        & (targets["Gravity"].str.startswith("microgravity"))
    ]
    assert float(exp_ug["C"].iloc[0]) == 0.0
