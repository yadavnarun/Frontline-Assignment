from __future__ import annotations

import json
import platform
from importlib.metadata import PackageNotFoundError, version
from datetime import datetime, timezone
from pathlib import Path

from evals.harness.types import TrialResult


KNOWN_GAPS = [
    {"id": "ceiling_not_backend_enforced", "severity": "critical", "status": "characterized", "evidence": "test_known_gap_backend_accepts_regular_agreement_above_ceiling"},
    {"id": "contact_name_not_backend_enforced", "severity": "high", "status": "characterized", "evidence": "test_known_gap_regular_agreement_does_not_require_contact_name"},
    {"id": "transfer_verification_not_backend_enforced", "severity": "high", "status": "characterized", "evidence": "test_known_gap_transfer_does_not_require_confirmed_carrier"},
    {"id": "record_agreement_retry_submits_second_quote", "severity": "high", "status": "characterized", "evidence": "test_known_gap_retry_submits_a_second_quote"},
]


def _dependency_manifest() -> dict[str, str]:
    dependencies = {"python": platform.python_version()}
    for package in ("pipecat-ai", "pytest", "PyYAML"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = "not-installed"
    return dependencies


def assessed_correctly(result: TrialResult) -> bool:
    if result.expected == "pass":
        return result.harness_passed
    return set(result.failed_assertions) == set(_expected_failures(result))


def _expected_failures(result: TrialResult) -> list[str]:
    for event in result.events:
        if event.type == "expected_failures":
            return list(event.payload.get("assertions", []))
    return []


def build(results: list[TrialResult], live_status: str = "NOT RUN") -> dict:
    rows = []
    for result in results:
        row = result.as_dict()
        row["script_classification_correct"] = assessed_correctly(result)
        row["expected_failures"] = _expected_failures(result)
        rows.append(row)
    scenarios = []
    for scenario in sorted({row["scenario"] for row in rows}):
        scenario_rows = [row for row in rows if row["scenario"] == scenario]
        scenarios.append({
            "scenario": scenario,
            "severity": scenario_rows[0]["severity"],
            "scripts": len(scenario_rows),
            "correct_classifications": sum(row["script_classification_correct"] for row in scenario_rows),
        })
    severity = {}
    for level in ("critical", "high", "medium", "low"):
        level_rows = [row for row in rows if row["severity"] == level]
        if level_rows:
            severity[level] = {
                "scripts": len(level_rows),
                "correct_classifications": sum(row["script_classification_correct"] for row in level_rows),
            }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "scripted",
        "model_settings": {
            "provider": "none", "model": "deterministic_fixture",
            "temperature": 0, "seed": "fixed",
        },
        "live_model": {"status": live_status, "reason": "No model API credentials are available"},
        "known_gaps": KNOWN_GAPS,
        "dependencies": _dependency_manifest(),
        "artifact_contract": {
            "summary": "summary.md", "report": "report.json",
            "traces": "traces/<scenario>/<script>-trial-<NNN>.json",
        },
        "summary": {
            "script_classifications": len(rows),
            "correct_classifications": sum(row["script_classification_correct"] for row in rows),
            "classification_failures": sum(not row["script_classification_correct"] for row in rows),
        },
        "scenario_summary": scenarios,
        "severity_summary": severity,
        "results": rows,
    }


def write(report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Frontline evaluation summary", "",
        f"- Correct scripted-fixture classifications: {report['summary']['correct_classifications']}/{report['summary']['script_classifications']}",
        "- This measures grader/harness correctness, not live-agent behavior.",
        f"- Live model: {report['live_model']['status']} — {report['live_model']['reason']}", "",
        "## Scripted-fixture classification table", "",
        "| Scenario | Severity | Correct classifications | Fixture trials |",
        "|---|---|---:|---:|",
    ]
    for scenario in report["scenario_summary"]:
        lines.append(
            f"| {scenario['scenario']} | {scenario['severity']} | {scenario['correct_classifications']} | {scenario['scripts']} |"
        )
    lines.extend([
        "", "## Severity summary", "",
        "| Severity | Correct classifications | Fixture trials |",
        "|---|---:|---:|",
    ])
    for level, summary in report["severity_summary"].items():
        lines.append(f"| {level} | {summary['correct_classifications']} | {summary['scripts']} |")
    lines.extend([
        "", "## Characterized production gaps", "",
        "These are observations, not harness failures or core-code fixes.", "",
        "| Gap | Severity | Status | Evidence |", "|---|---|---|---|",
    ])
    for gap in report["known_gaps"]:
        lines.append(f"| {gap['id']} | {gap['severity']} | {gap['status']} | `{gap['evidence']}` |")
    lines.extend([
        "", "## Scripted-fixture details", "",
        "| Script | Trial | Expected fixture behavior | Observed grader failures | Classification correct | Time (ms) |",
        "|---|---:|---|---|---|---:|",
    ])
    for result in report["results"]:
        failures = ", ".join(result["failed_assertions"]) or "none"
        status = "PASS" if result["script_classification_correct"] else "FAIL"
        lines.append(
            f"| {result['script']} | {result['trial']} | {result['expected']} | {failures} | {status} | {result['elapsed_ms']:.2f} |"
        )
    (output / "summary.md").write_text("\n".join(lines) + "\n")

    traces = output / "traces"
    for result in report["results"]:
        directory = traces / result["scenario"]
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{result['script']}-trial-{result['trial']:03d}.json"
        (directory / filename).write_text(json.dumps(result, indent=2) + "\n")
