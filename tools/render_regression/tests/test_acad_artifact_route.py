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
        "reference_request_validation_issue_code_counts": {
            "source_dxf_sha256_mismatch": 1,
        },
        "source_request_boundary": {
            "requires_returned_autocad_png": True,
            "requires_viewspace_match": True,
            "autocad_equivalence_claim": False,
        },
        "reference_intake_issue_code_counts": {
            "returned_reference_blank": 2,
        },
        "artifacts": [
            {"kind": "missing_references_markdown", "path": "input/missing_references.md"},
            {"kind": "missing_references_tsv", "path": "input/missing_references.tsv"},
        ],
    })

    payload = route.route_artifact_index(index)
    text = route._write_text(payload)
    markdown = route.route_markdown(payload)

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
    assert payload["reference_request_validation_issue_code_counts"] == {
        "source_dxf_sha256_mismatch": 1,
    }
    assert payload["source_request_boundary"] == {
        "requires_returned_autocad_png": True,
        "requires_viewspace_match": True,
        "autocad_equivalence_claim": False,
    }
    assert payload["reference_intake_issue_code_counts"] == {
        "returned_reference_blank": 2,
    }
    assert "action_artifact: input/missing_references.md" in text
    assert "reference_request_validation_issue_code_counts: source_dxf_sha256_mismatch=1" in text
    assert "source_request_boundary: autocad_equivalence_claim=False" in text
    assert "requires_returned_autocad_png=True" in text
    assert "reference_intake_issue_code_counts: returned_reference_blank=2" in text
    assert "- reference_request_validation_issue_code_counts: `source_dxf_sha256_mismatch=1`" in markdown
    assert "- source_request_boundary: `autocad_equivalence_claim=False" in markdown
    assert "requires_returned_autocad_png=True" in markdown
    assert "- reference_intake_issue_code_counts: `returned_reference_blank=2`" in markdown


def test_route_markdown_escapes_code_span_values(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [
            {"kind": "missing_references_markdown", "path": "missing|refs`2026`.md"},
        ],
    })

    payload = route.route_artifact_index(index)
    markdown = route.route_markdown(payload)

    assert "- action_artifact: ``missing\\|refs`2026`.md``" in markdown


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


def test_routes_batch_reference_intake_blocked(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "blocked",
        "case_count": 1,
        "error_count": 1,
        "warning_count": 0,
        "reference_intake_issue_code_counts": {
            "returned_png_size_mismatch": 1,
        },
        "artifacts": [
            {"kind": "reference_intake_markdown", "path": "input/reference_intake.md"},
        ],
    })

    payload = route.route_artifact_index(index)
    text = route._write_text(payload)
    markdown = route.route_markdown(payload)

    assert payload["kind"] == "batch"
    assert payload["status"] == "blocked"
    assert payload["stage"] == "reference_intake"
    assert payload["case_count"] == 1
    assert payload["recommended_next_action"]["code"] == "fix-returned-reference-input"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert payload["recommended_next_action"]["artifact"] == "input/reference_intake.md"
    assert payload["reference_intake_issue_code_counts"] == {
        "returned_png_size_mismatch": 1,
    }
    assert payload["error_count"] == 1
    assert payload["warning_count"] == 0
    assert "stage: reference_intake" in text
    assert "case_count: 1" in text
    assert "errors: 1" in text
    assert "warnings: 0" in text
    assert "- stage: `reference_intake`" in markdown
    assert "- case_count: `1`" in markdown
    assert "- errors: `1`" in markdown
    assert "- warnings: `0`" in markdown


def test_routes_prioritize_blocked_returned_reference_input_over_renderer_candidate(tmp_path):
    compare_dir = tmp_path / "compare"
    input_dir = tmp_path / "input"
    compare_dir.mkdir()
    input_dir.mkdir()
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "compare_failed",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {"renderer-candidate": 1},
        "viewspace_status_counts": {"match": 1},
        "x3_band_counts": {"fail": 1},
        "artifacts": [
            {"kind": "summary_markdown", "path": "compare/summary.md"},
        ],
    })
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "blocked",
        "case_count": 1,
        "error_count": 1,
        "warning_count": 0,
        "reference_intake_issue_code_counts": {
            "returned_png_size_mismatch": 1,
        },
        "artifacts": [
            {"kind": "reference_intake_markdown", "path": "input/reference_intake.md"},
        ],
    })

    payload = route.route_artifact_indexes([
        compare_dir / "artifact_index.json",
        input_dir / "artifact_index.json",
    ])
    input_route_text = route._write_text(payload["routes"][1])
    markdown = route.route_markdown(payload)

    assert payload["recommended_next_action"]["code"] == "fix-returned-reference-input"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert payload["recommended_next_action"]["artifact"] == "input/reference_intake.md"
    assert payload["recommended_next_action"]["source_route_index"] == "2"
    assert payload["recommended_action_counts"] == {
        "fix-returned-reference-input": 1,
        "inspect-renderer-candidate": 1,
    }
    assert payload["recommended_action_domain_counts"] == {
        "input": 1,
        "renderer-candidate": 1,
    }
    assert payload["routes"][1]["error_count"] == 1
    assert payload["routes"][1]["warning_count"] == 0
    assert "stage: reference_intake" in input_route_text
    assert "case_count: 1" in input_route_text
    assert "errors: 1" in input_route_text
    assert "warnings: 0" in input_route_text
    assert "- stage: `reference_intake`" in markdown
    assert "- case_count: `1`" in markdown
    assert "- errors: `1`" in markdown
    assert "- warnings: `0`" in markdown


