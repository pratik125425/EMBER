"""T15: narrator, guards, adversarial suite, Ask page question flow."""

from streamlit.testing.v1 import AppTest

from ember.engine.score import collapse, rank
from ember.eval.adversarial import run_adversarial
from ember.llm.guards import question_guards, refused
from ember.llm.narrator import narrate
from ember.paths import ROOT
from ember.registry import load_registry
from ember.schemas import Phenomenon

PAGE = str(ROOT / "app" / "pages" / "1_Ask.py")


def _s(ph="spread_opposed", g=0.166):
    return {
        "x_o2": 0.34,
        "p_kpa": 56.5,
        "u_cms": None,
        "gravity_g0": g,
        "phenomenon": ph,
        "fuel_class": None,
        "fuel_name": None,
    }


def test_template_narration_passes_its_own_verifier():
    reg = load_registry()
    ev = reg.evidence_dicts()
    for ph in Phenomenon:
        for g in (0.0, 0.166, 1.0):
            s = _s(ph.value, g)
            for res in (rank(s, ev), collapse(rank(s, ev), "investigation")):
                n = narrate(s, res, reg, k=10, use_llm=False)
                assert n.verified.n_dropped == 0, n.verified.dropped
                assert len(n.verified.kept) == min(10, len(res))


def test_llm_narration_is_verified_and_falls_back():
    reg = load_registry()
    s = _s()
    res = collapse(rank(s, reg.evidence_dicts()), "investigation")
    top = res[0]["evidence_id"]
    fake = (
        f"The closest test is {res[0]['investigation']}. [{top}]\n"
        f"It proves the habitat is fine. [{top}]\n"
        "Lunar flames spread at 3.7 cm/s.\n"
    )
    n = narrate(s, res, reg, use_llm=True, complete=lambda sys, user: fake)
    assert n.mode == "llm"
    assert len(n.verified.kept) == 1 and n.verified.n_dropped == 2
    assert n.verified.disclaimers  # lunar scenario
    # Offline with no cache → template narration, reason recorded.
    n2 = narrate(s, res, reg, use_llm=True)
    assert n2.mode == "template" and "offline" in n2.error


def test_guards():
    kinds = lambda q: [n.kind for n in question_guards(q)]  # noqa: E731
    assert refused(question_guards("Which water-mist test is best?"))
    assert kinds("Is Nomex safe at 34% O2?") == ["no_safety"]
    assert kinds("What was the cabin oxygen in CFI-G?") == ["burner_o2"]
    assert kinds("lunar PMMA spread") == ["partial_g"]
    assert kinds("Saffire VI SIBAL spread at 21%") == []


def test_adversarial_suite_all_handled():
    r = run_adversarial()
    assert r["prompt_pass_rate"] == 1.0, r["prompts"]
    assert r["probe_pass_rate"] == 1.0, r["probes"]
    assert r["n_prompts"] == 5


def test_ask_page_question_to_confirmed_scenario():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.run()
    at.sidebar.selectbox(key="preset").select("ISS").run()
    assert at.sidebar.slider(key="x_o2_pct").value == 21.0
    at.text_input[0].input("Fabric flammability in a lunar habitat at 34% and 8.2 psi").run()
    assert not at.exception
    # Nothing changes until the user confirms.
    assert at.sidebar.slider(key="x_o2_pct").value == 21.0
    btn = next(b for b in at.button if b.label == "Use this scenario")
    btn.click().run()
    assert not at.exception
    assert at.sidebar.slider(key="x_o2_pct").value == 34.0
    assert at.sidebar.slider(key="p_kpa").value == 56.54
    assert at.sidebar.selectbox(key="gravity_label").value == "Moon (0.166 g)"
    assert at.sidebar.selectbox(key="fuel_class").value == "thin_solid"
    assert at.sidebar.checkbox(key="u_specified").value is False
    assert any("kept 5 · dropped 0" in c.value for c in at.caption)


def test_ask_page_refuses_water_mist():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.run()
    at.text_input[0].input("Which water-mist test is best?").run()
    assert not at.exception
    assert any("water-mist" in e.value for e in at.error)
    assert not any(b.label == "Use this scenario" for b in at.button)
