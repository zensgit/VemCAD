from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = REPO_ROOT / "docs" / "VEMCAD_G11_AUTOCAD_REFERENCE_INPUT_RUNBOOK_20260628.md"


def _one_line(text: str) -> str:
    return " ".join(text.split())


def test_reference_input_runbook_keeps_returned_png_size_contract_honest():
    text = RUNBOOK.read_text(encoding="utf-8")
    one_line = _one_line(text)

    assert "every case must keep an explicit `expected_size`" in one_line
    assert "missing `expected_size` blocks manifest validation" in one_line
    assert "request-declared `requested_expected_size`" in text
    assert "opens returned PNGs only to compare their actual dimensions" in one_line
    assert "The helper never lets a returned PNG define its own expected size." in one_line
    assert "returned PNG to record `expected_size`" not in one_line
    assert "returned PNGs to record `expected_size`" not in one_line