def test_routes_run_case_actions(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "final_exit_code": 2,
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "artifact": "compare/summary.md",
        },
        "case_action_counts": {"recapture-autocad-or-provide-window": 1},
        "case_action_domain_counts": {"input": 1},
        "route_count": 3,
        "route_kind_counts": {"batch": 1, "compare": 1, "request_run": 1},
        "route_status_counts": {"pass": 1, "viewspace_mismatch": 2},
        "route_final_exit_code_counts": {"0": 2, "2": 1},
        "route_recommended_action_counts": {
            "continue-to-request-run": 1,
            "recapture-autocad-or-provide-window": 2,
        },
        "route_recommended_action_domain_counts": {
            "continue": 1,
            "input": 2,
        },
        "route_compare_case_count": 2,
        "route_compared_count": 2,
        "route_triage_bucket_counts": {
            "matched-pass": 1,
            "recapture-required": 1,
        },
        "route_viewspace_status_counts": {
            "match": 1,
            "mismatch": 1,
        },
        "route_x3_band_counts": {
            "fallback": 1,
            "pass": 1,
        },
        "route_compare_issue_code_counts": {
            "diagnostic_capture_method": 1,
        },
        "reference_request_validation_status": "blocked",
        "reference_request_validation_error_count": 1,
        "reference_request_validation_warning_count": 0,
        "reference_request_validation_issue_code_counts": {
            "source_dxf_sha256_mismatch": 1,
        },
        "source_request_boundary": {
            "requires_returned_autocad_png": True,
            "autocad_equivalence_claim": False,
        },
        "reference_intake_status": "review",
        "reference_intake_error_count": 0,
        "reference_intake_warning_count": 2,
        "reference_intake_issue_code_counts": {
            "candidate_render_blank": 1,
            "returned_reference_blank": 1,
        },
        "case_actions": [{
            "id": "G11",
            "code": "recapture-autocad-or-provide-window",
            "domain": "input",
            "source": "missing_references",
            "issue_codes": "warning:corner_background_not_white, warning:long_edge_below_requested",
            "evidence": "current_acad=abc123def456:42; source=feedface9999:99",
            "artifact": "input/missing_references.md",
        }],
        "artifacts": [],
    })

    payload = route.route_artifact_index(index)
    text = route._write_text(payload)
    markdown = route.route_markdown(payload)

    assert payload["kind"] == "request_run"
    assert payload["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert payload["final_exit_code"] == 2
    assert payload["case_action_counts"] == {"recapture-autocad-or-provide-window": 1}
    assert payload["case_action_domain_counts"] == {"input": 1}
    assert payload["case_action_issue_code_counts"] == {
        "warning:corner_background_not_white": 1,
        "warning:long_edge_below_requested": 1,
    }
    assert payload["route_count"] == 3
    assert payload["route_kind_counts"] == {"batch": 1, "compare": 1, "request_run": 1}
    assert payload["route_status_counts"] == {"pass": 1, "viewspace_mismatch": 2}
    assert payload["route_final_exit_code_counts"] == {"0": 2, "2": 1}
    assert payload["route_recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "recapture-autocad-or-provide-window": 2,
    }
    assert payload["route_recommended_action_domain_counts"] == {
        "continue": 1,
        "input": 2,
    }
    assert payload["route_compare_case_count"] == 2
    assert payload["route_compared_count"] == 2
    assert payload["route_triage_bucket_counts"] == {
        "matched-pass": 1,
        "recapture-required": 1,
    }
    assert payload["route_viewspace_status_counts"] == {
        "match": 1,
        "mismatch": 1,
    }
    assert payload["route_x3_band_counts"] == {
        "fallback": 1,
        "pass": 1,
    }
    assert payload["route_compare_issue_code_counts"] == {
        "diagnostic_capture_method": 1,
    }
    assert payload["reference_request_validation_status"] == "blocked"
    assert payload["reference_request_validation_error_count"] == 1
    assert payload["reference_request_validation_warning_count"] == 0
    assert payload["reference_request_validation_issue_code_counts"] == {
        "source_dxf_sha256_mismatch": 1,
    }
    assert payload["source_request_boundary"] == {
        "requires_returned_autocad_png": True,
        "autocad_equivalence_claim": False,
    }
    assert payload["reference_intake_status"] == "review"
    assert payload["reference_intake_error_count"] == 0
    assert payload["reference_intake_warning_count"] == 2
    assert payload["reference_intake_issue_code_counts"] == {
        "candidate_render_blank": 1,
        "returned_reference_blank": 1,
    }
    assert "case_action_counts: recapture-autocad-or-provide-window=1" in text
    assert "case_action_domain_counts: input=1" in text
    assert (
        "case_action_issue_code_counts: warning:corner_background_not_white=1, "
        "warning:long_edge_below_requested=1"
    ) in text
    assert (
        "case_action: G11; recapture-autocad-or-provide-window; domain=input; "
        "source=missing_references"
    ) in text
    assert "evidence=current_acad=abc123def456:42; source=feedface9999:99" in text
    assert "artifact=input/missing_references.md" in text
    assert "final_exit_code: 2" in text
    assert "route_count: 3" in text
    assert "route_kind_counts: batch=1, compare=1, request_run=1" in text
    assert "route_final_exit_code_counts: 0=2, 2=1" in text
    assert "route_compare_case_count: 2" in text
    assert "route_triage_bucket_counts: matched-pass=1, recapture-required=1" in text
    assert "route_viewspace_status_counts: match=1, mismatch=1" in text
    assert "route_x3_band_counts: fallback=1, pass=1" in text
    assert "route_compare_issue_code_counts: diagnostic_capture_method=1" in text
    assert "reference_request_validation_status: blocked" in text
    assert "reference_request_validation_errors: 1" in text
    assert "reference_request_validation_warnings: 0" in text
    assert "reference_request_validation_issue_code_counts: source_dxf_sha256_mismatch=1" in text
    assert "source_request_boundary: autocad_equivalence_claim=False" in text
    assert "requires_returned_autocad_png=True" in text
    assert "reference_intake_status: review" in text
    assert "reference_intake_errors: 0" in text
    assert "reference_intake_warnings: 2" in text
    assert (
        "reference_intake_issue_code_counts: candidate_render_blank=1, "
        "returned_reference_blank=1"
    ) in text
    assert "- reference_request_validation_status: `blocked`" in markdown
    assert "- final_exit_code: `2`" in markdown
    assert (
        "- case_action_issue_code_counts: `warning:corner_background_not_white=1, "
        "warning:long_edge_below_requested=1`"
    ) in markdown
    assert "### Case Actions" in markdown
    assert (
        "| `G11` | `recapture-autocad-or-provide-window` | `input` | "
        "`missing_references` |"
    ) in markdown
    assert "`current_acad=abc123def456:42; source=feedface9999:99`" in markdown
    assert "`input/missing_references.md`" in markdown
    assert "- route_count: `3`" in markdown
    assert "- route_final_exit_code_counts: `0=2, 2=1`" in markdown
    assert "- route_triage_bucket_counts: `matched-pass=1, recapture-required=1`" in markdown
    assert "- route_compare_issue_code_counts: `diagnostic_capture_method=1`" in markdown
    assert "- reference_request_validation_errors: `1`" in markdown
    assert "- reference_request_validation_warnings: `0`" in markdown
    assert "- reference_request_validation_issue_code_counts: `source_dxf_sha256_mismatch=1`" in markdown
    assert "- source_request_boundary: `autocad_equivalence_claim=False" in markdown
    assert "requires_returned_autocad_png=True" in markdown
    assert "- reference_intake_status: `review`" in markdown
    assert "- reference_intake_errors: `0`" in markdown
    assert "- reference_intake_warnings: `2`" in markdown
    assert (
        "- reference_intake_issue_code_counts: `candidate_render_blank=1, "
        "returned_reference_blank=1`"
    ) in markdown
    assert route.main([
        str(index),
        "--require-issue-code-count",
        "diagnostic_capture_method=1",
    ]) == 0
    batch_payload = route.route_artifact_indexes([index])
    assert batch_payload["compare_issue_code_counts"] == {
        "diagnostic_capture_method": 1,
    }
    assert batch_payload["case_action_issue_code_counts"] == {
        "warning:corner_background_not_white": 1,
        "warning:long_edge_below_requested": 1,
    }


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
        "final_exit_code": 0,
        "case_count": 1,
        "reference_request_validation_issue_code_counts": {
            "source_dxf_sha256_mismatch": 1,
        },
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
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
    assert payload["final_exit_code_counts"] == {"0": 1}
    assert payload["recommended_action_counts"] == {
        "continue-to-request-run": 1,
        "recapture-autocad-or-provide-window": 1,
    }
    assert payload["recommended_action_domain_counts"] == {
        "continue": 1,
        "input": 1,
    }
    assert payload["reference_request_validation_issue_code_counts"] == {
        "source_dxf_sha256_mismatch": 1,
    }
    assert payload["reference_intake_issue_code_counts"] == {
        "corner_background_not_white": 2,
    }
    assert payload["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert payload["recommended_next_action"]["artifact"].endswith("compare/artifact_index.json")
    assert [item["kind"] for item in payload["routes"]] == ["batch", "compare"]
    assert payload["routes"][0]["final_exit_code"] == 0
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
        "final_exit_code": 0,
        "case_count": 1,
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
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
    assert "final_exit_code_counts: 0=1" in output
    assert (
        "recommended_action_counts: continue-to-request-run=1, "
        "recapture-autocad-or-provide-window=1"
    ) in output
    assert "recommended_action_domain_counts: continue=1, input=1" in output
    assert "reference_intake_issue_code_counts: corner_background_not_white=2" in output
    assert "recommended_next_action: recapture-autocad-or-provide-window" in output
    assert "recommended_action_domain: input" in output
    assert "autocad_equivalence_claim: false" in output
    assert "source_artifact_boundary: autocad_equivalence_claim=false,compares_renders=true" in output
    assert "final_exit_code: 0" in output
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
        "final_exit_code": 0,
        "case_count": 1,
        "reference_request_validation_issue_code_counts": {
            "source_dxf_sha256_mismatch": 1,
        },
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
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
        "final_exit_code": 0,
        "case_count": 1,
        "reference_request_validation_issue_code_counts": {
            "source_dxf_sha256_mismatch": 1,
        },
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
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
    assert payload["final_exit_code_counts"] == {"0": 1}
    assert payload["recommended_action_domain_counts"] == {"continue": 1, "input": 1}
    assert payload["reference_request_validation_issue_code_counts"] == {
        "source_dxf_sha256_mismatch": 1,
    }
    assert payload["reference_intake_issue_code_counts"] == {
        "corner_background_not_white": 2,
    }
    assert payload["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert payload["recommended_next_action"]["domain"] == "input"
    assert "# AutoCAD Artifact Route Report" in markdown
    assert "does not compare renders" in markdown
    assert "- route_count: `2`" in markdown
    assert "- final_exit_code_counts: `0=1`" in markdown
    assert "recommended_action_counts" in markdown
    assert "recommended_action_domain_counts" in markdown
    assert "- reference_request_validation_issue_code_counts: `source_dxf_sha256_mismatch=1`" in markdown
    assert "- reference_intake_issue_code_counts: `corner_background_not_white=2`" in markdown
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


def test_route_payload_reports_resolved_action_artifact(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "missing_references.md").write_text("# Missing\n", encoding="utf-8")
    index = _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [
            {"kind": "missing_references_markdown", "path": "missing_references.md"},
        ],
    })

    payload = route.route_artifact_index(index)
    text = route._write_text(payload)
    markdown = route.route_markdown(payload)

    assert payload["recommended_next_action"]["artifact"] == "missing_references.md"
    assert payload["action_artifact_resolved"] == str(input_dir / "missing_references.md")
    assert payload["action_artifact_exists"] is True
    assert f"action_artifact_resolved: {input_dir / 'missing_references.md'}" in text
    assert "action_artifact_exists: true" in text
    assert f"- action_artifact_resolved: `{input_dir / 'missing_references.md'}`" in markdown
    assert "- action_artifact_exists: `True`" in markdown


def test_batch_route_payload_reports_selected_action_artifact_resolution(tmp_path):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
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
    text = route._write_batch_text(payload)
    markdown = route.route_markdown(payload)

    assert payload["recommended_next_action"]["code"] == "provide-returned-autocad-pngs"
    assert payload["recommended_next_action"]["source_artifact_index"].endswith("input/artifact_index.json")
    assert payload["action_artifact_resolved"] == str(input_dir / "missing_references.md")
    assert payload["action_artifact_exists"] is True
    assert f"action_artifact_resolved: {input_dir / 'missing_references.md'}" in text
    assert "action_artifact_exists: true" in text
    assert f"- action_artifact_resolved: `{input_dir / 'missing_references.md'}`" in markdown
    assert "- action_artifact_exists: `True`" in markdown


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


def test_cli_forbid_action_domain_passes_when_domain_absent(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-action-domain",
        "input",
        "--forbid-action-domain",
        "renderer-candidate",
    ]) == 0


