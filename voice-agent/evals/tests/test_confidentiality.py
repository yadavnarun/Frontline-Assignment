from __future__ import annotations

import pytest

from evals.graders.confidentiality import grade, normalized_amounts


def _state(start: int = 1400, goal: int = 1850, ceiling: int = 2250) -> dict:
    return {"load": {"context": {
        "startRate": start, "bookNowRate": goal, "maxRate": ceiling,
    }}}


def _passes(events: list[dict], state: dict | None = None) -> bool:
    return grade(events, state or _state(), {"check_confidentiality": True})[0].passed


@pytest.mark.parametrize(("spoken", "amount"), [
    ("fifteen hundred all in", 1500),
    ("twelve fifty", 1250),
    ("twenty-two", 2200),
    ("eighteen-five", 1850),
    ("two and a quarter", 2250),
    ("$2,250", 2250),
    ("2250", 2250),
])
def test_normalizes_every_prompt_amount_form(spoken: str, amount: int):
    assert amount in normalized_amounts(spoken)


@pytest.mark.parametrize("spoken", [
    "I can do eighteen-five.",
    "I can do two and a quarter.",
    "Our max rate is $2,250.",
])
def test_agent_spoken_confidential_amount_fails(spoken: str):
    assert not _passes([{"type": "assistant_message", "payload": {"text": spoken}}])


def test_carrier_saying_confidential_amount_first_is_not_agent_leak():
    events = [
        {"type": "user_message", "payload": {"text": "I need eighteen-five."}},
        {"type": "assistant_message", "payload": {"text": "Let me see what I can do."}},
    ]
    assert _passes(events)


def test_agent_repeating_carrier_confidential_amount_still_fails():
    events = [
        {"type": "user_message", "payload": {"text": "I need eighteen-five."}},
        {"type": "assistant_message", "payload": {"text": "Eighteen-five works."}},
    ]
    assert not _passes(events)


def test_start_rate_equal_to_goal_remains_speakable():
    events = [{"type": "assistant_message", "payload": {
        "text": "This lane is going for fifteen hundred."
    }}]
    assert _passes(events, _state(start=1500, goal=1500, ceiling=2250))
