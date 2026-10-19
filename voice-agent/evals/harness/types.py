from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TraceEvent:
    sequence: int
    type: str
    payload: dict[str, Any]
    state_before: dict[str, Any] = field(default_factory=dict)
    state_after: dict[str, Any] = field(default_factory=dict)


@dataclass
class Check:
    grader: str
    assertion: str
    passed: bool
    severity: str
    evidence: str


@dataclass
class TrialResult:
    scenario: str
    severity: str
    script: str
    trial: int
    expected: str
    checks: list[Check]
    events: list[TraceEvent]
    initial_state: dict[str, Any]
    final_state: dict[str, Any]
    rendered_system_prompt: str
    tool_schemas: list[dict[str, Any]]
    mock_manifest: dict[str, list[str]]
    elapsed_ms: float

    @property
    def failed_assertions(self) -> list[str]:
        return [check.assertion for check in self.checks if not check.passed]

    @property
    def harness_passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["failed_assertions"] = self.failed_assertions
        data["harness_passed"] = self.harness_passed
        return data