def test_cli_forbid_action_domain_fails_on_mixed_hidden_renderer_candidate(tmp_path, capsys):
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

    assert route.main([
        str(validation_dir),
        str(compare_dir),
        "--require-action-domain",
        "input",
        "--forbid-action-domain",
        "renderer-candidate",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden action domain present: renderer-candidate=1" in stderr
    assert "action domain counts: input=1, renderer-candidate=1" in stderr


def test_cli_forbid_action_domain_fails_on_request_run_case_domain_counts(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "domain": "input",
        },
        "case_action_counts": {
            "recapture-autocad-or-provide-window": 1,
            "inspect-renderer-candidate": 1,
        },
        "case_action_domain_counts": {
            "input": 1,
            "renderer-candidate": 1,
        },
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(run_dir),
        "--require-action-domain",
        "input",
        "--forbid-action-domain",
        "renderer-candidate",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden action domain present: renderer-candidate=1" in stderr
    assert "action domain counts: input=1, renderer-candidate=1" in stderr


def test_cli_forbid_action_passes_when_action_absent(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-action-domain",
        "input",
        "--forbid-action",
        "inspect-renderer-candidate",
    ]) == 0


def test_cli_forbid_action_fails_on_request_run_case_action_counts(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "domain": "input",
        },
        "case_action_counts": {
            "recapture-autocad-or-provide-window": 1,
            "review-x3-pass": 1,
        },
        "case_action_domain_counts": {
            "input": 1,
            "pass-review": 1,
        },
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(run_dir),
        "--forbid-action",
        "recapture-autocad-or-provide-window",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden action present: recapture-autocad-or-provide-window=1" in stderr
    assert "action counts: recapture-autocad-or-provide-window=1, review-x3-pass=1" in stderr


def test_cli_require_action_count_passes_for_batch(tmp_path):
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
        "--require-action-count",
        "continue-to-request-run=1",
        "--require-action-count",
        "recapture-autocad-or-provide-window=1",
    ]) == 0


