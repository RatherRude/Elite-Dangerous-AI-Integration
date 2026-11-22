from pathlib import Path
import sys
from threading import Event as ThreadEvent, RLock
from unittest.mock import MagicMock

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.Assistant import Assistant
from src.lib.ActionManager import ActionManager
from src.lib.Event import ConversationEvent, ExternalEvent, GameEvent, PluginEvent, ProjectedEvent, StatusEvent, ToolEvent
from src.lib.Logger import ModelUsageStats, PromptUsageStats
from src.lib.Models import LLMResponse
from src.lib.CharacterManager import CharacterManager
from src.lib.PluginBase import PluginBase, PluginManifest
from src.lib.PluginHelper import PluginHelper
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
    assistant._turn_lock = RLock()
    assistant._generation = assistant._last_reset = 0
    assistant.is_replying = False
    assistant.reply_pending = bool(events)
    assistant.pending = list(events)
    assistant.disabled_game_events = []
    assistant.enabled_game_events = []
    assistant.registered_should_reply_handlers = []
    assistant.short_term_memories = []
    assistant.event_manager.get_short_term_memory.return_value = list(reversed(events))
    assistant.event_manager.get_latest_memories.return_value = []
    assistant.action_manager = ActionManager()
    assistant.action_manager.registerAction("testAction", "Test", {}, lambda args, states: "done", "global")
    assistant.prompt_generator = MagicMock()
    assistant.prompt_generator.generate_prompt.return_value = ([{"role": "user", "content": "context"}], PromptUsageStats())
    assistant.llmModel = MagicMock()
    assistant.llmModel.generate.return_value = (None, None, ModelUsageStats())
    assistant.tts = MagicMock()
    assistant.characters = CharacterManager(assistant.config)
    return assistant


def test_attributed_lines_queue_in_order_and_use_each_speakers_voice():
    assistant = make_assistant([])
    provider = 'plugin:provider:tts'
    assistant.config.update({
        'tts_provider': provider,
        'plugin_settings': {'provider': {'model': 'shared'}},
        'active_characters': [1],
        'characters': [
            {'name': 'Pilot', 'tts_voice_settings': {provider: {'voice': 'pilot'}}},
            {'name': 'Navigator', 'tts_voice_settings': {provider: {'voice': 'navigator'}}},
        ],
    })
    assistant.characters.plugin_manager = MagicMock()
    assistant.characters.plugin_manager.get_plugin_provider.return_value = {'voice_settings_config': []}
    pilot_line, navigator_line = MagicMock(), MagicMock()
    assistant.tts.say.side_effect = [pilot_line, navigator_line]

    assert assistant.queue_utterance(LLMResponse(text='Ready', character_name='Pilot')) is pilot_line
    assert assistant.queue_utterance(LLMResponse(text='Departing', character_name='Navigator')) is navigator_line
    assert not pilot_line.mock_calls and not navigator_line.mock_calls
    assistant.event_manager.add_conversation_event.assert_not_called()

    calls = assistant.tts.say.call_args_list
    assert [call.args[0] for call in calls] == ['Ready', 'Departing']
    assert [call.kwargs['voice_settings'] for call in calls] == [
        {'model': 'shared', 'voice': 'pilot'}, {'model': 'shared', 'voice': 'navigator'},
    ]
    for call in calls:
        call.kwargs['on_start']()
    history = assistant.event_manager.add_conversation_event.call_args_list
    assert [(call.args[1], call.kwargs['character_name']) for call in history] == [
        ('Ready', 'Pilot'), ('Departing', 'Navigator'),
    ]


def test_memory_summary_receives_recorded_speaker_names():
    assistant = make_assistant([])
    assistant.embeddingModel = MagicMock()
    assistant.embeddingModel.create_embedding.return_value = ('model', [])
    assistant.summarize_memory([
        ConversationEvent(kind='assistant', character_name='Pilot', content='Standing by.'),
        ConversationEvent(kind='assistant', character_name='Tower', plugin_guid='tower', content='Pad clear.'),
    ])
    transcript = assistant.llmModel.generate.call_args.kwargs['messages'][1]['content']
    assert '[Speaker: Pilot] Standing by.' in transcript
    assert '[Speaker: Tower] Pad clear.' in transcript


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


