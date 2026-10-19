from __future__ import annotations

from typing import Any

from evals.harness.types import Check


def _get(state: dict[str, Any], path: str):
    value: Any = state
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def grade(final_state: dict[str, Any], expected: dict[str, Any]) -> list[Check]:
    checks = []
    for path, value in expected.get("final_state", {}).items():
        observed = _get(final_state, path)
        checks.append(Check(
            "state_transition", f"state:{path}", observed == value, "critical",
            f"expected={value!r}; observed={observed!r}",
        ))
    return checks
