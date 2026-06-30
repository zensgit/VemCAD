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
        "boundary": {
            "compares_renders": False,
            "autocad_equivalence_claim": False,
        },
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 2,
        "missing_count": 2,
        "artifacts": [
            {"kind": "missing_references_markdown", "path": "input/missing_references.md"},
            {"kind": "missing_references_tsv", "path": "input/missing_references.tsv"},
        ],
    })

    payload = route.route_artifact_index(index)
    text = route._write_text(payload)

    assert payload["schema"] == "vemcad.acad_artifact_route/v1"
    assert payload["boundary"]["read_only_routing"] is True
    assert payload["boundary"]["autocad_equivalence_claim"] is False
    assert payload["artifact_index_boundary"]["compares_renders"] is False
    assert payload["artifact_index_boundary"]["autocad_equivalence_claim"] is False
    assert payload["kind"] == "batch"
    assert payload["status"] == "blocked"
    assert payload["recommended_next_action"]["code"] == "provide-returned-autocad-pngs"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert payload["recommended_next_action"]["artifact"] == "input/missing_references.md"
    assert "action_artifact: input/missing_references.md" in text


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
    assert payload["recommended_next_action"]["domain"] == "input"
    assert payload["case_action_counts"] == {"recapture-autocad-or-provide-window": 1}
    assert "case_action_counts: recapture-autocad-or-provide-window=1" in text


def test_routes_multiple_directories_as_batch(tmp_path):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "boundary": {"compares_renders": False, "autocad_equivalence_claim": False},
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "boundary": {"compares_renders": True, "autocad_equivalence_claim": False},
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
    assert payload["boundary"]["read_only_routing"] is True
    assert payload["boundary"]["compares_renders"] is False
    assert payload["boundary"]["autocad_equivalence_claim"] is False
    assert payload["count"] == 2
    assert payload["kind_counts"] == {"batch": 1, "compare": 1}
    assert payload["status_counts"] == {"pass": 1, "viewspace_mismatch": 1}
    assert payload["recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "recapture-autocad-or-provide-window": 1,
    }
    assert payload["recommended_action_domain_counts"] == {
        "continue": 1,
        "input": 1,
    }
    assert payload["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert payload["recommended_next_action"]["artifact"].endswith("compare/artifact_index.json")
    assert [item["kind"] for item in payload["routes"]] == ["batch", "compare"]
    assert payload["routes"][0]["recommended_next_action"]["code"] == "continue-to-request-run"
    assert payload["routes"][0]["recommended_next_action"]["domain"] == "continue"
    assert payload["routes"][1]["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert payload["routes"][1]["recommended_next_action"]["domain"] == "input"
    assert payload["routes"][0]["artifact_index_boundary"]["compares_renders"] is False
    assert payload["routes"][1]["artifact_index_boundary"]["compares_renders"] is True


def test_cli_multiple_directories_text(tmp_path, capsys):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "boundary": {"compares_renders": False, "autocad_equivalence_claim": False},
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "boundary": {"compares_renders": True, "autocad_equivalence_claim": False},
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

    assert "route_count: 2" in output
    assert "kind_counts: batch=1, compare=1" in output
    assert "status_counts: pass=1, viewspace_mismatch=1" in output
    assert (
        "recommended_action_counts: continue-to-request-run=1, "
        "recapture-autocad-or-provide-window=1"
    ) in output
    assert "recommended_action_domain_counts: continue=1, input=1" in output
    assert "recommended_next_action: recapture-autocad-or-provide-window" in output
    assert "recommended_action_domain: input" in output
    assert "autocad_equivalence_claim: false" in output
    assert "source_artifact_boundary: autocad_equivalence_claim=false,compares_renders=true" in output
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
        "boundary": {"compares_renders": True, "autocad_equivalence_claim": False},
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


def test_cli_writes_json_and_markdown_reports(tmp_path):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    out_json = tmp_path / "reports" / "route_summary.json"
    out_md = tmp_path / "reports" / "route_summary.md"
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
        "boundary": {"compares_renders": True, "autocad_equivalence_claim": False},
        "status": "viewspace_mismatch",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"recapture-required": 1},
        "viewspace_status_counts": {"mismatch": 1},
        "x3_band_counts": {"fallback": 1},
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        str(compare_dir),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
    ]) == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")

    assert payload["schema"] == "vemcad.acad_artifact_route_batch/v1"
    assert payload["boundary"]["changes_renderer"] is False
    assert payload["boundary"]["changes_x3_scoring"] is False
    assert payload["recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "recapture-autocad-or-provide-window": 1,
    }
    assert payload["recommended_action_domain_counts"] == {"continue": 1, "input": 1}
    assert payload["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert "# AutoCAD Artifact Route Report" in markdown
    assert "does not compare renders" in markdown
    assert "- route_count: `2`" in markdown
    assert "recommended_action_counts" in markdown
    assert "recommended_action_domain_counts" in markdown
    assert "- recommended_next_action: `recapture-autocad-or-provide-window`" in markdown
    assert "- recommended_action_domain: `input`" in markdown
    assert "- read_only_routing: `True`" in markdown
    assert "- autocad_equivalence_claim: `False`" in markdown
    assert "- source_compares_renders: `True`" in markdown
    assert "- source_autocad_equivalence_claim: `False`" in markdown
    assert "recapture-autocad-or-provide-window=1" in markdown


def test_cli_require_action_passes_for_matching_top_level_action(tmp_path):
    compare_dir = tmp_path / "compare"
    compare_dir.mkdir()
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

    assert route.main([
        str(compare_dir),
        "--require-action",
        "recapture-autocad-or-provide-window",
    ]) == 0


def test_cli_require_action_fails_closed_on_unexpected_top_level_action(tmp_path, capsys):
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

    assert route.main([
        str(input_dir),
        str(compare_dir),
        "--require-action",
        "review-x3-pass",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required action 'review-x3-pass'" in stderr
    assert "got 'recapture-autocad-or-provide-window'" in stderr
    assert "action artifact:" in stderr


def test_cli_require_action_artifact_passes_for_matching_suffix(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [
            {"kind": "missing_references_markdown", "path": str(input_dir / "missing_references.md")},
        ],
    })

    assert route.main([
        str(input_dir),
        "--require-action",
        "provide-returned-autocad-pngs",
        "--require-action-domain",
        "input",
        "--require-action-artifact",
        "missing_references.md",
    ]) == 0


def test_cli_require_action_artifact_exists_resolves_relative_to_artifact_index(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "missing_references.md").write_text("# Missing\n", encoding="utf-8")
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [
            {"kind": "missing_references_markdown", "path": "missing_references.md"},
        ],
    })

    assert route.main([
        str(input_dir),
        "--require-action",
        "provide-returned-autocad-pngs",
        "--require-action-artifact",
        "missing_references.md",
        "--require-action-artifact-exists",
    ]) == 0


