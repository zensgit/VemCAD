import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import acad_artifact_route as route  # noqa: E402


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_routes_batch_missing_references(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 2,
        "missing_count": 2,
        "artifacts": [],
    })

    payload = route.route_artifact_index(index)

    assert payload["schema"] == "vemcad.acad_artifact_route/v1"
    assert payload["kind"] == "batch"
    assert payload["status"] == "blocked"
    assert payload["recommended_next_action"]["code"] == "provide-returned-autocad-pngs"


def test_routes_run_case_actions(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "artifact": "compare/summary.md",
        },
        "case_action_counts": {"recapture-autocad-or-provide-window": 1},
        "case_actions": [{
            "id": "G11",
            "code": "recapture-autocad-or-provide-window",
        }],
        "artifacts": [],
    })

    payload = route.route_artifact_index(index)
    text = route._write_text(payload)

    assert payload["kind"] == "request_run"
    assert payload["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert payload["case_action_counts"] == {"recapture-autocad-or-provide-window": 1}
    assert "case_action_counts: recapture-autocad-or-provide-window=1" in text


def test_routes_compare_renderer_candidate_before_recapture(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "viewspace_mismatch",
        "case_count": 2,
        "compared_count": 2,
        "triage_bucket_counts": {
            "recapture-required": 1,
            "renderer-candidate": 1,
        },
        "viewspace_status_counts": {"match": 1, "mismatch": 1},
        "x3_band_counts": {"fail": 1, "fallback": 1},
        "artifacts": [],
    })

    payload = route.route_artifact_index(index)

    assert payload["kind"] == "compare"
    assert payload["recommended_next_action"]["code"] == "inspect-renderer-candidate"
    assert payload["triage_bucket_counts"]["renderer-candidate"] == 1


def test_rejects_unknown_schema(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {"schema": "unknown"})

    assert route.main([str(index)]) == 2
