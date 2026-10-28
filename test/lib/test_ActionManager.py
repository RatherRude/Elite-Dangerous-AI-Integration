import json
from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from unittest.mock import MagicMock
from openai.types.chat import ChatCompletionMessageFunctionToolCall

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.ActionManager import ActionManager


@pytest.fixture(autouse=True)
def reset_actions(monkeypatch) -> Generator[None, None, None]:
    # These tests exercise dispatch, not the persistent action cache.
    monkeypatch.setattr("src.lib.ActionManager.KeyValueStore", lambda _: MagicMock())
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


@pytest.mark.parametrize(
    ("allowed_actions", "is_registered"),
    [
        ({}, False),
        ({"testPermission": False}, False),
        ({"testPermission": True}, True),
    ],
)
def test_registration_requires_explicitly_enabled_permission(
    allowed_actions: dict[str, bool],
    is_registered: bool,
) -> None:
    manager = ActionManager()
    manager.set_allowed_actions(allowed_actions)

    manager.registerAction(
        "testAction",
        "Test action",
        {},
        lambda args, states: "done",
        permission="testPermission",
    )

    assert ("testAction" in manager.actions) is is_registered


def test_tool_list_requires_explicitly_enabled_permission() -> None:
    manager = ActionManager()
    manager.set_allowed_actions({
        "enabledPermission": True,
        "disabledPermission": True,
        "missingPermission": True,
    })

    for action_name, permission in [
        ("enabledAction", "enabledPermission"),
        ("disabledAction", "disabledPermission"),
        ("missingAction", "missingPermission"),
    ]:
        manager.registerAction(
            action_name,
            "Test action",
            {},
            lambda args, states: "done",
            permission=permission,
        )

    tools = manager.getToolsList(
        "ship",
        True,
        False,
        False,
        {
            "enabledPermission": True,
            "disabledPermission": False,
        },
    )

    assert [tool["function"]["name"] for tool in tools] == ["enabledAction"]


def test_permissionless_actions_remain_available() -> None:
    manager = ActionManager()
    manager.set_allowed_actions({})
    manager.registerAction(
        "permissionlessAction",
        "Test action",
        {},
        lambda args, states: "done",
    )

    tools = manager.getToolsList("ship", True, False, False, {})

    assert [tool["function"]["name"] for tool in tools] == [
        "permissionlessAction"
    ]


def test_station_actions_require_docked_status() -> None:
    manager = ActionManager()
    manager.registerAction(
        "stationAction",
        "Test station action",
        {},
        lambda args, states: "done",
        action_type="in_station",
    )

    undocked_tools = manager.getToolsList("mainship", True, False, False)
    docked_tools = manager.getToolsList("mainship", True, False, False, in_station=True)
    fighter_tools = manager.getToolsList("fighter", True, False, False, in_station=True)

    assert undocked_tools == []
    assert [tool["function"]["name"] for tool in docked_tools] == ["stationAction"]
    assert fighter_tools == []


@pytest.mark.parametrize("source", ["llm", "cache", "ui"])
def test_outcome_is_emitted_once_after_generator_failure(monkeypatch, source):
    from src.lib.Errors import ToolError
    report = MagicMock()
    monkeypatch.setattr("src.lib.ActionManager.log_tool_usage", report)
    manager = ActionManager()
    def action(args, states):
        yield "working"
        raise ToolError("private arguments", kind="rate_limit")
    manager.registerAction("testAction", "Test", {}, action)
    result = manager.runAction(make_tool_call("testAction"), {}, source=source)
    assert result["content"].startswith("ERROR:")
    report.assert_called_once()
    assert report.call_args.kwargs["error_kind"] == "rate_limit"
    assert report.call_args.kwargs["source"] == source
    assert report.call_args.kwargs["duration_ms"] >= 0
    assert "private" not in str(report.call_args)


def test_error_text_is_not_a_failure_and_telemetry_failure_does_not_change_result(monkeypatch):
    manager = ActionManager()
    manager.registerAction("testAction", "Test", {}, lambda args, states: "ERROR is just text")
    report = MagicMock(side_effect=RuntimeError("export failed"))
    monkeypatch.setattr("src.lib.ActionManager.log_tool_usage", report)
    assert manager.runAction(make_tool_call("testAction"), {})["content"] == "ERROR is just text"
    assert report.call_args.kwargs["status"] == "success"


def test_unknown_and_malformed_actions_have_no_execution_duration(monkeypatch):
    report = MagicMock()
    monkeypatch.setattr("src.lib.ActionManager.log_tool_usage", report)
    manager = ActionManager()
    manager.runAction(make_tool_call("private-tool-name"), {})
    assert report.call_args.kwargs["tool_name"] == "private-tool-name"
    assert report.call_args.kwargs["error_kind"] == "unknown_tool"
    manager.registerAction("testAction", "Test", {}, lambda args, states: "done")
    call = make_tool_call("testAction")
    call.function.arguments = "{"
    manager.runAction(call, {})
    assert report.call_args.kwargs["error_kind"] == "invalid_arguments"
    assert report.call_args.kwargs["duration_ms"] is None
