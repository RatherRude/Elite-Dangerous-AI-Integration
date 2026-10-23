import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lib.PluginBase import PluginManifest
from plugins import EDCoPilotPlugin as edcp


PROVIDER_REF = 'plugin:voice-plugin:tts'


@pytest.fixture
def plugin(monkeypatch):
    monkeypatch.setattr(edcp, 'get_install_path', lambda: 'installed')
    monkeypatch.setattr(edcp, 'get_process_id', lambda: None)
    plugin = edcp.EDCoPilotPlugin(PluginManifest(json.dumps({'guid': 'edcp', 'name': 'EDCoPilot'})))
    manager = MagicMock()
    manager.get_plugin_provider.return_value = {'voice_settings_config': [{
        'key': 'voice', 'label': 'Voice', 'fields': [
            {'key': 'voice', 'type': 'text', 'default_value': 'default'},
            {'key': 'style_options', 'type': 'condition',
             'condition': {'key': 'model', 'operator': 'eq', 'value': 'expressive'},
             'fields': [
                 {'key': 'instructions', 'type': 'textarea', 'default_value': 'default style'},
             ]},
        ],
    }]}
    plugin._helper = SimpleNamespace(_config={
        'tts_provider': PROVIDER_REF,
        'plugin_settings': {'voice-plugin': {'voice': 'global', 'model': 'expressive'}},
        'characters': [{'tts_voice_settings': {PROVIDER_REF: {'voice': 'regular'}}}],
    }, _plugin_manager=manager)
    return plugin


@pytest.mark.parametrize('overrides, expected_voice, expected_instructions', [
    ({}, 'global', 'default style'),
    ({'voice': 'own', 'instructions': 'Own style'}, 'own', 'Own style'),
    ({'voice': None, 'instructions': None}, 'global', 'default style'),
    ({'instructions': ''}, 'global', ''),
])
def test_plugin_character_merges_provider_globals_and_nested_defaults(
    plugin, overrides, expected_voice, expected_instructions,
):
    character = {**plugin.character, 'tts_voice_settings': {PROVIDER_REF: overrides}}
    before = deepcopy((character, plugin._helper._config))

    settings = plugin._character_voice_settings(character)

    assert settings == {
        'voice': expected_voice, 'instructions': expected_instructions, 'model': 'expressive',
    }
    assert (character, plugin._helper._config) == before
    plugin._helper._plugin_manager.get_plugin_provider.assert_called_once_with('voice-plugin', 'tts')


def test_plugin_character_legacy_fallbacks_yield_to_explicit_provider_overrides(plugin):
    character = {**plugin.character, 'tts_voice': 'legacy', 'tts_prompt': 'Legacy style'}
    assert plugin._character_voice_settings(character) == {
        'voice': 'legacy', 'instructions': 'Legacy style', 'model': 'expressive',
    }

    character['tts_voice_settings'] = {PROVIDER_REF: {
        'voice': 'own', 'instructions': '', 'unknown': 'ignored',
    }}
    assert plugin._character_voice_settings(character) == {
        'voice': 'own', 'instructions': '', 'model': 'expressive',
    }


def test_plugin_character_uses_current_provider_on_each_call(plugin):
    assert plugin._character_voice_settings(plugin.character)['voice'] == 'global'

    plugin._helper._config['tts_provider'] = 'plugin:other-plugin:tts'
    plugin._helper._config['plugin_settings']['other-plugin'] = {'voice': 'other-global'}
    assert plugin._character_voice_settings(plugin.character)['voice'] == 'other-global'
    plugin._helper._plugin_manager.get_plugin_provider.assert_called_with('other-plugin', 'tts')
