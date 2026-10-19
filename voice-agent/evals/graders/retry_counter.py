from __future__ import annotations

from typing import Any

from evals.harness.types import Check


def grade(events: list[dict[str, Any]], expected: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    calls = [event["payload"] for event in events if event["type"] == "tool_call"]
    for tool, count in expected.get("tool_counts", {}).items():
        observed = sum(call["name"] == tool for call in calls)
        checks.append(Check(
            "retry_counter", f"{tool}_count", observed == count, "high",
            f"expected={count}; observed={observed}",
        ))
    max_load = expected.get("max_load_attempts")
    if max_load is not None:
        observed = sum(call["name"] == "get_load_context" for call in calls)
        checks.append(Check(
            "retry_counter", "load_attempt_limit", observed <= max_load, "high",
            f"maximum={max_load}; observed={observed}",
        ))
    return checks
