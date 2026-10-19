from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from call_helpers import record_agreement


@pytest.mark.asyncio
async def test_known_gap_retry_submits_a_second_quote():
    """Characterize the current lack of quote idempotency without changing it."""
    context = SimpleNamespace(
        load_uuid="EVAL-1001",
        call_id=UUID("00000000-0000-4000-8000-000000000010"),
        load_context={"load_id": "EVAL-1001", "maxRate": 2000},
        caller_mc="123456",
        caller_phone="+12025550199",
    )
    callback = AsyncMock()
    arguments = {
        "agreed_price": 1800,
        "carrier_contact_name": "Sam",
        "carrier_contact_phone": "+12025550199",
    }

    with (
        patch(
            "call_helpers.NegotiationDBService.create_negotiation",
            side_effect=[
                {"id": "00000000-0000-4000-8000-000000000011"},
                {"id": "00000000-0000-4000-8000-000000000012"},
            ],
        ) as create_negotiation,
        patch("call_helpers.link_negotiation_to_call") as link_negotiation,
        patch("call_helpers.NegotiationDBService.notify_carrier_quote") as quote,
    ):
        for index in range(2):
            await record_agreement(
                "record_agreement", f"tool-{index}", arguments, None, context, callback
            )

    assert create_negotiation.call_count == 2
    assert link_negotiation.call_count == 2
    assert quote.call_count == 2
    assert callback.await_count == 2
    assert all(json.loads(call.args[0])["status"] == "success" for call in callback.await_args_list)
