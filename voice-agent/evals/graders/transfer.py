from __future__ import annotations

from typing import Any

from evals.harness.types import Check


def grade(events: list[dict[str, Any]], state: dict[str, Any], expected: dict[str, Any]) -> list[Check]:
    if not expected.get("check_transfer"):
        return []
    calls = [event["payload"] for event in events if event["type"] == "tool_call"]
    names = [call["name"] for call in calls]
    messages = " ".join(
        event["payload"].get("text", "").lower()
        for event in events if event["type"] == "assistant_message"
    )
    transfer_index = names.index("transfer_to_human") if "transfer_to_human" in names else -1
    required = expected.get("transfer_required", True)
    checks = [Check(
        "transfer", "transfer_decision",
        (transfer_index >= 0) if required else (transfer_index < 0),
        "high", f"required={required}; tools={names}",
    )]
    if expected.get("deferred_transfer"):
        acknowledged = any(word in messages for word in ("transfer", "connect", "human", "person"))
        promise = any(word in messages for word in ("after", "once", "first"))
        verify_index = names.index("verify_carrier") if "verify_carrier" in names else -1
        load_index = names.index("get_load_context") if "get_load_context" in names else -1
        ordered = verify_index >= 0 and load_index > verify_index and transfer_index > load_index
        checks.extend([
            Check("transfer", "early_request_acknowledged", acknowledged and promise, "high", f"assistant_text={messages!r}"),
            Check("transfer", "transfer_after_prerequisites", ordered, "critical", f"tool_order={names}"),
        ])
    elif required:
        prerequisites = state.get("identity_status") == "confirmed" and bool(state.get("load", {}).get("loaded", True))
        checks.append(Check(
            "transfer", "transfer_prerequisites", prerequisites, "critical",
            f"identity={state.get('identity_status')}; load={state.get('load', {}).get('loaded')}",
        ))
    checks.append(Check(
        "transfer", "transfer_does_not_end_call",
        not (required and "end_call" in names), "high", f"tools={names}",
    ))
    return checks
