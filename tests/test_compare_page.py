from streamlit.testing.v1 import AppTest

from ember.paths import ROOT

PAGE = str(ROOT / "app" / "pages" / "3_Compare.py")


def test_compare_page_default_pair_is_caveats():
    at = AppTest.from_file(PAGE, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Compare"
    assert any("Comparable with caveats" in w.value for w in at.warning)
    at.radio[0].set_value("Measurements").run()
    assert not at.exception
    assert any("Comparable with caveats" in w.value for w in at.warning)
