"""T15: question parser (spec §11.2, §14 test_parser.py) and LLM client cache."""

import json

import pytest

from ember.llm import client
from ember.llm.parser import ground, parse_question, rule_parse, system_prompt

SPEC_Q = "lunar habitat at 34% and 8.2 psi, fabric"


def _check_spec_case(f):
    assert f["x_o2"] == pytest.approx(0.34)
    assert f["p_kpa"] == pytest.approx(56.5, abs=0.05)
    assert f["gravity_g0"] == pytest.approx(0.166)
    assert f["fuel_class"] == "thin_solid"
    assert f["u_cms"] is None  # never guessed


def test_rule_parser_spec_case():
    _check_spec_case(rule_parse(SPEC_Q).fields)


def test_rule_parser_rules():
    f = rule_parse("Fabric flammability in the exploration atmosphere on Mars").fields
    assert (f["x_o2"], f["p_kpa"], f["gravity_g0"]) == (0.34, 56.5, 0.38)
    assert "TP-2010-216134" in f["notes"]
    f = rule_parse("PMMA block spread at 21% O2, 1 atm, 10 mm/s on the ISS").fields
    assert f["fuel_class"] == "thick_solid" and f["gravity_g0"] == 0.0
    assert f["p_kpa"] == pytest.approx(101.33, abs=0.01) and f["u_cms"] == pytest.approx(1.0)
    assert rule_parse("2 bar droplet extinction").fields["p_kpa"] == pytest.approx(200.0)
    r = rule_parse("PMMA flame spread")
    assert r.fields["fuel_class"] is None and r.fields["fuel_name"] == "PMMA"
    assert any("opposed-flow" in n for n in r.notes)


def test_cached_llm_parse_offline(tmp_path, monkeypatch):
    """An LLM answer in the cache is replayed with no network (spec: test_parser is 'cached')."""
    answer = json.dumps(
        {
            "x_o2": 0.34,
            "p_kpa": 56.54,
            "u_cms": None,
            "gravity_g0": 0.166,
            "phenomenon": "spread_opposed",
            "fuel_class": "thin_solid",
            "fuel_name": None,
        }
    )
    key = client.cache_key(client.model_name(), system_prompt(), SPEC_Q, 4096)
    (tmp_path / f"{key}.json").write_text(json.dumps({"response": answer}))
    monkeypatch.setattr(client, "LLM_CACHE_DIR", tmp_path)
    r = parse_question(SPEC_Q)
    assert r.mode == "llm" and not r.dropped
    _check_spec_case(r.fields)


def test_llm_values_not_in_question_are_dropped():
    fields = {"x_o2": 0.30, "p_kpa": 56.54, "u_cms": 15.0, "gravity_g0": 0.38}
    out, dropped = ground(fields, SPEC_Q)
    assert out["x_o2"] is None and out["u_cms"] is None  # invented O2 and airflow removed
    assert out["p_kpa"] == 56.54 and out["gravity_g0"] == 0.38
    assert len(dropped) == 2
    out, dropped = ground({"gravity_g0": 0.0}, "PMMA at 21%")
    assert out["gravity_g0"] is None and dropped


def test_bad_llm_json_falls_back_to_rules():
    r = parse_question(SPEC_Q, complete=lambda s, u: "Sure! Here you go: not json")
    assert r.mode == "rules" and "schema" in r.error
    _check_spec_case(r.fields)


def test_client_offline_and_no_key(tmp_path, monkeypatch):
    with pytest.raises(client.LLMUnavailable, match="offline"):
        client.complete("s", "u", cache_dir=tmp_path)
    monkeypatch.delenv("EMBER_LLM_OFFLINE")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(client.LLMUnavailable, match="ANTHROPIC_API_KEY"):
        client.complete("s", "u", cache_dir=tmp_path)
    r = parse_question(SPEC_Q)  # unavailable LLM → rule parser, reason recorded
    assert r.mode == "rules" and r.error


def test_cache_key_is_stable_and_sensitive():
    k = client.cache_key("m", "s", "u", 10)
    assert k == client.cache_key("m", "s", "u", 10)
    assert k != client.cache_key("m", "s", "u2", 10) != client.cache_key("m2", "s", "u", 10)
