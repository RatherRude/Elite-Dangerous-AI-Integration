import json
from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.ActionManager import ActionManager


@pytest.fixture(autouse=True)
def reset_actions() -> Generator[None, None, None]:
    original_actions = ActionManager.actions
    ActionManager.actions = {}
    try:
        yield
    finally:
        ActionManager.actions = original_actions


def make_tool_call(name: str, arguments: dict | None = None) -> ChatCompletionMessageFunctionToolCall:
    return ChatCompletionMessageFunctionToolCall(
        type="function",
        id="call_test",
        function={
            "name": name,
            "arguments": json.dumps(arguments or {}),
        },
    )


def test_run_action_returns_existing_final_result_shape() -> None:
    manager = ActionManager()

    def action(args: dict, projected_states: dict) -> str:
        return f"done {args['value']}"

    manager.registerAction("testAction", "Test action", {}, action)

    result = manager.runAction(make_tool_call("testAction", {"value": 42}), {})

    assert result == {
        "tool_call_id": "call_test",
        "role": "tool",
        "name": "testAction",
        "content": "done 42",
    }


def test_run_action_emits_processing_results_from_iterator() -> None:
    manager = ActionManager()
    processing_results: list[tuple[str, str, object]] = []

    def action(args: dict, projected_states: dict):
        yield "starting"
        yield {"status": "working"}
        return "finished"

    manager.registerAction("testAction", "Test action", {}, action)

    result = manager.runAction(
        make_tool_call("testAction"),
        {},
        processing_callback=lambda tool_call_id, name, content: processing_results.append((tool_call_id, name, content)),
    )

    assert processing_results == [
        ("call_test", "testAction", "starting"),
        ("call_test", "testAction", {"status": "working"}),
    ]
    assert result == {
        "tool_call_id": "call_test",
        "role": "tool",
        "name": "testAction",
        "content": "finished",
    }


def test_run_action_iterator_exception_returns_error_result() -> None:
    manager = ActionManager()
    processing_results: list[tuple[str, str, object]] = []

    def action(args: dict, projected_states: dict):
        yield "starting"
        raise ValueError("failed")

    manager.registerAction("testAction", "Test action", {}, action)

    result = manager.runAction(
        make_tool_call("testAction"),
        {},
        processing_callback=lambda tool_call_id, name, content: processing_results.append((tool_call_id, name, content)),
    )

    assert processing_results == [("call_test", "testAction", "starting")]
    assert result["tool_call_id"] == "call_test"
    assert result["role"] == "tool"
    assert result["name"] == "testAction"
    assert str(result["content"]).startswith("ERROR: ValueError")
