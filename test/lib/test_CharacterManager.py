import queue
from threading import RLock
from unittest.mock import MagicMock

import pytest

from lib.Assistant import Assistant
from lib.CharacterManager import CharacterManager
from lib.EventManager import EventManager
from lib.Models import LLMResponse
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper


class CommentaryPlugin(PluginBase):
    def __init__(self):
        super().__init__(PluginManifest('{"guid":"test-commentary","name":"Commentary"}'))
        self.character = {'name': 'External', 'avatar': 'external.png'}


def make_speaker(characters, events, tts):
    assistant = Assistant.__new__(Assistant)
    assistant.characters, assistant.event_manager, assistant.tts = characters, events, tts
    assistant._turn_lock = RLock()
    assistant._generation = assistant._last_reset = 0
    return assistant


@pytest.fixture
def characters():
    provider = 'plugin:provider:speech'
    return CharacterManager({
        'tts_provider': provider,
        'active_character_index': 2,
        'active_characters': [4, 0, 2, 0, 3, 5, True, 99],
        'characters': [
            {'name': 'Navigator', 'character': 'Navigate.', 'tts_environment_helmet_effects_var': False},
            {'name': 'Standby', 'character': 'Not active.'},
            {'name': 'Pilot', 'character': 'Pilot the ship.', 'avatar': 'pilot.png', 'tts_speed': '1.4',
             'tts_voice_settings': {provider: {'voice': 'pilot-only'}}, 'tts_postprocessing': {'volume': 0.5}},
            {'name': ' pilot ', 'character': 'Duplicate pilot.'},
            {'name': 'External', 'character': 'Not model crew.', 'externally_voiced': True},
            {'name': 'Plugin record', 'character': 'Not model crew.', 'plugin_guid': 'test-commentary'},
        ],
    })


def test_active_prompts_are_primary_first_and_exclude_standby_external_and_duplicates(characters):
    assert characters.active_prompts == (('Pilot', 'Pilot the ship.'), ('Navigator', 'Navigate.'))
    assert characters.resolve_model(' PILOT ').crew_index == 2
    assert characters.resolve_model('Navigator').crew_index == 0
    del characters.config['active_characters']
    assert characters.active_prompts == (('Pilot', 'Pilot the ship.'),)
    assert characters.resolve_model('Navigator') is None


@pytest.mark.parametrize('speaker', ['Standby', 'External', 'Plugin record', 'Unknown'])
def test_rejected_labels_leave_history_and_tts_untouched(characters, speaker, monkeypatch):
    events, tts = MagicMock(), MagicMock()
    warning = MagicMock()
    monkeypatch.setattr('lib.Assistant.log', warning)
    assistant = make_speaker(characters, events, tts)
    assert assistant.queue_model_line(LLMResponse(text='Do not speak', character_name=speaker)) is None
    assert not events.mock_calls and not tts.mock_calls
    warning.assert_called_once()
    assert warning.call_args.args[0] == 'warn' and speaker in warning.call_args.args[1]


def test_pilot_plugin_pilot_resolves_each_line_without_inheriting_primary_settings(characters):
    events = EventManager.__new__(EventManager)
    events.incoming = queue.Queue()
    events.short_term_memory = MagicMock()
    events.processed, events.projections = [], []
    tts = MagicMock()
    assistant = make_speaker(characters, events, tts)
    helper = PluginHelper.__new__(PluginHelper)
    helper._assistant = assistant
    plugin = CommentaryPlugin()
    states = {'CurrentStatus': {'flags2': {'OnFoot': True}}}

    assistant.queue_model_line(LLMResponse(text='Welcome aboard'), states)
    helper.queue_utterance(plugin, LLMResponse(text='Telemetry', character_name='Pilot'))
    assistant.queue_model_line(LLMResponse(text='Fallback reply'), states)

    calls = tts.say.call_args_list
    assert events.incoming.empty()
    assert [call.args[0] for call in calls] == ['Welcome aboard', 'Telemetry', 'Fallback reply']
    first, external, last = [call.kwargs for call in calls]
    for current in (first, last):
        assert current['voice_settings'] == {'voice': 'pilot-only'}
        assert current['speed'] == 1.4
        assert current['postprocessing_layers'][0]['volume'] == 0.5
        assert len(current['postprocessing_layers']) == 2
    assert external['voice'] == '' and external['voice_settings'] == {'voice': ''}
    assert external['speed'] == 1.0
    assert len(external['postprocessing_layers']) == 1
    assert external['postprocessing_layers'][0]['volume'] == 1.0
    for call in calls:
        call.kwargs['on_start']()
    history = [event for event in list(events.incoming.queue) if event.kind == 'assistant']
    assert [(line.character_name, line.character_index, line.plugin_guid, line.avatar_url) for line in history] == [
        ('Pilot', 2, None, 'pilot.png'), ('External', None, 'test-commentary', 'external.png'),
        ('Pilot', 2, None, 'pilot.png'),
    ]


def test_environment_flags_follow_resolved_speaker(characters):
    states = {'CurrentStatus': {'flags2': {'OnFoot': True}}}
    navigator = characters.resolve_model('Navigator')
    assert len(characters.playback(navigator, states).postprocessing_layers) == 1
    plugin = CommentaryPlugin()
    plugin.character['tts_environment_helmet_effects_var'] = True
    assert len(characters.playback(characters.resolve_plugin(plugin), states).postprocessing_layers) == 2