def test_replacement_starts_before_obsolete_request_releases_and_keeps_unanswered_context():
    original = ConversationEvent(kind='user', content='Original request', responded_at=None, processed_at=1)
    replacement = ConversationEvent(kind='user', content='Correction', responded_at=None, processed_at=2)
    assistant = make_assistant([original])
    assistant._process_active_quests = MagicMock()
    old_entered, release_old = ThreadEvent(), ThreadEvent()
    new_entered, release_new = ThreadEvent(), ThreadEvent()
    prompts = []

    def prompt(**kwargs):
        pending = [event.content for event in kwargs['pending_events']]
        return [{'role': 'user', 'content': pending}], PromptUsageStats()

    def generate(messages, **kwargs):
        pending = messages[0]['content']
        prompts.append(pending)
        if pending == ['Original request']:
            old_entered.set()
            assert release_old.wait(3)
            return 'Obsolete speech', None, ModelUsageStats()
        new_entered.set()
        assert release_new.wait(3)
        return 'Updated reply', None, ModelUsageStats()

    assistant.prompt_generator.generate_prompt.side_effect = prompt
    assistant.llmModel.generate.side_effect = generate
    old = assistant.reply({})
    assert old is not None
    try:
        assert old_entered.wait(3)
        assistant.interrupt_response()
        assistant.tts.abort.assert_called_once_with(preserve_retained=True)
        assert not assistant.is_replying and assistant.reply({}) is None
        assistant.event_manager.get_short_term_memory.return_value = [replacement, original]
        assistant.on_event(replacement, {})
        new = assistant.reply({})
        assert new is not None and new_entered.wait(3)
        assert assistant.reply({}) is None
        release_old.set()
        old.join(3)
        assert not old.is_alive() and assistant.is_replying
        assistant.tts.say.assert_not_called()
        assistant.event_manager.add_conversation_event.assert_not_called()
    finally:
        release_old.set()
        release_new.set()
    new.join(3)
    assert not new.is_alive() and not assistant.is_replying
    assert prompts == [['Original request'], ['Original request', 'Correction']]
    assert assistant.tts.say.call_args.args == ('Updated reply',)
    assistant.tts.say.call_args.kwargs['on_start']()
    assert assistant.event_manager.add_conversation_event.call_args.kwargs['processed_at'] == 2


def test_interruption_between_submission_and_on_start_does_not_record_or_complete_stale_line():
    assistant = make_assistant([])
    assistant.queue_model_line(LLMResponse(text='Obsolete'), reasons=['user'], processed_at=1)
    callbacks = assistant.tts.say.call_args.kwargs
    assert not callbacks['drop_if']()
    assistant.interrupt_response()
    callbacks['on_start']()
    callbacks['on_complete']()
    assert callbacks['drop_if']()
    assistant.event_manager.add_assistant_speaking.assert_not_called()
    assistant.event_manager.add_conversation_event.assert_not_called()
    assistant.event_manager.add_assistant_complete_event.assert_not_called()


@pytest.mark.parametrize('invalidate', ['interrupt_response', 'clear_conversation_state', 'reset_runtime_state'])
def test_invalidation_drops_late_model_tools(invalidate):
    request = ConversationEvent(kind='user', content='Run a test', responded_at=None)
    assistant = make_assistant([request])
    entered, release = ThreadEvent(), ThreadEvent()
    action = ChatCompletionMessageFunctionToolCall(
        id='call_test', type='function', function={'name': 'testAction', 'arguments': '{}'},
    )

    def generate(**kwargs):
        entered.set()
        assert release.wait(3)
        return None, [action], ModelUsageStats()

    assistant.action_manager.runAction = MagicMock()
    assistant.llmModel.generate.side_effect = generate
    worker = assistant.reply({})
    assert worker is not None
    try:
        assert entered.wait(3)
        getattr(assistant, invalidate)()
        assistant.tts.abort.assert_called_once_with(preserve_retained=invalidate == 'interrupt_response')
        assert not assistant.is_replying and assistant.reply({}) is None
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    assistant.action_manager.runAction.assert_not_called()
    assistant.event_manager.add_assistant_acting.assert_not_called()
    assistant.event_manager.add_tool_call.assert_not_called()


