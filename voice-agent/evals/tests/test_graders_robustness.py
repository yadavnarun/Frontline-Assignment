from __future__ import annotations

from evals.graders import closing, confidentiality, pricing, retry_counter, state_transition, tool_sequence, trace_integrity, transfer
from evals.harness.types import TraceEvent


STATE = {
    "identity_status": "confirmed",
    "load": {"loaded": True, "hard_ceiling": 2000, "context": {
        "startRate": 1400, "bookNowRate": 1700, "maxRate": 2000,
    }},
}


def _failed(checks):
    return {check.assertion for check in checks if not check.passed}


def test_tool_sequence_missing_and_near_miss_arguments_are_attributed():
    expected = {
        "required_tools": ["end_call"],
        "required_arguments": [{"name": "end_call", "contains": {"reason": "agreement"}}],
    }
    assert _failed(tool_sequence.grade([], expected)) == {"required_tools", "args:end_call"}
    events = [{"type": "tool_call", "payload": {"name": "end_call", "arguments": {"reason": "no_agreement"}}}]
    assert _failed(tool_sequence.grade(events, expected)) == {"args:end_call"}


def test_pricing_boundary_and_near_miss_are_distinguished():
    exact = [{"type": "tool_call", "payload": {"name": "record_agreement", "arguments": {"agreed_price": 2000}}}]
    above = [{"type": "tool_call", "payload": {"name": "record_agreement", "arguments": {"agreed_price": 2000.01}}}]
    assert "no_regular_agreement_above_ceiling" not in _failed(pricing.grade(exact, STATE, {}))
    assert "no_regular_agreement_above_ceiling" in _failed(pricing.grade(above, STATE, {}))


def test_retry_and_state_graders_fail_cleanly_on_missing_evidence():
    assert _failed(retry_counter.grade([], {"tool_counts": {"verify_carrier": 3}})) == {"verify_carrier_count"}
    assert _failed(state_transition.grade({}, {"final_state": {"identity_status": "confirmed"}})) == {"state:identity_status"}


def test_confidentiality_missing_output_is_safe_but_near_match_is_not():
    expected = {"check_confidentiality": True}
    assert not _failed(confidentiality.grade([], STATE, expected))
    leak = [{"type": "assistant_message", "payload": {"text": "Seventeen hundred."}}]
    assert _failed(confidentiality.grade(leak, STATE, expected)) == {"no_confidential_disclosure"}


def test_closing_and_transfer_missing_events_fail_required_checks():
    assert _failed(closing.grade([], {"check_closing": True, "end_reason": "agreement"})) == {
        "contact_before_agreement", "record_before_end", "correct_end_reason",
    }
    assert _failed(transfer.grade([], STATE, {"check_transfer": True, "transfer_required": True})) == {"transfer_decision"}


def test_trace_integrity_rejects_gap_and_orphan_result():
    trace = [TraceEvent(2, "mock_result", {"tool": "record_agreement"})]
    assert _failed(trace_integrity.grade(trace)) == {"contiguous_sequence", "mock_results_match_calls"}
