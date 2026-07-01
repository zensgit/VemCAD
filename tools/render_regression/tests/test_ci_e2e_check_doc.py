from pathlib import Path


def test_ci_e2e_check_doc_describes_shipped_gate():
    text = (Path(__file__).resolve().parents[1] / "ci_e2e_check.py").read_text("utf-8")

    assert "D2 PR deferred" not in text
    assert "deferred to D3" not in text
    assert "shipped render\u2192compare end-to-end CI gate" in text