def test_tool_batch_drops_progress_and_results_from_inflight_tool_and_skips_remaining_tools():
    assistant = make_assistant([ConversationEvent(kind='user', content='Execute both', responded_at=None)])
    entered, release = ThreadEvent(), ThreadEvent()
    first, second = [ChatCompletionMessageFunctionToolCall(
        id=call_id, type='function', function={'name': 'testAction', 'arguments': '{}'},
    ) for call_id in ['first', 'second']]

    def run_action(action, states, processing_callback):
        entered.set()
        assert release.wait(3)
        processing_callback(action.id, action.function.name, 'Stale progress')
        return {'content': 'Stale result'}

    assistant.action_manager.runAction = MagicMock(side_effect=run_action)
    assistant.llmModel.generate.return_value = (None, [first, second], ModelUsageStats())
    worker = assistant.reply({})
    assert worker is not None
    try:
        assert entered.wait(3)
        assistant.interrupt_response()
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    assert [call.args[0].id for call in assistant.action_manager.runAction.call_args_list] == ['first']
    assistant.event_manager.add_assistant_acting.assert_called_once_with()
    assistant.event_manager.add_tool_processing.assert_not_called()
    assistant.event_manager.add_tool_call.assert_not_called()


def test_tool_is_not_admitted_if_interrupted_while_preparing_its_description():
    assistant = make_assistant([ConversationEvent(kind='user', content='Run a test', responded_at=None)])
    entered, release = ThreadEvent(), ThreadEvent()
    action = ChatCompletionMessageFunctionToolCall(
        id='call_test', type='function', function={'name': 'testAction', 'arguments': '{}'},
    )

    def describe(action, states):
        entered.set()
        assert release.wait(3)
        return 'Obsolete action description'

    assistant.action_manager.getActionDesc = MagicMock(side_effect=describe)
    assistant.action_manager.runAction = MagicMock()
    assistant.llmModel.generate.return_value = (None, [action], ModelUsageStats())
    worker = assistant.reply({})
    assert worker is not None
    try:
        assert entered.wait(3)
        assistant.interrupt_response()
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    assistant.tts.say.assert_not_called()
    assistant.action_manager.runAction.assert_not_called()
    assistant.event_manager.add_assistant_acting.assert_not_called()
    assistant.event_manager.add_tool_call.assert_not_called()


def test_plugin_retention_is_opt_in_and_only_interrupting_audible_lines_invalidate():
    assistant = make_assistant([ConversationEvent(kind='user', content='In progress')])
    assistant.event_manager.get_current_state.return_value = ([], {})
    helper = PluginHelper.__new__(PluginHelper)
    helper._assistant = assistant
    class CommentaryPlugin(PluginBase):
        def __init__(self):
            super().__init__(PluginManifest('{"guid":"commentary","name":"Commentary"}'))
            self.character = {'name': 'Commentary', 'avatar': 'commentary.png'}

    plugin = CommentaryPlugin()
    assistant.is_replying = True

    helper.queue_utterance(plugin, LLMResponse(text='Silent'), speak=False, interrupt=True)
    helper.queue_utterance(plugin, LLMResponse(text='Ordinary'))
    ordinary = assistant.tts.say.call_args.kwargs
    helper.queue_utterance(plugin, LLMResponse(text='Retained'), retain_on_interrupt=True)
    retained = assistant.tts.say.call_args.kwargs
    assert ordinary['retain_on_interrupt'] is False and retained['retain_on_interrupt'] is True
    assert assistant.is_replying
    assistant.tts.abort.assert_not_called()

    helper.queue_utterance(plugin, LLMResponse(text='Interrupting'), interrupt=True)
    assistant.tts.abort.assert_called_once_with(preserve_retained=True)
    assert not assistant.is_replying and assistant.reply({}) is None
    assert ordinary['drop_if']() and not retained['drop_if']()
    ordinary['on_start']()
    retained['on_start']()
    retained['on_start']()
    history = assistant.event_manager.add_conversation_event.call_args_list
    assert [(call.args[1], call.kwargs['plugin_guid'], call.kwargs['avatar_url']) for call in history] == [
        ('Silent', 'commentary', None), ('Retained', 'commentary', 'commentary.png'),
    ]
    assistant.clear_conversation_state()
    assert retained['drop_if']()
