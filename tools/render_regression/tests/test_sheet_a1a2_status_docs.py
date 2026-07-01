from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _one_line(text: str) -> str:
    return " ".join(text.split())


def test_render_image_workflow_does_not_describe_a1a2_as_future_work():
    text = (REPO_ROOT / ".github" / "workflows" / "render-image.yml").read_text("utf-8")

    assert "follow-up A1a-2" not in text
    assert "A1a-2 verdict corpus exists" in text
    assert "operator/training drawing evidence" in text


def test_a1a_doc_records_current_a1a2_status():
    text = (
        REPO_ROOT / "docs" / "DEV_AND_VERIFICATION_RENDER_SHEET_AUDIT_CI_SMOKE_A1A_20260627.md"
    ).read_text("utf-8")
    one_line = _one_line(text)

    assert "end-to-end CI smoke (blocking)" in text
    assert "synthetic A1a-2 curated verdict corpus" in one_line
    assert "complete as a fast-gate regression check" in one_line
    assert "A1a-2 done, real corpus still gated" in text
    assert "real customer/training drawing corpus" in one_line
