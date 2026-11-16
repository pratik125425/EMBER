"""T06: the Ask page renders without exceptions and reacts to the scenario sidebar."""

from streamlit.testing.v1 import AppTest

from ember.paths import ROOT

PAGE = str(ROOT / "app" / "pages" / "1_Ask.py")


def _run():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def _shows_partial_g(at) -> bool:
    """The disclaimer is a high-contrast callout (markdown), cited in full."""
    return any(
        "Partial-gravity disclaimer" in m.value and "NTRS 20210021318" in m.value
        for m in at.markdown
    )


def test_ask_page_renders_with_defaults():
    at = _run()
    assert at.title[0].value == "Ask"
    assert len(at.dataframe) >= 1
    top = at.dataframe[0].value
    assert list(top["#"]) == list(range(1, min(10, len(top)) + 1))
    # Default scenario is the Exploration Atmosphere on the Moon → partial-g disclaimer shows.
    assert _shows_partial_g(at)
    # Data-free records sit below records with data.
    tiers = list(top["Tier"])
    first_nc = tiers.index("no conditions") if "no conditions" in tiers else len(tiers)
    assert all(t != "no conditions" for t in tiers[:first_nc])
    assert all(t == "no conditions" for t in tiers[first_nc:])
    # T08: stability column and badge.
    assert "P(top-5)" in top.columns and all(0.0 <= p <= 1.0 for p in top["P(top-5)"])
    assert top.iloc[0]["P(top-5)"] >= 0.8 and "Stable" in top.iloc[0]["Badges"]
    assert any(m.label.startswith("Kendall") for m in at.metric)


def test_iss_preset_clears_gravity_warning_and_reranks():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.run()
    at.sidebar.selectbox(key="preset").select("ISS").run()
    assert not at.exception
    assert not _shows_partial_g(at)
    top = at.dataframe[0].value
    # At 21% / 101.3 kPa the BASS-II envelope (13.6–22.2% O2) sits inside on O2 → D from P only (unknown) → D=0.
    row = top[top["Evidence"] == "BASS-II:campaign"].iloc[0]
    assert row["D"] == 0.0


def test_unweighted_phenomenon_shows_info():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.run()
    at.sidebar.selectbox(key="phenomenon").select("ignition").run()
    assert not at.exception
    assert any("unweighted" in i.value for i in at.sidebar.info)
    assert "Unweighted" in " ".join(at.dataframe[0].value["Badges"])
