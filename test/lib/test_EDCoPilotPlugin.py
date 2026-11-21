from pathlib import Path
import queue
import sys
from threading import RLock
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lib.ActionManager import ActionManager
from lib.Assistant import Assistant
from lib.CharacterManager import CharacterManager
from lib.Event import ConversationEvent
from lib.EventManager import EventManager
from lib.PluginBase import PluginManifest
from lib.PluginManager import PluginManager
from lib.PluginHelper import PluginHelper
from plugins.EDCoPilotPlugin import EDCoPilotPlugin, SpeakingPhraseEvent


@pytest.fixture
def commentary_plugin(monkeypatch):
    monkeypatch.setattr(EDCoPilotPlugin, "is_installed", lambda self: False)
    plugin = EDCoPilotPlugin(PluginManifest('{"guid":"edcopilot-plugin"}'))
    plugin.settings = {"read_commentary": True, "voice": "Commentator"}
    plugin._helper = PluginHelper.__new__(PluginHelper)
    assistant = Assistant.__new__(Assistant)
    event_manager = EventManager.__new__(EventManager)
    event_manager.incoming = queue.Queue()
    event_manager.short_term_memory = MagicMock()
    event_manager.projections = []
    event_manager.processed = []
    assistant.event_manager = event_manager
    assistant.tts = MagicMock()
    plugin._helper._assistant = assistant
    plugin._helper._event_manager = event_manager
    plugin._helper._plugin_manager = MagicMock()
    plugin._helper._config = {
        "tts_provider": "plugin:tts-plugin:tts",
        "plugin_settings": {"tts-plugin": {"instructions": "Global style", "model": "tts-model"}},
        "characters": [{
            "name": "Commentator",
            "tts_voice_settings": {},
            "tts_postprocessing": {"volume": 0.5},
            "avatar": "commentator.png",
        }],
    }
    plugin._helper._plugin_manager.get_plugin_provider.return_value = {
        "voice_settings_config": [{
            "key": "voice",
            "label": "Voice",
            "fields": [{"key": "stability", "type": "number", "default_value": 0.5}],
        }],
    }
    assistant.config = plugin._helper._config
    assistant.characters = CharacterManager(assistant.config, plugin._helper._plugin_manager)
    assistant._turn_lock = RLock()
    assistant._generation = assistant._last_reset = 0
    plugin.client = MagicMock()
    plugin.client.pending_events = queue.Queue()
    plugin.client.pending_events.put(MagicMock(
        spec=SpeakingPhraseEvent,
        text="EDCoPilot commentary",
        reason="commentary",
        duration=0,
        interrupt=False,
    ))

    def stop_loop(_delay):
        raise RuntimeError("stop event loop")

    monkeypatch.setattr("plugins.EDCoPilotPlugin.time.sleep", stop_loop)
    return plugin


@pytest.mark.parametrize("stored_settings", [
    {"voice": "commentator-voice", "instructions": "Character style", "stability": 0.8},
    {"description": "Warm and conversational", "instructions": "Character style"},
    {},
])
def test_commentary_uses_full_character_voice_settings(commentary_plugin, stored_settings):
    character = commentary_plugin._helper._config["characters"][0]
    character["tts_voice_settings"] = {
        "plugin:tts-plugin:tts": stored_settings,
        "plugin:other-plugin:tts": {"voice": "wrong-voice"},
    }
    commentary_plugin.initialize_character(commentary_plugin._helper._config)
    assert "voice" not in commentary_plugin.settings

    with pytest.raises(RuntimeError, match="stop event loop"):
        commentary_plugin.process_edcopilot_events()

    kwargs = commentary_plugin._helper._assistant.tts.say.call_args.kwargs
    assert commentary_plugin._helper._assistant.tts.say.call_args.args == ("EDCoPilot commentary",)
    assert kwargs["voice"] == stored_settings.get('voice', '')
    assert kwargs["voice_settings"] == {
        "voice": "", "stability": 0.5, "instructions": "Global style", "model": "tts-model", **stored_settings,
    }
    assert kwargs["postprocessing_layers"][0]['volume'] == character["tts_postprocessing"]['volume']
    incoming = commentary_plugin._helper._event_manager.incoming
    assert incoming.empty()
    kwargs["on_start"]()
    kwargs["on_start"]()
    speaking, line, reaction = [incoming.get_nowait() for _ in range(3)]
    assert speaking.kind == "assistant_speaking"
    assert line.avatar_url == "commentator.png"
    assert line.character_name == "EDCoPilot" and line.plugin_guid == "edcopilot-plugin"
    assert reaction.plugin_guid == line.plugin_guid and reaction.has_conversation_line
    assert incoming.empty()
    commentary_plugin._helper._event_manager.short_term_memory.replied_before.assert_not_called()


@pytest.mark.parametrize("voice", ["raw-voice", ""])
def test_commentary_preserves_raw_voice_and_default_settings(commentary_plugin, voice):
    commentary_plugin.settings["voice"] = voice
    commentary_plugin.initialize_character(commentary_plugin._helper._config)

    with pytest.raises(RuntimeError, match="stop event loop"):
        commentary_plugin.process_edcopilot_events()

    kwargs = commentary_plugin._helper._assistant.tts.say.call_args.kwargs
    assert kwargs["voice"] == voice
    assert kwargs["voice_settings"] == {
        "voice": voice, "stability": 0.5, "instructions": "Global style", "model": "tts-model",
    }
    assert kwargs["postprocessing_layers"][0]['volume'] == 1.0


