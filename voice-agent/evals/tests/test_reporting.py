from __future__ import annotations

from evals.harness.runner import discover_scripts, run_script
from evals.reporting.report_builder import build, write


def test_report_calls_results_fixture_classifications_and_links_real_gap_test(tmp_path):
    result = run_script(next(path for path in discover_scripts() if path.stem == "10_confidentiality"))
    report = build([result])
    write(report, tmp_path)

    assert report["summary"] == {
        "script_classifications": 1,
        "correct_classifications": 1,
        "classification_failures": 0,
    }
    assert report["results"][0]["script_classification_correct"] is True
    retry_gap = next(
        gap for gap in report["known_gaps"]
        if gap["id"] == "record_agreement_retry_submits_second_quote"
    )
    assert retry_gap["evidence"] == "test_known_gap_retry_submits_a_second_quote"
    summary = (tmp_path / "summary.md").read_text()
    assert "grader/harness correctness, not live-agent behavior" in summary
    assert "Scenario pass table" not in summary