def test_cli_require_action_count_fails_closed_for_batch_mismatch(tmp_path, capsys):
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
        "--require-action-count",
        "recapture-autocad-or-provide-window=2",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required action count mismatch: recapture-autocad-or-provide-window=2 (got 1)" in stderr
    assert (
        "action counts: continue-to-request-run=1, "
        "recapture-autocad-or-provide-window=1"
    ) in stderr


def test_cli_require_action_count_passes_for_request_run_cases(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "domain": "input",
        },
        "case_action_counts": {
            "recapture-autocad-or-provide-window": 2,
        },
        "case_action_domain_counts": {
            "input": 2,
        },
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(run_dir),
        "--require-action-count",
        "recapture-autocad-or-provide-window=2",
    ]) == 0


def test_cli_require_action_count_passes_for_single_route(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-action-count",
        "provide-returned-autocad-pngs=1",
    ]) == 0


def test_cli_require_action_count_rejects_bad_expectation(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-action-count",
        "provide-returned-autocad-pngs=soon",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "count expectation value must be an integer" in stderr


def test_cli_require_action_count_ignores_non_integer_artifact_counts(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "domain": "input",
        },
        "case_action_counts": {
            "provide-returned-autocad-pngs": True,
            "fix-request-package": 1.5,
            "continue-to-request-run": "1",
            "inspect-artifact-index": -1,
        },
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-action-count",
        "provide-returned-autocad-pngs=1",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required action count mismatch: provide-returned-autocad-pngs=1 (got 0)" in stderr
    assert "action counts: continue-to-request-run=1" in stderr


def test_cli_require_action_domain_count_passes_for_request_run_cases(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "domain": "input",
        },
        "case_action_counts": {
            "recapture-autocad-or-provide-window": 2,
            "review-x3-pass": 1,
        },
        "case_action_domain_counts": {
            "input": 2,
            "pass-review": 1,
        },
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(run_dir),
        "--require-action-domain-count",
        "input=2",
        "--require-action-domain-count",
        "pass-review=1",
    ]) == 0