def test_commentary_does_not_apply_character_voice_settings_in_dominant_mode(commentary_plugin):
    commentary_plugin._helper._config["tts_provider"] = (
        f"plugin:{commentary_plugin.plugin_manifest.guid}:edcopilot-dominant"
    )
    commentary_plugin.initialize_character(commentary_plugin._helper._config)

    with pytest.raises(RuntimeError, match="stop event loop"):
        commentary_plugin.process_edcopilot_events()

    kwargs = commentary_plugin._helper._assistant.tts.say.call_args.kwargs
    assert kwargs["voice"] == ''
    assert kwargs["voice_settings"] == {'voice': ''}
    assert kwargs["postprocessing_layers"][0]['volume'] == 0.5


def test_commentary_uses_legacy_voice_if_profile_migration_has_not_succeeded(commentary_plugin):
    plugin = commentary_plugin
    with pytest.raises(RuntimeError, match="stop event loop"):
        plugin.process_edcopilot_events()
    kwargs = plugin._helper._assistant.tts.say.call_args.kwargs
    assert kwargs['voice_settings']['model'] == 'tts-model'
    assert kwargs['postprocessing_layers'][0]['volume'] == 0.5


def test_edcopilot_migration_persists_legacy_controls_and_retains_saved_edits(commentary_plugin, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    plugin = commentary_plugin
    guid = plugin.plugin_manifest.guid
    config = plugin._helper._config
    config["plugin_settings"][guid] = {"enabled": True, "read_commentary": True, "react_to_commentary": True, "voice": "Commentator"}
    manager = PluginManager(config)
    manager.plugin_list[guid] = manager._initialize_plugin_settings(plugin)
    assert config["plugin_settings"][guid] == {"enabled": True}
    assert plugin.character["react_to_commentary"] is True
    assert plugin.character["avatar"] == "commentator.png"
    manager.update_plugin_character(guid, {"read_commentary": False})
    reloaded = manager._initialize_plugin_settings(EDCoPilotPlugin(plugin.plugin_manifest))
    assert reloaded.character["read_commentary"] is False
    assert reloaded.character["react_to_commentary"] is True


def test_external_commentary_is_recorded_without_replaying_or_echoing(commentary_plugin):
    plugin = commentary_plugin
    plugin.initialize_character(plugin._helper._config)
    plugin.client.pending_events.queue[0].duration = 1

    with pytest.raises(RuntimeError, match="stop event loop"):
        plugin.process_edcopilot_events()

    plugin._helper._assistant.tts.say.assert_not_called()
    incoming = plugin._helper._event_manager.incoming
    line, reaction = [incoming.get_nowait() for _ in range(2)]
    assert isinstance(line, ConversationEvent) and line.plugin_guid == plugin.plugin_manifest.guid
    assert line.avatar_url is None
    assert reaction.plugin_event_name == "EdCoPilotEvent"
    assert incoming.empty()
    plugin.provider = MagicMock()
    plugin.output_covas = MagicMock()
    plugin._on_event(line, {})
    plugin.output_covas.assert_not_called()
    plugin._on_event(ConversationEvent(kind="assistant", content="Normal reply"), {})
    plugin.output_covas.assert_called_once_with("Normal reply", [])


def test_only_registered_commentary_event_can_trigger_live_reactions(commentary_plugin):
    plugin = commentary_plugin
    helper = plugin._helper
    assistant = helper._assistant
    assistant.config['active_character_index'] = 0
    assistant.registered_should_reply_handlers = []
    helper._prompt_generator = MagicMock()
    plugin.initialize_character(helper._config)
    plugin._register_commentary_event(helper)
    plugin.client.pending_events.queue[0].duration = 1
    with pytest.raises(RuntimeError, match="stop event loop"):
        plugin.process_edcopilot_events()
    line, reaction = [helper._event_manager.incoming.get_nowait() for _ in range(2)]

    assistant.pending = [line, reaction]
    assert not assistant.should_reply({})
    plugin.character['react_to_commentary'] = True
    assert assistant.should_reply({})
    assistant.pending = [line]
    assert not assistant.should_reply({})


@pytest.mark.parametrize("settings", [
    {},
    {"enabled": True},
    {"enabled": True, "actions": False},
    {"enabled": False, "actions": True},
])
def test_disabled_edcopilot_actions_are_not_offered_or_executed(settings):
    plugin = EDCoPilotPlugin.__new__(EDCoPilotPlugin)
    plugin.settings = {"enabled": True, "actions": True}
    plugin.edcopilot_open_panel = MagicMock(return_value="opened")
    manager = ActionManager()
    helper = PluginHelper.__new__(PluginHelper)
    helper._action_manager = manager
    plugin._register_actions(helper)
    assert len(manager.getToolsList("mainship", True, True, True)) == 2

    # PluginManager replaces settings dictionaries when the UI updates them.
    plugin.settings = settings

    assert manager.getToolsList("mainship", True, True, True) == []
    result = manager.runAction(ChatCompletionMessageFunctionToolCall(
        id="call_test", type="function",
        function={"name": "edcopilot_open_panel", "arguments": '{"panelName":"aboutedcopilot"}'},
    ), {})
    assert "disabled" in result["content"]
    plugin.edcopilot_open_panel.assert_not_called()

    plugin.settings = {"enabled": True, "actions": True}
    assert len(manager.getToolsList("mainship", True, True, True)) == 2
