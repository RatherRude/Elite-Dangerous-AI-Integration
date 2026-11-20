from pathlib import Path
import queue
import sys
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lib.ActionManager import ActionManager
from lib.PluginHelper import PluginHelper
from plugins.EDCoPilotPlugin import EDCoPilotPlugin, SpeakingPhraseEvent


@pytest.fixture
def commentary_plugin(monkeypatch):
    plugin = EDCoPilotPlugin.__new__(EDCoPilotPlugin)
    plugin.plugin_manifest = MagicMock(guid="edcopilot-plugin")
    plugin.settings = {"read_commentary": True, "voice": "Commentator"}
    plugin._helper = MagicMock()
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

    with pytest.raises(RuntimeError, match="stop event loop"):
        commentary_plugin.process_edcopilot_events()

    kwargs = commentary_plugin._helper._assistant.tts.say.call_args.kwargs
    assert commentary_plugin._helper._assistant.tts.say.call_args.args == ("EDCoPilot commentary",)
    assert kwargs["voice"] is None
    assert kwargs["voice_settings"] == {
        "stability": 0.5, "instructions": "Global style", "model": "tts-model", **stored_settings,
    }
    assert kwargs["postprocessing"] == character["tts_postprocessing"]
    kwargs["on_start"]()
    event = commentary_plugin._helper.dispatch_event.call_args.args[0]
    assert event.plugin_event_content["avatar_url"] == "commentator.png"


@pytest.mark.parametrize("voice", ["raw-voice", ""])
def test_commentary_preserves_raw_voice_and_default_settings(commentary_plugin, voice):
    commentary_plugin.settings["voice"] = voice

    with pytest.raises(RuntimeError, match="stop event loop"):
        commentary_plugin.process_edcopilot_events()

    kwargs = commentary_plugin._helper._assistant.tts.say.call_args.kwargs
    assert kwargs["voice"] == (voice or None)
    assert kwargs["voice_settings"] is None
    assert kwargs["postprocessing"] is None


def test_commentary_does_not_apply_character_voice_settings_in_dominant_mode(commentary_plugin):
    commentary_plugin._helper._config["tts_provider"] = (
        f"plugin:{commentary_plugin.plugin_manifest.guid}:edcopilot-dominant"
    )

    with pytest.raises(RuntimeError, match="stop event loop"):
        commentary_plugin.process_edcopilot_events()

    kwargs = commentary_plugin._helper._assistant.tts.say.call_args.kwargs
    assert kwargs["voice"] is None
    assert kwargs["voice_settings"] is None
    assert kwargs["postprocessing"] == {"volume": 0.5}


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