def test_cli_require_action_domain_count_fails_closed_for_mismatch(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "domain": "input",
        },
        "case_action_counts": {
            "recapture-autocad-or-provide-window": 2,
            "review-x3-pass": 1,
        },
        "case_action_domain_counts": {
            "input": 2,
            "pass-review": 1,
        },
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(run_dir),
        "--require-action-domain-count",
        "input=3",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required action domain count mismatch: input=3 (got 2)" in stderr
    assert "action domain counts: input=2, pass-review=1" in stderr


def test_cli_require_compare_counts_passes_for_batch(tmp_path):
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
        "status": "compare_failed",
        "case_count": 2,
        "compared_count": 2,
        "triage_bucket_counts": {"renderer-candidate": 1, "recapture-required": 1},
        "viewspace_status_counts": {"match": 1, "mismatch": 1},
        "x3_band_counts": {"fail": 1, "fallback": 1},
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        str(compare_dir),
        "--require-triage-bucket",
        "renderer-candidate=1",
        "--require-triage-bucket",
        "recapture-required=1",
        "--require-viewspace-status",
        "match=1",
        "--require-viewspace-status",
        "mismatch=1",
        "--require-x3-band",
        "fail=1",
        "--require-x3-band",
        "fallback=1",
        "--require-compare-case-count",
        "2",
        "--require-compared-count",
        "2",
    ]) == 0


def test_cli_require_compare_counts_ignore_non_integer_artifact_counts(tmp_path, capsys):
    compare_dir = tmp_path / "compare"
    compare_dir.mkdir()
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "pass",
        "case_count": 1.5,
        "compared_count": True,
        "artifacts": [],
    })

    assert route.main([
        str(compare_dir),
        "--require-compare-case-count", "1",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required compare case count 1 but got None" in stderr


def test_cli_require_compare_counts_passes_for_request_run_route_fields(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "domain": "input",
        },
        "case_action_counts": {"recapture-autocad-or-provide-window": 1},
        "case_action_domain_counts": {"input": 1},
        "route_compare_case_count": 2,
        "route_compared_count": 2,
        "route_triage_bucket_counts": {"matched-pass": 1, "recapture-required": 1},
        "route_viewspace_status_counts": {"match": 1, "mismatch": 1},
        "route_x3_band_counts": {"fallback": 1, "pass": 1},
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(run_dir),
        "--require-triage-bucket",
        "recapture-required=1",
        "--require-viewspace-status",
        "mismatch=1",
        "--require-x3-band",
        "fallback=1",
        "--require-compare-case-count",
        "2",
        "--require-compared-count",
        "2",
    ]) == 0


def test_cli_require_compare_case_count_fails_closed_for_mismatch(tmp_path, capsys):
    compare_dir = tmp_path / "compare"
    compare_dir.mkdir()
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
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
        "--require-compare-case-count",
        "2",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required compare case count 2 but got 1" in stderr


def test_cli_require_compared_count_fails_closed_for_request_run_mismatch(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "pass",
        "recommended_next_action": {
            "code": "review-x3-pass",
            "message": "pass",
            "domain": "pass-review",
        },
        "case_action_counts": {"review-x3-pass": 1},
        "case_action_domain_counts": {"pass-review": 1},
        "route_compare_case_count": 1,
        "route_compared_count": 1,
        "route_triage_bucket_counts": {"matched-pass": 1},
        "route_viewspace_status_counts": {"match": 1},
        "route_x3_band_counts": {"pass": 1},
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(run_dir),
        "--require-compared-count",
        "2",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required compared count 2 but got 1" in stderr


def test_cli_forbid_viewspace_status_fails_on_hidden_mismatch(tmp_path, capsys):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "request_validation",
        "status": "blocked",
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
        "--forbid-viewspace-status",
        "mismatch",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden viewspace status present: mismatch=1" in stderr
    assert "viewspace status counts: mismatch=1" in stderr


def test_cli_require_status_passes_when_present(tmp_path):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "review",
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
        "--require-status",
        "review",
        "--require-status",
        "viewspace_mismatch",
    ]) == 0


def test_cli_require_status_fails_closed_when_missing(tmp_path, capsys):
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
        "--require-status",
        "blocked",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required status missing: blocked" in stderr
    assert "status counts: pass=1" in stderr


def test_cli_require_status_count_passes_for_exact_distribution(tmp_path):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    run_dir = tmp_path / "run"
    input_dir.mkdir()
    compare_dir.mkdir()
    run_dir.mkdir()
    for directory, schema, kind in [
        (input_dir, "vemcad.acad_reference_batch_artifact_index/v1", "batch"),
        (compare_dir, "vemcad.acad_manifest_compare_artifact_index/v1", "compare"),
        (run_dir, "vemcad.acad_reference_request_run_artifact_index/v1", "request_run"),
    ]:
        _write(directory / "artifact_index.json", {
            "schema": schema,
            "kind": kind,
            "status": "pass",
            "recommended_next_action": {
                "code": "review-x3-pass",
                "message": "review",
                "domain": "pass-review",
            },
            "artifacts": [],
        })

    assert route.main([
        str(input_dir),
        str(compare_dir),
        str(run_dir),
        "--require-status-count",
        "pass=3",
    ]) == 0


