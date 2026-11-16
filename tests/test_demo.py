"""T17: badge legend, guided demo, pre-cache status, offline check."""

import socket

import pytest
from streamlit.testing.v1 import AppTest

from ember import demo
from ember.paths import ROOT
from ember.registry import load_registry
from ember.ui.badges import BADGES, CLAIM_BADGES

PAGE = str(ROOT / "app" / "pages" / "0_Demo.py")


@pytest.fixture(scope="module")
def reg():
    return load_registry()


def test_demo_scenario_comes_from_parser():
    f = demo.lunar_fields()
    assert f["x_o2"] == pytest.approx(0.34)
    assert f["p_kpa"] == pytest.approx(56.5, abs=0.1)
    assert f["gravity_g0"] == pytest.approx(0.166)
    assert f["u_cms"] is None  # airflow never guessed


def test_air_step_moves_only_o2_and_pressure():
    f = demo.lunar_fields()
    a = demo.air_fields(f)
    assert a["x_o2"] == 0.21 and a["p_kpa"] == 101.3
    assert {k: v for k, v in a.items() if k not in ("x_o2", "p_kpa")} == {
        k: v for k, v in f.items() if k not in ("x_o2", "p_kpa")
    }


def test_reshuffle_is_consistent(reg):
    f = demo.lunar_fields()
    b, _, _ = demo.ranked(demo.scenario_dict(f), reg)
    a, _, _ = demo.ranked(demo.scenario_dict(demo.air_fields(f)), reg)
    df = demo.reshuffle(b, a)
    for _, r in df.dropna(subset=["Move"]).iterrows():
        assert r["Move"] == r["Rank before"] - r["Rank after"]


def test_part_share_matches_D(reg):
    res, _, _ = demo.ranked(demo.scenario_dict(demo.lunar_fields()), reg)
    for r in res[:10]:
        o2, d = demo.part_share(r)
        assert d == r["D"]
        if o2 is not None:
            assert o2 <= d + 1e-9


def test_compare_pair_exists(reg):
    by_id = reg.evidence_by_id()
    assert all(i in by_id for i in demo.COMPARE_PAIR)


def test_no_network_blocks_outbound_and_restores():
    real = socket.socket.connect
    with demo.no_network() as attempts:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(OSError):
            s.connect(("93.184.216.34", 80))
        s.close()
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("example.com", 443)
    assert "93.184.216.34" in attempts and "example.com" in attempts
    assert socket.socket.connect is real


def test_mirror_check_passes():
    m = demo.mirror_check()
    assert m["ok"], m
    assert m["mirrored"] > 0


def test_demo_walks_every_step_offline():
    with demo.no_network() as attempts:
        at = AppTest.from_file(PAGE, default_timeout=120).run()
        seen = []
        for i in range(len(demo.STEPS)):
            assert not at.exception, (i, at.exception)
            assert at.session_state["demo_step"] == i
            seen.append(at.subheader[0].value)
            if i < len(demo.STEPS) - 1:
                at.button(key="demo_next").click().run()
        assert at.button(key="demo_next").disabled
    assert attempts == []
    assert [s.split(". ", 1)[1] for s in seen] == [t for t, _ in demo.STEPS]


def test_demo_fast_path_walks_scenario_rank_source_gap():
    at = AppTest.from_file(PAGE, default_timeout=120).run()
    at.session_state["demo_mode"] = "Fast path (about 90 s)"
    at.run()
    at.button(key="demo_restart").click().run()
    stops = []
    while True:
        assert not at.exception
        stops.append(at.session_state["demo_step"])
        if at.button(key="demo_next").disabled:
            break
        at.button(key="demo_next").click().run()
    assert stops == [1, 2, 4, 6]
    at.button(key="demo_back").click().run()
    assert at.session_state["demo_step"] == 4
    at.button(key="demo_restart").click().run()
    assert at.session_state["demo_step"] == 1


def test_demo_confirm_sets_sidebar_scenario():
    at = AppTest.from_file(PAGE, default_timeout=120).run()
    at.button(key="demo_next").click().run()  # step 1: proposal shown, nothing applied yet
    at.button(key="demo_next").click().run()  # confirm → step 2
    assert at.session_state["x_o2_pct"] == pytest.approx(34.0)
    assert at.session_state["gravity_label"].startswith("Moon")
    assert at.session_state["u_specified"] is False
    for _ in range(5):
        at.button(key="demo_next").click().run()  # → step 7 (Earth air)
    assert at.session_state["x_o2_pct"] == pytest.approx(21.0)
    assert at.session_state["p_kpa"] == pytest.approx(101.3)


def test_demo_text_has_no_forbidden_words():
    at = AppTest.from_file(PAGE, default_timeout=120).run()
    texts = []
    for _ in range(len(demo.STEPS)):
        texts += [m.value for m in at.info] + [m.value for m in at.markdown]
        if not at.button(key="demo_next").disabled:
            at.button(key="demo_next").click().run()
    blob = " ".join(texts).lower()
    for w in (" safe ", " safely", " proves", " guarantee"):
        assert w not in blob, w


def test_legend_lists_every_badge_on_every_page():
    for p in [ROOT / "app" / "Home.py", *sorted((ROOT / "app" / "pages").glob("*.py"))]:
        at = AppTest.from_file(str(p), default_timeout=120).run()
        assert not at.exception, p.name
        side = " ".join(c.value for c in at.sidebar.caption)
        for short, _ in BADGES.values():
            assert short in side, (p.name, short)
        for k in CLAIM_BADGES:
            assert k in side, (p.name, k)
