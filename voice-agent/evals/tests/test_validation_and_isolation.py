from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from evals.harness.runner import discover_scripts, load_yaml, run_script, run_suite, scenario_catalog
from evals.harness.validation import SpecValidationError, validate_catalog, validate_script


def _valid_spec() -> tuple[dict, Path]:
    path = next(path for path in discover_scripts() if path.stem == "01_valid_mc")
    return load_yaml(path), path


@pytest.mark.parametrize(("mutation", "message"), [
    (lambda spec: spec.pop("events"), "missing required fields"),
    (lambda spec: spec.update(scenario="unknown"), "unknown scenario"),
    (lambda spec: spec.update(expected="maybe"), "expected must be"),
    (lambda spec: spec.update(events=[{"unknown_event": {}}]), "unknown type"),
    (lambda spec: spec.update(events=[{"tool_call": {"name": "end_call"}}]), "requires name and arguments"),
    (lambda spec: spec.update(events=[{"mock_result": {"tool": "end_call"}}]), "precedes matching tool_call"),
    (lambda spec: spec.update(expected="pass", events=[{"expected_failures": {"assertions": ["x"]}}]), "passing script"),
])
def test_invalid_scripts_fail_with_actionable_errors(mutation, message):
    spec, path = _valid_spec()
    mutation(spec)
    with pytest.raises(SpecValidationError, match=message):
        validate_script(spec, scenario_catalog(), path)


def test_catalog_cap_and_severity_are_validated(tmp_path):
    oversized = {
        f"scenario-{index}": {"severity": "high", "title": "test"}
        for index in range(16)
    }
    with pytest.raises(SpecValidationError, match="1-15"):
        validate_catalog(oversized, tmp_path / "scenarios.yaml")
    with pytest.raises(SpecValidationError, match="invalid severity"):
        validate_catalog({"one": {"severity": "urgent", "title": "test"}}, tmp_path / "scenarios.yaml")


def test_parallel_process_trials_are_complete_and_do_not_share_state():
    path = next(path for path in discover_scripts() if path.stem == "above_ceiling")
    results = run_suite([path], trials=4, workers=2)
    assert [result.trial for result in results] == [1, 2, 3, 4]
    assert all(result.harness_passed for result in results)
    results[0].final_state["identity_status"] = "contaminated"
    assert all(result.final_state["identity_status"] == "confirmed" for result in results[1:])
    assert all(result.initial_state is not result.final_state for result in results)


def test_validation_does_not_mutate_fixture_input():
    spec, path = _valid_spec()
    original = copy.deepcopy(spec)
    validate_script(spec, scenario_catalog(), path)
    assert spec == original
