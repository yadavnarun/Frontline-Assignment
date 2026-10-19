from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from call_helpers import record_agreement
from transfer_tool_handler import TransferToolHandler


def _agreement_context():
    return SimpleNamespace(
        load_uuid="EVAL-1001",
        call_id=UUID("00000000-0000-4000-8000-000000000010"),
        load_context={"load_id": "EVAL-1001", "maxRate": 2000},
        caller_mc="123456",
        caller_phone="+12025550199",
    )


@pytest.mark.asyncio
async def test_known_gap_backend_accepts_regular_agreement_above_ceiling():
    context = _agreement_context()
    callback = AsyncMock()
    with (
        patch("call_helpers.NegotiationDBService.create_negotiation", return_value={
            "id": "00000000-0000-4000-8000-000000000011"
        }),
        patch("call_helpers.link_negotiation_to_call"),
        patch("call_helpers.NegotiationDBService.notify_carrier_quote") as quote,
    ):
        await record_agreement(
            "record_agreement", "tool-1", {"agreed_price": 2300},
            None, context, callback,
        )

    result = json.loads(callback.await_args.args[0])
    assert result["status"] == "success"
    quote.assert_called_once()


@pytest.mark.asyncio
async def test_known_gap_regular_agreement_does_not_require_contact_name():
    context = _agreement_context()
    callback = AsyncMock()
    with (
        patch("call_helpers.NegotiationDBService.create_negotiation", return_value={
            "id": "00000000-0000-4000-8000-000000000011"
        }),
        patch("call_helpers.link_negotiation_to_call"),
        patch("call_helpers.NegotiationDBService.notify_carrier_quote"),
    ):
        await record_agreement(
            "record_agreement", "tool-1", {"agreed_price": 1800},
            None, context, callback,
        )

    assert json.loads(callback.await_args.args[0])["status"] == "success"


@pytest.mark.asyncio
async def test_known_gap_transfer_does_not_require_confirmed_carrier():
    orchestrator = MagicMock()
    speech_sync = MagicMock()
    speech_sync.schedule_after_speech = AsyncMock()
    handler = TransferToolHandler(
        orchestrator=orchestrator,
        http_session=MagicMock(), stt=MagicMock(), tts=MagicMock(),
        llm=MagicMock(), skip_tts_processor=MagicMock(), transcript=MagicMock(),
        speech_sync=speech_sync, audiobuffer=MagicMock(), context_aggregator=MagicMock(),
    )
    # Deliberately no caller_mc, carrier_name, or confirmation flag.
    context = SimpleNamespace(load_uuid="EVAL-1001")
    callback = AsyncMock()
    with patch("transfer_tool_handler.NegotiationDBService.get_load", return_value={
        "load_number": "EVAL-1001",
        "carrier_sales_rep_phone": "+12025550101",
    }):
        await handler.handle_transfer_to_human(
            "transfer_to_human", "tool-1",
            {"reason": "requested", "load_number": "EVAL-1001"},
            None, context, callback,
        )

    assert json.loads(callback.await_args.args[0])["status"] == "transferring"
    orchestrator.set_transfer_metadata.assert_called_once()
