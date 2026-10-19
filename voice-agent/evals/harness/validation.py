from __future__ import annotations

from pathlib import Path
from typing import Any


ALLOWED_EVENTS = {
    "assistant_message", "user_message", "tool_call", "mock_result",
    "state_update", "expected_failures",
}
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}


class SpecValidationError(ValueError):
    pass


def _fail(path: Path, message: str) -> None:
    raise SpecValidationError(f"{path}: {message}")


def validate_catalog(catalog: dict[str, Any], path: Path) -> None:
    if not catalog or len(catalog) > 15:
        _fail(path, f"scenario catalog must contain 1-15 entries; found {len(catalog)}")
    for scenario, definition in catalog.items():
        if not isinstance(definition, dict):
            _fail(path, f"scenario {scenario!r} must be a mapping")
        if definition.get("severity") not in ALLOWED_SEVERITIES:
            _fail(path, f"scenario {scenario!r} has invalid severity")
        if not isinstance(definition.get("title"), str) or not definition["title"].strip():
            _fail(path, f"scenario {scenario!r} needs a non-empty title")


def validate_script(spec: dict[str, Any], catalog: dict[str, Any], path: Path) -> None:
    required = {"scenario", "id", "expected", "events", "expectations"}
    missing = sorted(required - set(spec))
    if missing:
        _fail(path, f"missing required fields: {missing}")
    if spec["scenario"] not in catalog:
        _fail(path, f"unknown scenario {spec['scenario']!r}")
    if spec["expected"] not in {"pass", "fail"}:
        _fail(path, "expected must be 'pass' or 'fail'")
    if not isinstance(spec["id"], str) or not spec["id"].strip():
        _fail(path, "id must be a non-empty string")
    if not isinstance(spec["events"], list) or not spec["events"]:
        _fail(path, "events must be a non-empty list")
    if not isinstance(spec["expectations"], dict):
        _fail(path, "expectations must be a mapping")
    if "initial_state" in spec and not isinstance(spec["initial_state"], dict):
        _fail(path, "initial_state must be a mapping")

    failure_events = []
    called_tools: set[str] = set()
    for index, event in enumerate(spec["events"], start=1):
        if not isinstance(event, dict) or len(event) != 1:
            _fail(path, f"event {index} must contain exactly one event type")
        event_type, payload = next(iter(event.items()))
        if event_type not in ALLOWED_EVENTS:
            _fail(path, f"event {index} has unknown type {event_type!r}")
        if not isinstance(payload, dict):
            _fail(path, f"event {index} payload must be a mapping")
        if event_type in {"assistant_message", "user_message"} and not isinstance(payload.get("text"), str):
            _fail(path, f"event {index} requires text")
        if event_type == "tool_call":
            if not isinstance(payload.get("name"), str) or not isinstance(payload.get("arguments"), dict):
                _fail(path, f"event {index} tool_call requires name and arguments")
            called_tools.add(payload["name"])
        if event_type == "mock_result" and payload.get("tool") not in called_tools:
            _fail(path, f"event {index} mock_result precedes matching tool_call")
        if event_type == "expected_failures":
            assertions = payload.get("assertions")
            if not isinstance(assertions, list) or not assertions or not all(isinstance(item, str) for item in assertions):
                _fail(path, f"event {index} expected_failures needs string assertions")
            failure_events.append(payload)

    if spec["expected"] == "pass" and failure_events:
        _fail(path, "passing script cannot declare expected_failures")
    if spec["expected"] == "fail" and len(failure_events) != 1:
        _fail(path, "failing script must declare exactly one expected_failures event")
