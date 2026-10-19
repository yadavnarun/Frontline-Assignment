from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from tool_definitions import (
    END_CALL_FUNCTION,
    GET_LOAD_CONTEXT_FUNCTION,
    RECORD_AGREEMENT_FUNCTION,
    TRANSFER_HUMAN_TO_CARRIER_FUNCTION,
    TRANSFER_TO_HUMAN_FUNCTION,
    VERIFY_CARRIER_FUNCTION,
)


ROOM1_BY_SYMBOL = {
    "VERIFY_CARRIER_FUNCTION": VERIFY_CARRIER_FUNCTION,
    "GET_LOAD_CONTEXT_FUNCTION": GET_LOAD_CONTEXT_FUNCTION,
    "RECORD_AGREEMENT_FUNCTION": RECORD_AGREEMENT_FUNCTION,
    "END_CALL_FUNCTION": END_CALL_FUNCTION,
    "TRANSFER_TO_HUMAN_FUNCTION": TRANSFER_TO_HUMAN_FUNCTION,
}
ROOM2_BY_SYMBOL = {
    "TRANSFER_HUMAN_TO_CARRIER_FUNCTION": TRANSFER_HUMAN_TO_CARRIER_FUNCTION,
}


def normalize_schema(schema: Any) -> dict[str, Any]:
    return json.loads(json.dumps(schema.to_default_dict(), sort_keys=True))


def _assigned_symbols(path: Path, variable: str) -> list[str]:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == variable for target in node.targets):
            continue
        if isinstance(node.value, ast.List):
            return [item.id for item in node.value.elts if isinstance(item, ast.Name)]
    raise AssertionError(f"Could not find list assignment {variable!r} in {path}")


def production_tool_schemas(voice_root: Path) -> dict[str, list[dict[str, Any]]]:
    room1_symbols = _assigned_symbols(voice_root / "bot.py", "standard_tools")
    unknown = set(room1_symbols) - set(ROOM1_BY_SYMBOL)
    if unknown:
        raise AssertionError(f"Unknown Room 1 production tool symbols: {sorted(unknown)}")

    # Room 2 is a module-level ToolsSchema rather than a plain list. Its single
    # production symbol is asserted against the source so drift is visible.
    room2_source = (voice_root / "context_builder.py").read_text()
    room2_symbols = [name for name in ROOM2_BY_SYMBOL if name in room2_source]
    if room2_symbols != list(ROOM2_BY_SYMBOL):
        raise AssertionError("Room 2 production tool surface changed")

    return {
        "room1": [normalize_schema(ROOM1_BY_SYMBOL[name]) for name in room1_symbols],
        "room2": [normalize_schema(ROOM2_BY_SYMBOL[name]) for name in room2_symbols],
    }


def assert_harness_parity(voice_root: Path, exposed: dict[str, list[dict[str, Any]]]) -> None:
    production = production_tool_schemas(voice_root)
    if exposed != production:
        raise AssertionError(
            "Evaluation tool surface differs from production:\n"
            f"production={json.dumps(production, sort_keys=True)}\n"
            f"evaluation={json.dumps(exposed, sort_keys=True)}"
        )