def test_cli_require_action_artifact_exists_fails_closed_when_missing(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [
            {"kind": "missing_references_markdown", "path": "missing_references.md"},
        ],
    })

    assert route.main([
        str(input_dir),
        "--require-action-artifact-exists",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required action artifact to exist" in stderr
    assert "missing_references.md" in stderr
    assert "provide-returned-autocad-pngs" in stderr


def test_cli_require_action_artifact_fails_closed_on_unexpected_artifact(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [
            {"kind": "missing_references_markdown", "path": str(input_dir / "missing_references.md")},
        ],
    })

    assert route.main([
        str(input_dir),
        "--require-action-artifact",
        "reference_intake.md",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required action artifact 'reference_intake.md'" in stderr
    assert "missing_references.md" in stderr
    assert "provide-returned-autocad-pngs" in stderr


def test_cli_require_action_domain_passes_for_expected_domain(tmp_path):
    compare_dir = tmp_path / "compare"
    compare_dir.mkdir()
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

    assert route.main([
        str(compare_dir),
        "--require-action-domain",
        "input",
    ]) == 0


def test_cli_require_action_domain_fails_closed_on_unexpected_domain(tmp_path, capsys):
    compare_dir = tmp_path / "compare"
    compare_dir.mkdir()
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "compare_failed",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"renderer-candidate": 1},
        "viewspace_status_counts": {"match": 1},
        "x3_band_counts": {"fail": 1},
        "artifacts": [],
    })

    assert route.main([
        str(compare_dir),
        "--require-action-domain",
        "input",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required action domain 'input'" in stderr
    assert "got 'renderer-candidate'" in stderr
    assert "for action 'inspect-renderer-candidate'" in stderr


def test_cli_require_source_boundary_passes_when_all_routes_match(tmp_path):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "boundary": {"compares_renders": False, "autocad_equivalence_claim": False},
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "boundary": {"compares_renders": True, "autocad_equivalence_claim": False},
        "status": "viewspace_mismatch",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"recapture-required": 1},
        "viewspace_status_counts": {"mismatch": 1},
        "x3_band_counts": {"fallback": 1},
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        str(compare_dir),
        "--require-source-boundary",
        "autocad_equivalence_claim=false",
    ]) == 0


def test_cli_require_source_boundary_fails_on_missing_boundary(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-source-boundary",
        "autocad_equivalence_claim=false",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "source boundary requirement failed" in stderr
    assert "missing source boundary autocad_equivalence_claim" in stderr


def test_cli_require_source_boundary_fails_on_mismatch(tmp_path, capsys):
    compare_dir = tmp_path / "compare"
    compare_dir.mkdir()
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "boundary": {"compares_renders": True, "autocad_equivalence_claim": False},
        "status": "pass",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"matched-pass": 1},
        "viewspace_status_counts": {"match": 1},
        "x3_band_counts": {"pass": 1},
        "artifacts": [],
    })

    assert route.main([
        str(compare_dir),
        "--require-source-boundary",
        "compares_renders=false",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "source boundary requirement failed" in stderr
    assert "source boundary compares_renders=True != False" in stderr


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
    assert payload["recommended_next_action"]["domain"] == "renderer-candidate"
    assert payload["triage_bucket_counts"]["renderer-candidate"] == 1


def test_batch_route_prioritizes_input_repairs_before_renderer_candidates(tmp_path):
    validation_dir = tmp_path / "validation"
    compare_dir = tmp_path / "compare"
    validation_dir.mkdir()
    compare_dir.mkdir()
    _write(validation_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "request_validation",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [],
    })
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "compare_failed",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"renderer-candidate": 1},
        "viewspace_status_counts": {"match": 1},
        "x3_band_counts": {"fail": 1},
        "artifacts": [],
    })

    payload = route.route_artifact_indexes([validation_dir, compare_dir])

    assert payload["recommended_action_counts"] == {
        "fix-request-package": 1,
        "inspect-renderer-candidate": 1,
    }
    assert payload["recommended_action_domain_counts"] == {
        "input": 1,
        "renderer-candidate": 1,
    }
    assert payload["recommended_next_action"]["code"] == "fix-request-package"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert payload["recommended_next_action"]["artifact"].endswith("validation/artifact_index.json")


def test_rejects_unknown_schema(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {"schema": "unknown"})

    assert route.main([str(index)]) == 2


def test_rejects_directory_without_artifact_index(tmp_path):
    assert route.main([str(tmp_path)]) == 2
