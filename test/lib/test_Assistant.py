from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.Assistant import Assistant
from src.lib.ActionManager import ActionManager
from src.lib.Event import ConversationEvent, ExternalEvent, GameEvent, PluginEvent, ProjectedEvent, StatusEvent, ToolEvent
from src.lib.Logger import ModelUsageStats, PromptUsageStats
from openai.types.chat import ChatCompletionMessageFunctionToolCall


def make_assistant(events):
    assistant = Assistant.__new__(Assistant)
    assistant.config = {
        "game_actions_var": True,
        "web_search_actions_var": True,
        "ui_actions_var": True,
        "use_action_cache_var": False,
    }
    assistant.event_manager = MagicMock()
    assistant.event_manager.get_short_term_memory.return_value = list(reversed(events))
    assistant.event_manager.get_latest_memories.return_value = []
    assistant.action_manager = ActionManager()
    assistant.action_manager.registerAction("testAction", "Test", {}, lambda args, states: "done", "global")
    assistant.prompt_generator = MagicMock()
    assistant.prompt_generator.generate_prompt.return_value = ([{"role": "user", "content": "context"}], PromptUsageStats())
    assistant.llmModel = MagicMock()
    assistant.llmModel.generate.return_value = (None, None, ModelUsageStats())
    assistant.tts = MagicMock()
    return assistant


@pytest.mark.parametrize("event", [
    GameEvent(content={"event": "FSDJump", "timestamp": ""}, historic=False),
    StatusEvent(status={"event": "InDanger"}),
    ProjectedEvent(content={"event": "Idle"}),
    ExternalEvent(content={"event": "ExternalMessage"}),
    PluginEvent(plugin_event_name="EdCoPilotEvent", plugin_event_content={"text": "hello"}),
])
def test_event_replies_do_not_offer_tools_even_with_older_user_history(event):
    event.responded_at = None
    assistant = make_assistant([
        ConversationEvent(kind="user", content="earlier request", responded_at=1),
        ToolEvent(request=[], results=[], responded_at=1),
        event,
    ])

    assistant.reply_thread({})

    assert assistant.llmModel.generate.call_args.kwargs["tools"] == []


@pytest.mark.parametrize("event", [
    ConversationEvent(kind="user", content="do something", responded_at=None),
    ToolEvent(request=[], results=[], responded_at=None),
])
def test_user_requests_and_tool_followups_offer_enabled_tools(event):
    assistant = make_assistant([event])

    assistant.reply_thread({})

    assert [tool["function"]["name"] for tool in assistant.llmModel.generate.call_args.kwargs["tools"]] == ["testAction"]


def test_unavailable_model_tool_call_is_not_executed_or_turned_into_a_followup():
    assistant = make_assistant([])
    action = ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function", function={"name": "testAction", "arguments": "{}"},
    )
    assistant.action_manager.runAction = MagicMock()

    assistant.execute_actions([action], {}, available_tools=[])

    assistant.action_manager.runAction.assert_not_called()
    assistant.event_manager.add_tool_call.assert_not_called()
    assistant.tts.say.assert_not_called()


@pytest.mark.parametrize("source", ["llm", "cache", "ui"])
def test_available_tool_execution_preserves_telemetry_source(monkeypatch, source):
    assistant = make_assistant([])
    report = MagicMock()
    monkeypatch.setattr("src.lib.ActionManager.log_tool_usage", report)
    action = ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function", function={"name": "testAction", "arguments": "{}"},
    )
    available_tools = assistant.action_manager.getToolsList("mainship", True, False, False)

    assistant.execute_actions([action], {}, available_tools=available_tools, source=source)

    report.assert_called_once()
    assert report.call_args.kwargs["source"] == source
    assert report.call_args.kwargs["status"] == "success"
    assistant.event_manager.add_tool_call.assert_called_once()


@pytest.mark.parametrize("action_type,toggle", [
    ("global", "game_actions_var"),
    ("web", "web_search_actions_var"),
    ("ui", "ui_actions_var"),
])
def test_toggle_disabled_during_model_request_prevents_execution(action_type, toggle):
    assistant = make_assistant([ConversationEvent(kind="user", content="do something", responded_at=None)])
    method = MagicMock(return_value="done")
    assistant.action_manager.registerAction("testAction", "Test", {}, method, action_type)
    action = ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function", function={"name": "testAction", "arguments": "{}"},
    )

    def generate(**kwargs):
        assert [tool["function"]["name"] for tool in kwargs["tools"]] == ["testAction"]
        assistant.config = {**assistant.config, toggle: False}
        return None, [action], ModelUsageStats()

    assistant.llmModel.generate.side_effect = generate

    assistant.reply_thread({})

    method.assert_not_called()
    assistant.event_manager.add_tool_call.assert_not_called()