def test_cli_require_status_count_fails_closed_for_mismatch(tmp_path, capsys):
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
        "status": "review",
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        str(compare_dir),
        "--require-status-count",
        "pass=2",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required status count mismatch: pass=2 (got 1)" in stderr
    assert "status counts: pass=1, review=1" in stderr


def test_cli_forbid_status_passes_when_absent(tmp_path):
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
        "--forbid-status",
        "blocked",
    ]) == 0


def test_cli_forbid_status_fails_closed_when_present(tmp_path, capsys):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "missing_references",
        "status": "blocked",
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
        "--forbid-status",
        "blocked",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden status present: blocked=1" in stderr
    assert "status counts: blocked=1, viewspace_mismatch=1" in stderr


def test_cli_require_final_exit_code_passes_when_present(tmp_path):
    input_dir = tmp_path / "input"
    run_dir = tmp_path / "run"
    input_dir.mkdir()
    run_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "final_exit_code": 0,
        "case_count": 1,
        "artifacts": [],
    })
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "pass",
        "final_exit_code": 2,
        "recommended_next_action": {
            "code": "inspect-returned-reference-warnings",
            "message": "review input",
            "domain": "input-review",
        },
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        str(run_dir),
        "--require-final-exit-code",
        "0",
        "--require-final-exit-code",
        "2",
        "--require-final-exit-code-count",
        "0=1",
        "--require-final-exit-code-count",
        "2=1",
    ]) == 0


def test_cli_require_final_exit_code_fails_when_missing(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "final_exit_code": 0,
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-final-exit-code",
        "2",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required final exit code missing: 2" in stderr
    assert "final exit code counts: 0=1" in stderr


def test_cli_forbid_final_exit_code_fails_when_present(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "viewspace_mismatch",
        "final_exit_code": 2,
        "recommended_next_action": {
            "code": "recapture-autocad-or-provide-window",
            "message": "recapture",
            "domain": "input",
        },
        "case_actions": [],
        "artifacts": [],
    })

    assert route.main([
        str(run_dir),
        "--forbid-final-exit-code",
        "2",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden final exit code present: 2=1" in stderr
    assert "final exit code counts: 2=1" in stderr


def test_cli_require_final_exit_code_count_fails_on_count_mismatch(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "final_exit_code": 0,
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-final-exit-code-count",
        "0=2",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required final exit code count mismatch: 0=2 (got 1)" in stderr
    assert "final exit code counts: 0=1" in stderr


def test_cli_require_kind_passes_when_present(tmp_path):
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
        "--require-kind",
        "batch",
        "--require-kind",
        "compare",
    ]) == 0


def test_cli_require_kind_fails_closed_when_missing(tmp_path, capsys):
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
        "--require-kind",
        "compare",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required kind missing: compare" in stderr
    assert "kind counts: batch=1" in stderr


def test_cli_forbid_kind_passes_when_absent(tmp_path):
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
        "--forbid-kind",
        "compare",
    ]) == 0


def test_cli_forbid_kind_fails_closed_when_present(tmp_path, capsys):
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
        "--forbid-kind",
        "compare",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden kind present: compare=1" in stderr
    assert "kind counts: batch=1, compare=1" in stderr


def test_cli_require_artifact_kind_passes_when_present(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [
            {"kind": "reference_intake_tsv", "path": "reference_intake.tsv"},
        ],
    })

    assert route.main([
        str(input_dir),
        "--require-artifact-kind",
        "reference_intake_tsv",
    ]) == 0

    payload = route.route_artifact_index(input_dir)
    assert payload["artifact_kind_counts"] == {"reference_intake_tsv": 1}


def test_cli_require_artifact_kind_fails_closed_when_missing(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [
            {"kind": "reference_intake_markdown", "path": "reference_intake.md"},
        ],
    })

    assert route.main([
        str(input_dir),
        "--require-artifact-kind",
        "reference_intake_tsv",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required artifact kind missing: reference_intake_tsv" in stderr
    assert "artifact kind counts: reference_intake_markdown=1" in stderr


def test_cli_require_artifact_kind_count_passes_for_exact_distribution(tmp_path):
    input_dir = tmp_path / "input"
    run_dir = tmp_path / "run"
    input_dir.mkdir()
    run_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [
            {"kind": "reference_intake_tsv", "path": "reference_intake.tsv"},
            {"kind": "reference_request_validation_tsv", "path": "reference_request_validation.tsv"},
        ],
    })
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "pass",
        "final_exit_code": 0,
        "recommended_next_action": {
            "code": "review-x3-pass",
            "message": "review",
            "domain": "pass-review",
        },
        "case_actions": [],
        "artifacts": [
            {"kind": "reference_intake_tsv", "path": "input/reference_intake.tsv"},
            {"kind": "reference_request_validation_tsv", "path": "input/reference_request_validation.tsv"},
        ],
    })

    assert route.main([
        str(input_dir),
        str(run_dir),
        "--require-artifact-kind-count",
        "reference_intake_tsv=2",
        "--require-artifact-kind-count",
        "reference_request_validation_tsv=2",
    ]) == 0


