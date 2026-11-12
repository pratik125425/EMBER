"""T15: verifier rules (spec §11.3, §14 test_verifier.py)."""

from ember.llm.verifier import BANNER_ENVELOPE, citations_of, verify

PAYLOAD = {
    "records": {
        "SAFFIRE6:SIBAL": {
            "x_o2": {"min": 0.288, "max": 0.31},
            "p_kpa": {"min": 54.1, "max": 55.2},
            "D": 0.084,
            "gravity": "microgravity",
        },
        "CFIG:burner85": {"x_o2": {"min": 0.85, "max": 0.85}, "o2_context": "burner_oxidizer_flow"},
        "LUCI:overlay": {"gravity": "simulated_partial"},
    },
    "sources": {"NTRS-20240015307": {"title": "FM2 abstract", "year": 2024}},
    "claims": {"C-FM2": {"claim_type": "author_interpretation", "text": "goldilocks"}},
    "top_D": [0.084],
}
ISS = {"x_o2": 0.21, "p_kpa": 101.3, "gravity_g0": 0.0}


def kept(text, scenario=ISS, payload=PAYLOAD):
    return [s.text for s in verify(text, payload, scenario).kept]


def reason(text, scenario=ISS):
    v = verify(text, PAYLOAD, scenario)
    assert not v.kept, v.kept
    return v.dropped[0][1]


def test_keeps_a_correct_cited_sentence():
    s = "Saffire VI burned SIBAL at X_O₂ 0.288–0.310 and 54.1–55.2 kPa, D = 0.08. [SAFFIRE6:SIBAL]"
    assert kept(s) == [s]


def test_drops_uncited_and_unknown_ids():
    assert reason("Saffire VI burned SIBAL.") == "no citation"
    assert "unknown id" in reason("Saffire VII burned Nomex. [SAFFIRE7:NOMEX]")


def test_drops_wrong_numbers_with_last_digit_tolerance():
    assert "0.45" in reason("Saffire VI ran at X_O₂ 0.45. [SAFFIRE6:SIBAL]")
    assert kept("Saffire VI ran near 0.29 O₂. [SAFFIRE6:SIBAL]")  # 0.288 within ±0.01
    assert kept("Saffire VI ran at 31% O₂. [SAFFIRE6:SIBAL]")  # percent → 0.31
    assert kept("Saffire VI ran at about 8 psi. [SAFFIRE6:SIBAL]")  # 8 psi = 55.2 kPa ±6.9
    assert "12.5" in reason("Saffire VI spread at 12.5 cm/s. [SAFFIRE6:SIBAL]")
    # Scenario numbers may be restated.
    assert kept("Your 21% scenario sits below Saffire VI's 0.31. [SAFFIRE6:SIBAL]")
    # Digits inside names and formulas are not numbers.
    assert kept("CO2 and O2 are named in SAFFIRE6:SIBAL notes. [SAFFIRE6:SIBAL]")


def test_measured_on_the_moon_is_rejected_unless_luci_non_psi():
    assert "partial-gravity" in reason(
        "Saffire VI flames were measured on the Moon. [SAFFIRE6:SIBAL]"
    )
    assert "partial-gravity" in reason("LUCI tested flames in lunar gravity. [LUCI:overlay]")
    ok = "LUCI tested flames in simulated lunar gravity (non-PSI). [LUCI:overlay]"
    assert kept(ok) == [ok]


def test_cfig_85_needs_burner():
    assert "burner" in reason("CFI-G used 85% oxygen. [CFIG:burner85]")
    ok = "CFI-G's 85% oxygen is burner-side oxidizer flow. [CFIG:burner85]"
    assert kept(ok) == [ok]


def test_forbidden_words():
    assert "safe" in reason("SIBAL is safe at 21% O₂. [SAFFIRE6:SIBAL]")
    assert "proves" in reason("Saffire VI proves the cabin is fine. [SAFFIRE6:SIBAL]")
    assert "guarantee" in reason("Nothing here can guarantee it. [SAFFIRE6:SIBAL]")
    assert kept("Saffire VI is the closest test. [SAFFIRE6:SIBAL]")  # 'Saffire' is not 'safe'


def test_unlisted_unit_is_replaced():
    out = kept("Saffire VI ran at 0.31 furlong/fortnight. [SAFFIRE6:SIBAL]")
    assert out == ["Saffire VI ran at 0.31 (unit not stated). [SAFFIRE6:SIBAL]"]


def test_banner_disclaimer_and_badges():
    v = verify("The lunar case is cited. [C-FM2]", PAYLOAD, ISS)
    assert v.kept[0].badge == "author interpretation"
    assert v.disclaimers  # text mentions lunar
    assert not verify("x [SAFFIRE6:SIBAL]", PAYLOAD, ISS).disclaimers
    assert verify("x [SAFFIRE6:SIBAL]", PAYLOAD, {"gravity_g0": 0.38}).disclaimers
    far = dict(PAYLOAD, top_D=[0.2, 1.4])
    assert verify("x [SAFFIRE6:SIBAL]", far, ISS).banners == [BANNER_ENVELOPE]
    assert verify("x [SAFFIRE6:SIBAL]", PAYLOAD, ISS).kept[0].badge == "registry record"


def test_bullets_and_multi_citations():
    assert citations_of("a [A; B] b [C]") == ["A", "B", "C"]
    assert kept("- Both apply. [SAFFIRE6:SIBAL, LUCI:overlay]") == [
        "Both apply. [SAFFIRE6:SIBAL, LUCI:overlay]"
    ]
