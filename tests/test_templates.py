from ember.llm.templates import format_range, template_sentence
from ember.schemas import Range


def test_format_range():
    assert format_range(Range(status="unknown")) == "unknown"
    assert format_range(Range(status="not_applicable")) == "n/a"
    assert format_range(None) == "n/a"
    known = Range(min=0.136, max=0.222, status="known", source_id="s", source_locator="l")
    assert format_range(known, "{:.3g}") == "0.136–0.222"
    point = Range(min=200, max=200, status="known", source_id="s", source_locator="l")
    assert format_range(point, "{:.4g}", "kPa") == "200 kPa"


def test_template_sentence_cites_and_marks_burner_o2():
    from ember.registry import load_registry

    reg = load_registry()
    e = reg.evidence_by_id()["CFIG:burner85"]
    result = {
        "D": 0.0,
        "expD": 1.0,
        "D_lower_bound": True,
        "flags": ["BURNER_SIDE_O2: x", "INCOMPLETE_CONDITIONS: y"],
    }
    s = template_sentence(e, result)
    assert s.endswith("[CFIG:burner85]")
    assert "burner/oxidizer-side" in s and "ambient" in s
    assert "lower bound" in s and "BURNER_SIDE_O2" in s