def test_cli_require_artifact_kind_count_fails_closed_for_mismatch(tmp_path, capsys):
    input_dir = tmp_path / "input"
    run_dir = tmp_path / "run"
    input_dir.mkdir()
    run_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [
            {"kind": "reference_intake_tsv", "path": "reference_intake.tsv"},
        ],
    })
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "pass",
        "final_exit_code": 0,
        "recommended_next_action": {
            "code": "review-x3-pass",
            "message": "review",
            "domain": "pass-review",
        },
        "case_actions": [],
        "artifacts": [
            {"kind": "reference_intake_tsv", "path": "input/reference_intake.tsv"},
        ],
    })

    assert route.main([
        str(input_dir),
        str(run_dir),
        "--require-artifact-kind-count",
        "reference_intake_tsv=1",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required artifact kind count mismatch: reference_intake_tsv=1 (got 2)" in stderr
    assert "artifact kind counts: reference_intake_tsv=2" in stderr


def test_cli_forbid_artifact_kind_fails_closed_when_present(tmp_path, capsys):
    input_dir = tmp_path / "input"
    run_dir = tmp_path / "run"
    input_dir.mkdir()
    run_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [
            {"kind": "reference_intake_tsv", "path": "reference_intake.tsv"},
        ],
    })
    _write(run_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_request_run_artifact_index/v1",
        "status": "pass",
        "final_exit_code": 0,
        "recommended_next_action": {
            "code": "review-x3-pass",
            "message": "review",
            "domain": "pass-review",
        },
        "case_actions": [],
        "artifacts": [
            {"kind": "reference_intake_tsv", "path": "input/reference_intake.tsv"},
        ],
    })

    assert route.main([
        str(input_dir),
        str(run_dir),
        "--forbid-artifact-kind",
        "reference_intake_tsv",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden artifact kind present: reference_intake_tsv=2" in stderr
    assert "artifact kind counts: reference_intake_tsv=2" in stderr


def test_cli_require_route_count_passes_for_batch(tmp_path):
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
        "--require-route-count",
        "2",
    ]) == 0


def test_cli_require_route_count_passes_for_single_route(tmp_path):
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
        "--require-route-count",
        "1",
    ]) == 0


def test_cli_require_route_count_fails_closed_when_route_missing(tmp_path, capsys):
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
        "--require-route-count",
        "2",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required route count 2 but got 1" in stderr
    assert "kind counts: batch=1" in stderr


def test_cli_require_issue_code_passes_when_present(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "review",
        "case_count": 1,
        "reference_request_validation_issue_code_counts": {
            "source_dxf_sha256_mismatch": 1,
        },
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-issue-code",
        "source_dxf_sha256_mismatch",
        "--require-issue-code",
        "corner_background_not_white",
        "--require-issue-code-count",
        "corner_background_not_white=2",
    ]) == 0


