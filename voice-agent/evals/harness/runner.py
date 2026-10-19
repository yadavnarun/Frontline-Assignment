from __future__ import annotations

import copy
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import yaml

from evals.graders import (
    closing, confidentiality, pricing, retry_counter, state_transition,
    tool_sequence, trace_integrity, transfer,
)
from evals.harness.boundary_patcher import block_network
from evals.harness.tool_parity import assert_harness_parity, production_tool_schemas
from evals.harness.types import TraceEvent, TrialResult
from evals.harness.validation import validate_catalog, validate_script
from voice_prompt import build_full_negotiation_prompt


VOICE_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def mock_manifest() -> dict[str, list[str]]:
    return load_yaml(EVAL_ROOT / "config/external_boundaries.yaml")


def scenario_catalog() -> dict[str, Any]:
    path = EVAL_ROOT / "config/scenarios.yaml"
    catalog = load_yaml(path)
    validate_catalog(catalog, path)
    return catalog


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def run_script(path: Path, trial: int = 1) -> TrialResult:
    started = time.perf_counter()
    with block_network():
        spec = load_yaml(path)
        catalog = scenario_catalog()
        validate_script(spec, catalog, path)
        base_state = load_yaml(EVAL_ROOT / "fixtures/base_state.yaml")
        initial_state = _deep_merge(base_state, spec.get("initial_state", {}))
        state = copy.deepcopy(initial_state)
        schemas = production_tool_schemas(VOICE_ROOT)
        assert_harness_parity(VOICE_ROOT, schemas)
        rendered_prompt = build_full_negotiation_prompt(state["load"]["context"])

        trace: list[TraceEvent] = []
        for sequence, raw_event in enumerate(spec["events"], start=1):
            if len(raw_event) != 1:
                raise ValueError(f"Each event needs exactly one type: {raw_event}")
            event_type, payload = next(iter(raw_event.items()))
            before = copy.deepcopy(state)
            payload = payload or {}
            if event_type == "state_update":
                for key, value in payload.items():
                    state[key] = copy.deepcopy(value)
            elif event_type == "tool_call":
                state.setdefault("tool_history", []).append(copy.deepcopy(payload))
            trace.append(TraceEvent(sequence, event_type, copy.deepcopy(payload), before, copy.deepcopy(state)))

    event_dicts = [
        {"type": event.type, "payload": event.payload}
        for event in trace
    ]
    expectations = spec.get("expectations", {})
    checks = tool_sequence.grade(event_dicts, expectations)
    checks.extend(pricing.grade(event_dicts, initial_state, expectations))
    checks.extend(retry_counter.grade(event_dicts, expectations))
    checks.extend(confidentiality.grade(event_dicts, initial_state, expectations))
    checks.extend(state_transition.grade(state, expectations))
    checks.extend(closing.grade(event_dicts, expectations))
    checks.extend(transfer.grade(event_dicts, initial_state, expectations))
    checks.extend(trace_integrity.grade(trace))

    return TrialResult(
        scenario=spec["scenario"],
        severity=catalog[spec["scenario"]]["severity"],
        script=spec["id"], trial=trial,
        expected=spec["expected"],
        checks=checks, events=trace, initial_state=initial_state, final_state=state,
        rendered_system_prompt=rendered_prompt, tool_schemas=schemas["room1"],
        mock_manifest=mock_manifest(), elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def discover_scripts() -> list[Path]:
    return sorted((EVAL_ROOT / "scripts").glob("**/*.yaml"))


def _run_job(job: tuple[Path, int]) -> TrialResult:
    return run_script(*job)


def run_suite(paths: list[Path], trials: int, workers: int = 1) -> list[TrialResult]:
    if trials < 1:
        raise ValueError("trials must be positive")
    if workers < 1:
        raise ValueError("workers must be positive")
    jobs = [(path, trial) for path in paths for trial in range(1, trials + 1)]
    if workers == 1:
        return [_run_job(job) for job in jobs]
    # Processes isolate module globals, environment mappings, mocks, and
    # mutable agent state. executor.map preserves deterministic report order.
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(_run_job, jobs))
