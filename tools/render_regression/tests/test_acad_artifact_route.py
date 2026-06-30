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


def test_routes_directory_containing_artifact_index(tmp_path):
    _write(tmp_path / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "review",
        "case_count": 1,
        "artifacts": [],
    })

    payload = route.route_artifact_index(tmp_path)

    assert payload["artifact_index"].endswith("artifact_index.json")
    assert payload["kind"] == "batch"
    assert payload["recommended_next_action"]["code"] == "inspect-returned-reference-warnings"


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


def test_routes_multiple_directories_as_batch(tmp_path):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "viewspace_mismatch",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"recapture-required": 1},
        "viewspace_status_counts": {"mismatch": 1},
        "x3_band_counts": {"fallback": 1},
        "artifacts": [],
    })

    payload = route.route_artifact_indexes([input_dir, compare_dir])

    assert payload["schema"] == "vemcad.acad_artifact_route_batch/v1"
    assert payload["count"] == 2
    assert [item["kind"] for item in payload["routes"]] == ["batch", "compare"]
    assert payload["routes"][0]["recommended_next_action"]["code"] == "continue-to-request-run"
    assert payload["routes"][1]["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"


def test_cli_multiple_directories_text(tmp_path, capsys):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "viewspace_mismatch",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"recapture-required": 1},
        "viewspace_status_counts": {"mismatch": 1},
        "x3_band_counts": {"fallback": 1},
        "artifacts": [],
    })

    assert route.main([str(input_dir), str(compare_dir), "--text"]) == 0
    output = capsys.readouterr().out

    assert "route: 1" in output
    assert "route: 2" in output
    assert "recommended_next_action: continue-to-request-run" in output
    assert "recommended_next_action: recapture-autocad-or-provide-window" in output


def test_cli_recursive_discovers_nested_artifact_indexes(tmp_path, capsys):
    run_dir = tmp_path / "run"
    input_dir = run_dir / "input"
    compare_dir = run_dir / "compare"
    input_dir.mkdir(parents=True)
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "viewspace_mismatch",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"recapture-required": 1},
        "viewspace_status_counts": {"mismatch": 1},
        "x3_band_counts": {"fallback": 1},
        "artifacts": [],
    })

    assert route.main([str(run_dir), "--recursive", "--text"]) == 0
    output = capsys.readouterr().out

    assert "route: 1" in output
    assert "route: 2" in output
    assert "input/artifact_index.json" in output
    assert "compare/artifact_index.json" in output
    assert "recommended_next_action: continue-to-request-run" in output
    assert "recommended_next_action: recapture-autocad-or-provide-window" in output


def test_recursive_rejects_directory_without_artifact_indexes(tmp_path):
    assert route.main([str(tmp_path), "--recursive"]) == 2


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


def test_rejects_directory_without_artifact_index(tmp_path):
    assert route.main([str(tmp_path)]) == 2
