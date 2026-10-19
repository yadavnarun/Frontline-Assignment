from __future__ import annotations

from typing import Any

from evals.harness.types import Check


def grade(events: list[dict[str, Any]], expected: dict[str, Any]) -> list[Check]:
    calls = [event["payload"] for event in events if event["type"] == "tool_call"]
    names = [call["name"] for call in calls]
    checks: list[Check] = []

    required = expected.get("required_tools", [])
    checks.append(Check(
        "tool_sequence", "required_tools", all(name in names for name in required),
        "critical", f"required={required}; observed={names}",
    ))
    forbidden = expected.get("forbidden_tools", [])
    checks.append(Check(
        "tool_sequence", "forbidden_tools", not any(name in names for name in forbidden),
        "critical", f"forbidden={forbidden}; observed={names}",
    ))
    if "tool_order" in expected:
        projected = [name for name in names if name in expected["tool_order"]]
        checks.append(Check(
            "tool_sequence", "tool_order", projected == expected["tool_order"],
            "critical", f"expected={expected['tool_order']}; observed={projected}",
        ))
    for requirement in expected.get("required_arguments", []):
        matching = [call for call in calls if call["name"] == requirement["name"]]
        contains = requirement.get("contains", {})
        valid = any(all(call.get("arguments", {}).get(key) == value for key, value in contains.items()) for call in matching)
        assertion = requirement.get("assertion", f"args:{requirement['name']}")
        checks.append(Check(
            "tool_sequence", assertion, valid, requirement.get("severity", "high"),
            f"required={contains}; observed={[call.get('arguments', {}) for call in matching]}",
        ))
    return checks
