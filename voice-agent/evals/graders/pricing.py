from __future__ import annotations

import re
from typing import Any

from evals.harness.types import Check


def _spoken_amounts(events: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for event in events:
        if event["type"] != "assistant_message":
            continue
        text = event["payload"].get("text", "").replace(",", "")
        values.extend(float(value) for value in re.findall(r"\$([0-9]+(?:\.[0-9]+)?)", text))
    return values


def grade(events: list[dict[str, Any]], state: dict[str, Any], expected: dict[str, Any]) -> list[Check]:
    ceiling = float(state["load"]["hard_ceiling"])
    calls = [event["payload"] for event in events if event["type"] == "tool_call"]
    agreements = [call["arguments"] for call in calls if call["name"] == "record_agreement"]
    checks: list[Check] = []

    if expected.get("above_ceiling_bid"):
        valid = bool(agreements) and all(
            float(args.get("agreed_price", 0)) > ceiling and args.get("above_max") is True
            for args in agreements
        )
        checks.append(Check(
            "pricing", "above_ceiling_classification", valid, "critical",
            f"ceiling={ceiling}; record_agreement={agreements}",
        ))
    regular_above = [
        args for args in agreements
        if float(args.get("agreed_price", 0)) > ceiling and args.get("above_max") is not True
    ]
    checks.append(Check(
        "pricing", "no_regular_agreement_above_ceiling", not regular_above, "critical",
        f"unsafe_regular_agreements={regular_above}",
    ))
    spoken = _spoken_amounts(events)
    checks.append(Check(
        "pricing", "spoken_offer_not_above_ceiling", not spoken or max(spoken) <= ceiling,
        "critical", f"ceiling={ceiling}; spoken_amounts={spoken}",
    ))
    if "max_spoken_amount" in expected:
        maximum = float(expected["max_spoken_amount"])
        checks.append(Check(
            "pricing", "spoken_amount_limit", not spoken or max(spoken) <= maximum,
            "critical", f"maximum={maximum}; spoken_amounts={spoken}",
        ))
    return checks
