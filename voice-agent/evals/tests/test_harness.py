from __future__ import annotations

import copy
import socket
from pathlib import Path

from evals.harness.boundary_patcher import UnexpectedExternalAccess, block_network
from evals.harness.runner import discover_scripts, run_script
from evals.harness.tool_parity import assert_harness_parity, production_tool_schemas
from evals.mocks.recording import RecordingBoundary


VOICE_ROOT = Path(__file__).resolve().parents[2]


def test_tool_surface_matches_bot():
    schemas = production_tool_schemas(VOICE_ROOT)
    assert_harness_parity(VOICE_ROOT, schemas)
    assert [schema["name"] for schema in schemas["room1"]] == [
        "verify_carrier", "get_load_context", "record_agreement",
        "end_call", "transfer_to_human",
    ]


def test_good_and_bad_scripts_assess_graders_correctly():
    results = [run_script(path) for path in discover_scripts()]
    by_id = {result.script: result for result in results}
    assert by_id["above_ceiling_correct"].harness_passed
    assert set(by_id["above_ceiling_regular_agreement"].failed_assertions) == {
        "above_ceiling_classification", "no_regular_agreement_above_ceiling",
    }
    assert by_id["above_ceiling_spoken_offer"].failed_assertions == [
        "spoken_offer_not_above_ceiling"
    ]


def test_trials_are_isolated():
    path = next(path for path in discover_scripts() if path.stem == "above_ceiling")
    first = run_script(path)
    first.final_state["identity_status"] = "contaminated"
    first.final_state.setdefault("tool_history", []).append({"name": "leak"})
    second = run_script(path)
    assert second.initial_state["identity_status"] == "confirmed"
    assert second.final_state["identity_status"] == "confirmed"
    assert all(call.get("name") != "leak" for call in second.final_state["tool_history"])
    assert second.initial_state is not second.final_state
    assert second.initial_state == copy.deepcopy(second.initial_state)


def test_offline_network_access_fails_closed():
    with block_network():
        try:
            socket.create_connection(("example.com", 443))
        except UnexpectedExternalAccess as error:
            assert "Network access is disabled" in str(error)
        else:
            raise AssertionError("Network operation was not blocked")


def test_external_boundary_fakes_do_not_share_recorded_calls():
    first = RecordingBoundary({"ok": True})
    second = RecordingBoundary({"ok": True})
    assert first("load-1", price=1800) == {"ok": True}
    assert first.calls == [{"args": ["load-1"], "kwargs": {"price": 1800}}]
    assert second.calls == []
