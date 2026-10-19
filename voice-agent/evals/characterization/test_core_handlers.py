from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest
from pipecat.frames.frames import EndFrame

from call_helpers import end_call, get_load_context, verify_carrier
from evals.mocks.recording import AsyncRecordingBoundary, RecordingBoundary


def _context(**overrides):
    values = {
        "call_id": UUID("00000000-0000-4000-8000-000000000010"),
        "org_id": "00000000-0000-0000-0000-000000000001",
        "messages": [
            {"role": "system", "content": "greeting prompt"},
            {"role": "user", "content": "REF-1001"},
        ],
        "call_mode": "BOT",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_verify_carrier_real_handler_stages_identity_with_boundary_fakes():
    carrier = AsyncRecordingBoundary({"data": {
        "dbaName": "ACME TRUCKING", "mcNumber": "123456", "dotNumber": "1380078",
    }})
    update_call = RecordingBoundary()
    callback = AsyncRecordingBoundary()
    context = _context()

    with (
        patch("call_helpers.fetch_carrier_by_mc", new=carrier),
        patch("call_helpers.update_call_mc", new=update_call),
    ):
        await verify_carrier(
            "verify_carrier", "tool-1", {"mc_number": " 123456 "},
            None, context, callback,
        )

    result = json.loads(callback.calls[0]["args"][0])
    assert result == {
        "status": "success", "message": "Carrier found: Acme Trucking",
        "carrier_name": "Acme Trucking", "mc_number": "123456",
    }
    assert carrier.calls == [{"args": ["123456"], "kwargs": {}}]
    assert context.caller_mc == "123456"
    assert context.carrier_name == "Acme Trucking"
    assert context.caller_dot_number == "1380078"
    assert context.awaiting_carrier_identity_confirmation is True
    assert context.carrier_identity_confirmed is False


@pytest.mark.asyncio
async def test_get_load_context_real_handler_swaps_only_system_prompt():
    raw_load = {
        "id": "00000000-0000-4000-8000-000000000020",
        "load_id": "REF-1001",
        "origin_city": "Chicago", "origin_state": "IL",
        "destination_city": "Indianapolis", "destination_state": "IN",
        "pickup_time": "October 20th, 2026 at 9 AM",
        "dropoff_time": "October 20th, 2026 at 3 PM",
        "equipment": "Dry Van", "commodity": "Packaged goods",
        "special_instructions": "Driver must use a tracker",
        "tracker_required": True, "start_rate": 1400,
        "book_now_rate": 1700, "max_rate": 2000,
    }
    lookup = RecordingBoundary(raw_load)
    update_call = RecordingBoundary()
    callback = AsyncRecordingBoundary()
    context = _context()
    prior_user_message = context.messages[1].copy()

    with (
        patch("call_helpers.NegotiationDBService.get_load_by_reference", new=lookup),
        patch("call_helpers.update_call_load", new=update_call),
        patch.dict("os.environ", {"HIGHWAY_PHONE_LOOKUP_ENABLED": "false"}),
    ):
        await get_load_context(
            "get_load_context", "tool-1", {"load_id": "REF-1001"},
            None, context, callback, caller_phone="+12025550199",
        )

    result = json.loads(callback.calls[0]["args"][0])
    assert result["status"] == "success"
    assert lookup.calls == [{
        "args": ["REF-1001", context.org_id], "kwargs": {},
    }]
    assert context.messages[0]["role"] == "system"
    assert "We just found the load context for reference number: REF-1001" in context.messages[0]["content"]
    assert context.messages[1] == prior_user_message
    assert context.load_uuid == raw_load["id"]
    assert context.load_context["maxRate"] == 2000.0


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", ["", "Noted down", "reference"])
async def test_get_load_context_reference_guard_never_calls_external_boundaries(reference: str):
    lookup = RecordingBoundary()
    update_call = RecordingBoundary()
    callback = AsyncRecordingBoundary()
    context = _context()

    with (
        patch("call_helpers.NegotiationDBService.get_load_by_reference", new=lookup),
        patch("call_helpers.update_call_load", new=update_call),
    ):
        await get_load_context(
            "get_load_context", "tool-1", {"load_id": reference},
            None, context, callback,
        )

    result = json.loads(callback.calls[0]["args"][0])
    assert result["status"] == "error"
    assert "reference number" in result["message"].lower()
    assert lookup.calls == []
    assert update_call.calls == []
    assert context.messages[0]["content"] == "greeting prompt"


@pytest.mark.asyncio
async def test_end_call_real_handler_sets_reason_and_queues_end_frame():
    callback = AsyncRecordingBoundary()
    queue_frames = AsyncRecordingBoundary()
    task = SimpleNamespace(queue_frames=queue_frames)
    context = _context()

    await end_call(
        "end_call", "tool-1", {"reason": "agreement"},
        None, context, callback, task=task,
    )

    result = json.loads(callback.calls[0]["args"][0])
    assert result["status"] == "success"
    assert context.end_reason == "agreement"
    frames = queue_frames.calls[0]["args"][0]
    assert len(frames) == 1 and isinstance(frames[0], EndFrame)


@pytest.mark.asyncio
async def test_end_call_real_handler_rejects_invalid_reason_without_ending():
    callback = AsyncRecordingBoundary()
    queue_frames = AsyncRecordingBoundary()
    task = SimpleNamespace(queue_frames=queue_frames)
    context = _context()

    await end_call(
        "end_call", "tool-1", {"reason": "transfer"},
        None, context, callback, task=task,
    )

    assert json.loads(callback.calls[0]["args"][0])["status"] == "error"
    assert not hasattr(context, "end_reason")
    assert queue_frames.calls == []
