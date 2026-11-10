from pathlib import Path
import sys
from unittest.mock import MagicMock, call

import pytest
import pysqlite3 as sqlite3

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.Assistant import Assistant
from src.lib.ActionManager import ActionManager
from src.lib.Event import ConversationEvent, ExternalEvent, GameEvent, PluginEvent, ProjectedEvent, StatusEvent, ToolEvent
from src.lib.Logger import ModelUsageStats, PromptUsageStats
from src.lib.Models import LLMError, LLMModel, LLMResponse
from openai.types.chat import ChatCompletionMessageFunctionToolCall


class LegacyLLMModel(LLMModel):
    def generate(self, messages, tools=None, tool_choice=None):
        return None, None, ModelUsageStats()


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    connection = sqlite3.connect(":memory:")
    monkeypatch.setattr("src.lib.Database.get_connection", lambda: connection)
    try:
        yield
    finally:
        connection.close()


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
    assistant.llmModel = LegacyLLMModel("legacy")
    assistant.llmModel.generate = MagicMock(return_value=(None, None, ModelUsageStats()))
    assistant.tts = MagicMock()
    assistant._get_tts_postprocessing_layers = MagicMock(return_value=[])
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


@pytest.mark.parametrize("response,expected", [
    ("A: hi\nB: hello\nA: ready?", [("A", "hi"), ("B", "hello"), ("A", "ready?")]),
    ("Plain reply", [(None, "Plain reply")]),
])
def test_reply_saves_separate_character_events(response, expected):
    assistant = make_assistant([
        ConversationEvent(kind="user", content="hello", processed_at=12.0, responded_at=None),
    ])
    assistant.config["characters"] = [{"name": "A"}, {"name": "B"}]
    assistant.llmModel.generate.return_value = (response, None, ModelUsageStats())
    assistant._get_tts_postprocessing_layers = MagicMock(return_value=[])

    assistant.reply_thread({})

    assert assistant.event_manager.add_conversation_event.call_args_list == [
        call("assistant", text, reasons=["user"], processed_at=12.0, character_name=name)
        for name, text in expected
    ]
    assert [speech.args for speech in assistant.tts.say.call_args_list] == [(text,) for _, text in expected]
    for speech in assistant.tts.say.call_args_list:
        assert speech.kwargs["on_start"] == assistant.event_manager.add_assistant_speaking
        assert speech.kwargs["on_complete"] == assistant.event_manager.add_assistant_complete_event


def test_streamed_responses_are_handled_before_requesting_the_next_output():
    event = ConversationEvent(kind="user", content="hello", responded_at=None)
    assistant = make_assistant([event])
    assistant.config["characters"] = [{"name": "A"}, {"name": "B"}]
    action = ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function", function={"name": "testAction", "arguments": "{}"},
    )
    assistant.execute_actions = MagicMock()

    def stream(**kwargs):
        assert kwargs["events"] == [event]
        assert kwargs["characters"] == assistant.config["characters"]
        assert kwargs["prompt_generator"] is assistant.prompt_generator
        yield LLMResponse(character_name="A", text="hi")
        assistant.event_manager.add_conversation_event.assert_called_once()
        assistant.tts.say.assert_called_once()
        assistant.tts.say.return_value.wait_for_completion.assert_not_called()
        yield LLMResponse(tool_calls=[action])
        assistant.execute_actions.assert_called_once()
        yield LLMResponse(character_name="B", text="Provider: already parsed")
        assert assistant.event_manager.add_conversation_event.call_count == 2
        assistant.tts.say.return_value.wait_for_completion.assert_not_called()

    assistant.llmModel.generate_multi_character = MagicMock(side_effect=stream)

    assistant.reply_thread({})

    assistant.llmModel.generate.assert_not_called()
    assistant.prompt_generator.generate_prompt.assert_not_called()
    assert assistant.event_manager.add_conversation_event.call_args_list[-1].args == ("assistant", "Provider: already parsed")
    assert assistant.tts.say.return_value.wait_for_completion.call_count == 2
    assert assistant.is_replying is False


