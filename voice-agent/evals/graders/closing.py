from __future__ import annotations

from typing import Any

from evals.harness.types import Check


def grade(events: list[dict[str, Any]], expected: dict[str, Any]) -> list[Check]:
    if not expected.get("check_closing"):
        return []
    calls = [event["payload"] for event in events if event["type"] == "tool_call"]
    names = [call["name"] for call in calls]
    agreements = [call["arguments"] for call in calls if call["name"] == "record_agreement"]
    contact_ok = bool(agreements) and all(
        args.get("carrier_contact_name") and args.get("carrier_contact_phone")
        for args in agreements
    )
    record_index = names.index("record_agreement") if "record_agreement" in names else -1
    end_index = names.index("end_call") if "end_call" in names else -1
    order_ok = record_index >= 0 and end_index > record_index
    end_reason = None
    if end_index >= 0:
        end_reason = calls[end_index]["arguments"].get("reason")
    expected_reason = expected.get("end_reason")
    return [
        Check("closing", "contact_before_agreement", contact_ok, "critical", f"agreement_args={agreements}"),
        Check("closing", "record_before_end", order_ok, "critical", f"tool_order={names}"),
        Check("closing", "correct_end_reason", end_reason == expected_reason, "high", f"expected={expected_reason}; observed={end_reason}"),
    ]