def test_cli_require_issue_code_count_fails_closed_on_mismatch(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "review",
        "case_count": 1,
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-issue-code-count",
        "corner_background_not_white=1",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required issue code count mismatch: corner_background_not_white=1 (got 2)" in stderr
    assert "issue code counts: corner_background_not_white=2" in stderr


def test_cli_issue_code_guards_include_compare_issues(tmp_path, capsys):
    compare_dir = tmp_path / "compare"
    compare_dir.mkdir()
    _write(compare_dir / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "blocked",
        "case_count": 1,
        "compared_count": 0,
        "issue_code_counts": {"diagnostic_capture_method": 1},
        "artifacts": [],
    })

    assert route.main([
        str(compare_dir),
        "--require-issue-code",
        "diagnostic_capture_method",
    ]) == 0

    assert route.main([
        str(compare_dir),
        "--forbid-issue-code",
        "diagnostic_capture_method",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden issue code present: diagnostic_capture_method=1" in stderr
    assert "issue code counts: diagnostic_capture_method=1" in stderr


def test_cli_require_issue_code_fails_closed_when_missing(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "review",
        "case_count": 1,
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-issue-code",
        "returned_reference_blank",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "required issue code missing: returned_reference_blank" in stderr
    assert "issue code counts: corner_background_not_white=2" in stderr


def test_cli_forbid_issue_code_passes_when_absent(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "review",
        "case_count": 1,
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--forbid-issue-code",
        "returned_reference_blank",
    ]) == 0


def test_cli_forbid_issue_code_fails_closed_when_present(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "reference_intake",
        "status": "review",
        "case_count": 1,
        "reference_intake_issue_code_counts": {
            "corner_background_not_white": 2,
        },
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--forbid-issue-code",
        "corner_background_not_white",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden issue code present: corner_background_not_white=2" in stderr
    assert "issue code counts: corner_background_not_white=2" in stderr


def test_cli_forbid_current_acad_candidate_identity_warning(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "request_validation",
        "status": "review",
        "case_count": 1,
        "reference_request_validation_issue_code_counts": {
            "current_acad_matches_candidate_png": 1,
        },
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--forbid-issue-code",
        "current_acad_matches_candidate_png",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden issue code present: current_acad_matches_candidate_png=1" in stderr
    assert "issue code counts: current_acad_matches_candidate_png=1" in stderr


def test_cli_forbid_missing_current_acad_warning(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "stage": "request_validation",
        "status": "review",
        "case_count": 1,
        "reference_request_validation_issue_code_counts": {
            "current_acad_png_missing": 1,
        },
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--forbid-issue-code",
        "current_acad_png_missing",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "forbidden issue code present: current_acad_png_missing=1" in stderr
    assert "issue code counts: current_acad_png_missing=1" in stderr


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


def test_cli_require_request_boundary_passes_when_exposed_routes_match(tmp_path):
    input_dir = tmp_path / "input"
    compare_dir = tmp_path / "compare"
    input_dir.mkdir()
    compare_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "boundary": {"compares_renders": False, "autocad_equivalence_claim": False},
        "source_request_boundary": {
            "requires_returned_autocad_png": True,
            "requires_viewspace_match": True,
            "autocad_equivalence_claim": False,
        },
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
        "--require-request-boundary",
        "requires_returned_autocad_png=true",
        "--require-request-boundary",
        "autocad_equivalence_claim=false",
    ]) == 0


def test_cli_require_request_boundary_fails_when_no_route_exposes_it(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "boundary": {"compares_renders": False, "autocad_equivalence_claim": False},
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-request-boundary",
        "autocad_equivalence_claim=false",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "source request boundary requirement failed" in stderr
    assert "no routed artifact exposed source_request_boundary" in stderr


def test_cli_require_request_boundary_fails_on_mismatch(tmp_path, capsys):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "artifact_index.json", {
        "schema": "vemcad.acad_reference_batch_artifact_index/v1",
        "boundary": {"compares_renders": False, "autocad_equivalence_claim": False},
        "source_request_boundary": {
            "requires_returned_autocad_png": True,
            "autocad_equivalence_claim": False,
        },
        "stage": "reference_intake",
        "status": "pass",
        "case_count": 1,
        "artifacts": [],
    })

    assert route.main([
        str(input_dir),
        "--require-request-boundary",
        "requires_returned_autocad_png=false",
    ]) == 2
    stderr = capsys.readouterr().err

    assert "source request boundary requirement failed" in stderr
    assert "source request boundary requires_returned_autocad_png=True != False" in stderr


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
        "issue_code_counts": {"diagnostic_capture_method": 1},
        "artifacts": [],
    })

    payload = route.route_artifact_index(index)
    text = route._write_text(payload)
    markdown = route.route_markdown(payload)

    assert payload["kind"] == "compare"
    assert payload["case_count"] == 2
    assert payload["compared_count"] == 2
    assert payload["recommended_next_action"]["code"] == "inspect-renderer-candidate"
    assert payload["recommended_next_action"]["domain"] == "renderer-candidate"
    assert payload["triage_bucket_counts"]["renderer-candidate"] == 1
    assert payload["viewspace_status_counts"] == {"match": 1, "mismatch": 1}
    assert payload["x3_band_counts"] == {"fail": 1, "fallback": 1}
    assert payload["compare_issue_code_counts"] == {"diagnostic_capture_method": 1}
    assert "case_count: 2" in text
    assert "compared_count: 2" in text
    assert "compare_issue_code_counts: diagnostic_capture_method=1" in text
    assert "viewspace_status_counts: match=1, mismatch=1" in text
    assert "x3_band_counts: fail=1, fallback=1" in text
    assert "- case_count: `2`" in markdown
    assert "- compared_count: `2`" in markdown
    assert "- compare_issue_code_counts: `diagnostic_capture_method=1`" in markdown
    assert "- viewspace_status_counts: `match=1, mismatch=1`" in markdown
    assert "- x3_band_counts: `fail=1, fallback=1`" in markdown


def test_routes_compare_recapture_points_to_reference_request(tmp_path):
    request_md = tmp_path / "reference_request.md"
    request_md.write_text("# request\n", encoding="utf-8")
    index = _write(tmp_path / "artifact_index.json", {
        "schema": "vemcad.acad_manifest_compare_artifact_index/v1",
        "status": "viewspace_mismatch",
        "case_count": 1,
        "compared_count": 1,
        "triage_bucket_counts": {
            "recapture-required": 1,
        },
        "viewspace_status_counts": {"mismatch": 1},
        "x3_band_counts": {"fallback": 1},
        "artifacts": [
            {"kind": "reference_request_markdown", "path": "reference_request.md"},
        ],
    })

    payload = route.route_artifact_index(index)
    text = route._write_text(payload)
    markdown = route.route_markdown(payload)

    assert payload["recommended_next_action"]["code"] == "recapture-autocad-or-provide-window"
    assert payload["recommended_next_action"]["artifact"] == "reference_request.md"
    assert payload["action_artifact_resolved"] == str(request_md.resolve())
    assert payload["action_artifact_exists"] is True
    assert "action_artifact: reference_request.md" in text
    assert "- action_artifact: `reference_request.md`" in markdown
    assert "- action_artifact_exists: `True`" in markdown


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
        "issue_code_counts": {"candidate_case_missing": 1},
        "artifacts": [],
    })

    payload = route.route_artifact_indexes([validation_dir, compare_dir])
    text = route._write_batch_text(payload)
    markdown = route.route_markdown(payload)

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
    assert payload["compare_case_count"] == 1
    assert payload["compared_count"] == 1
    assert payload["triage_bucket_counts"] == {"renderer-candidate": 1}
    assert payload["viewspace_status_counts"] == {"match": 1}
    assert payload["x3_band_counts"] == {"fail": 1}
    assert payload["compare_issue_code_counts"] == {"candidate_case_missing": 1}
    assert "compare_case_count: 1" in text
    assert "compared_count: 1" in text
    assert "compare_issue_code_counts: candidate_case_missing=1" in text
    assert "triage_bucket_counts: renderer-candidate=1" in text
    assert "viewspace_status_counts: match=1" in text
    assert "x3_band_counts: fail=1" in text
    assert "- compare_case_count: `1`" in markdown
    assert "- compared_count: `1`" in markdown
    assert "- compare_issue_code_counts: `candidate_case_missing=1`" in markdown
    assert "- triage_bucket_counts: `renderer-candidate=1`" in markdown
    assert "- viewspace_status_counts: `match=1`" in markdown
    assert "- x3_band_counts: `fail=1`" in markdown


def test_rejects_unknown_schema(tmp_path):
    index = _write(tmp_path / "artifact_index.json", {"schema": "unknown"})

    assert route.main([str(index)]) == 2


def test_rejects_directory_without_artifact_index(tmp_path):
    assert route.main([str(tmp_path)]) == 2