def test_reply_preserves_text_yielded_alongside_tool_calls():
    assistant = make_assistant([ConversationEvent(kind="user", content="do something", responded_at=None)])
    action = ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function", function={"name": "testAction", "arguments": "{}"},
    )
    assistant.llmModel.generate_multi_character = MagicMock(return_value=iter([
        LLMResponse(character_name="A", text="Working on it", tool_calls=[action]),
    ]))
    assistant.execute_actions = MagicMock()

    assistant.reply_thread({})

    assistant.event_manager.add_conversation_event.assert_called_once()
    assistant.execute_actions.assert_called_once()


def test_stream_error_keeps_utterances_and_waits_for_queued_speech(monkeypatch):
    assistant = make_assistant([])
    show_error = MagicMock()
    monkeypatch.setattr("src.lib.Assistant.show_chat_message", show_error)

    def stream(**kwargs):
        yield LLMResponse(character_name="A", text="hi")
        raise LLMError("Stream failed")

    assistant.llmModel.generate_multi_character = MagicMock(side_effect=stream)

    assistant.reply_thread({})

    assistant.event_manager.add_conversation_event.assert_called_once()
    assistant.tts.say.return_value.wait_for_completion.assert_called_once()
    show_error.assert_called_once_with("error", "LLM Error:", "Stream failed")
    assert assistant.is_replying is False


def test_cached_action_does_not_generate_a_prompt_or_call_the_model():
    assistant = make_assistant([ConversationEvent(kind="user", content="do something", responded_at=None)])
    action = ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function", function={"name": "testAction", "arguments": "{}"},
    )
    assistant.config["use_action_cache_var"] = True
    assistant.action_manager.predict_action = MagicMock(return_value=[action])
    assistant.llmModel.generate_multi_character = MagicMock()
    assistant.execute_actions = MagicMock()

    assistant.reply_thread({})

    assistant.llmModel.generate_multi_character.assert_not_called()
    assistant.llmModel.generate.assert_not_called()
    assistant.prompt_generator.generate_prompt.assert_not_called()
    assistant.execute_actions.assert_called_once()


def test_action_verification_uses_multi_character_generation():
    assistant = make_assistant([])
    action = ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function", function={"name": "testAction", "arguments": "{}"},
    )
    assistant.action_manager.has_action_in_cache = MagicMock(return_value=True)
    assistant.action_manager.confirm_action_in_cache = MagicMock()
    assistant.llmModel.generate_multi_character = MagicMock(return_value=iter([
        LLMResponse(tool_calls=[action]),
        LLMResponse(model_usage=ModelUsageStats()),
    ]))

    assistant.verify_action("do something", action, [], {})

    assistant.llmModel.generate.assert_not_called()
    assistant.action_manager.confirm_action_in_cache.assert_called_once_with("do something", action, [])


def test_usage_is_not_counted_once_per_character(monkeypatch):
    assistant = make_assistant([])
    assistant.config["characters"] = [{"name": "A"}, {"name": "B"}]
    usage = ModelUsageStats(input_tokens=20, output_tokens=10)
    assistant.llmModel.generate.return_value = ("A: hi\nB: hello\nA: ready?", None, usage)
    log_usage = MagicMock()
    monkeypatch.setattr("src.lib.Assistant.log_llm_usage", log_usage)

    assistant.reply_thread({})

    assert assistant.event_manager.add_conversation_event.call_count == 3
    log_usage.assert_called_once_with(
        "assistant", model_usage=usage,
        prompt_usage=assistant.prompt_generator.generate_prompt.return_value[1],
        llm_model=assistant.llmModel,
    )


def test_streamed_tool_batches_recheck_permissions():
    assistant = make_assistant([ConversationEvent(kind="user", content="do something", responded_at=None)])
    action = ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function", function={"name": "testAction", "arguments": "{}"},
    )
    method = MagicMock(return_value="done")
    assistant.action_manager.registerAction("testAction", "Test", {}, method, "global")

    def stream(**kwargs):
        yield LLMResponse(tool_calls=[action])
        method.assert_called_once()
        assistant.config["game_actions_var"] = False
        yield LLMResponse(tool_calls=[action])

    assistant.llmModel.generate_multi_character = MagicMock(side_effect=stream)

    assistant.reply_thread({})

    method.assert_called_once()
    assistant.event_manager.add_tool_call.assert_called_once()
