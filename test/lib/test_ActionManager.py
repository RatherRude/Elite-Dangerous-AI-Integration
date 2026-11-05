import json
from pathlib import Path
import sys

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.ActionManager import ActionManager
from src.lib.actions import action_language_packs
from src.lib.actions.action_language_packs import load_action_language_packs


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


def test_selected_language_aliases_are_applied_and_removed() -> None:
    manager = ActionManager()

    class MemoryCache:
        def __init__(self) -> None:
            self.values: dict[str, object] = {}

        def get(self, key: str, default: object = None) -> object:
            return self.values.get(key, default)

        def set(self, key: str, value: object) -> None:
            self.values[key] = value

        def delete(self, key: str) -> None:
            self.values.pop(key, None)

    manager.action_cache = MemoryCache()  # type: ignore[assignment]
    manager.registerAction(
        "FsdJump",
        "Enter supercruise",
        {"type": "object", "properties": {}},
        lambda args, states: "started",
        cache_prefill={"supercruise": {"jump_type": "supercruise"}},
    )
    manager.registerAction(
        "target_next_system_in_route",
        "Target the next system in route",
        {"type": "object", "properties": {}},
        lambda args, states: "targeted",
        cache_prefill={"continue route": {}},
    )
    manager.registerAction(
        "nightVisionToggle",
        "Toggle night vision",
        {"type": "object", "properties": {}},
        lambda args, states: "toggled",
        action_type="ship",
        cache_prefill={"night vision": {}},
    )
    tools = manager.getToolsList("mainship", True, False, False)

    manager.apply_language_aliases(load_action_language_packs(), ["fr"])
    expected_aliases = {
        "vitesse de croisière": ("FsdJump", {"jump_type": "supercruise"}),
        "passer en vitesse de croisière": ("FsdJump", {"jump_type": "supercruise"}),
        "continue la route": ("target_next_system_in_route", {}),
        "continue la navigation": ("target_next_system_in_route", {}),
        "vision nocturne": ("nightVisionToggle", {}),
        "active la vision nocturne": ("nightVisionToggle", {}),
        "désactive la vision nocturne": ("nightVisionToggle", {}),
    }
    for phrase, (action_name, arguments) in expected_aliases.items():
        prediction = manager.predict_action(phrase, tools)
        assert prediction is not None
        assert prediction[0].function.name == action_name
        assert json.loads(prediction[0].function.arguments) == arguments

    manager.apply_language_aliases(load_action_language_packs(), [])

    for phrase in expected_aliases:
        assert manager.predict_action(phrase, tools) is None
    assert manager.predict_action("supercruise", tools) is not None
    assert manager.predict_action("continue route", tools) is not None
    assert manager.predict_action("night vision", tools) is not None


@pytest.mark.parametrize("phrases", [None, "command", [], [""], ["   "], ["valid", 42]])
def test_language_pack_rejects_invalid_phrases(
    phrases: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = {
        "name": "Test",
        "aliases": [{"phrases": phrases, "action": "FsdJump", "arguments": {}}],
    }
    (tmp_path / "test.json").write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(action_language_packs, "LANGUAGE_PACKS_DIRECTORY", tmp_path)

    with pytest.raises(ValueError, match="Invalid action alias"):
        load_action_language_packs()


def test_language_alias_cannot_override_an_english_command() -> None:
    manager = ActionManager()
    manager.registerAction(
        "FsdJump",
        "Enter supercruise",
        {"type": "object", "properties": {}},
        lambda args, states: "started",
        cache_prefill={"supercruise": {"jump_type": "supercruise"}},
    )

    with pytest.raises(ValueError, match="conflicts with an English command"):
        manager.apply_language_aliases(
            {
                "fr": {
                    "aliases": [{
                        "phrase": "supercruise",
                        "action": "FsdJump",
                        "arguments": {"jump_type": "next_system"},
                    }]
                }
            },
            ["fr"],
        )


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


def test_action_registrations_do_not_leak_between_sessions() -> None:
    first_session = ActionManager()
    first_session.registerAction("pluginAction", "Plugin action", {}, lambda args, states: "done")

    second_session = ActionManager()

    assert second_session.getToolsList("ship", True, True, True) == []
    assert "ERROR" in second_session.runAction(make_tool_call("pluginAction"), {})["content"]


@pytest.mark.parametrize("action_type", ["ship", "global", "web", "ui"])
def test_category_toggles_remove_tools_from_model_list(action_type: str) -> None:
    manager = ActionManager()
    manager.registerAction("testAction", "Test", {}, lambda args, states: "done", action_type)
    enabled_category = {"ship": 0, "global": 0, "web": 1, "ui": 2}[action_type]
    toggles = [False, False, False]

    assert manager.getToolsList("mainship", *toggles) == []
    toggles[enabled_category] = True
    assert [tool["function"]["name"] for tool in manager.getToolsList("mainship", *toggles)] == ["testAction"]
    toggles[enabled_category] = False
    assert manager.getToolsList("mainship", *toggles) == []


def test_dynamic_plugin_toggle_hides_and_prevents_execution() -> None:
    manager = ActionManager()
    settings = {"actions": True}
    calls = []
    manager.registerAction(
        "pluginAction", "Plugin action", {}, lambda args, states: calls.append(args),
        action_type="global", is_enabled=lambda: settings["actions"],
    )

    assert len(manager.getToolsList("mainship", True, False, False)) == 1
    settings["actions"] = False

    assert manager.getToolsList("mainship", True, False, False) == []
    assert "disabled" in manager.runAction(make_tool_call("pluginAction"), {})["content"]
    assert calls == []
