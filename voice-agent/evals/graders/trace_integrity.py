from __future__ import annotations

from typing import Any

from evals.harness.types import Check, TraceEvent


def grade(events: list[TraceEvent]) -> list[Check]:
    sequences = [event.sequence for event in events]
    contiguous = sequences == list(range(1, len(events) + 1))
    calls = [event.payload.get("name") for event in events if event.type == "tool_call"]
    results = [event.payload.get("tool") for event in events if event.type == "mock_result"]
    unmatched = [name for name in results if name not in calls]
    return [
        Check("trace_integrity", "contiguous_sequence", contiguous, "high", f"sequences={sequences}"),
        Check("trace_integrity", "mock_results_match_calls", not unmatched, "high", f"unmatched={unmatched}"),
    ]
