from copy import deepcopy
import json
from pathlib import Path
from queue import Queue
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / 'src'))

from lib.Event import PluginEvent
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper
from lib.PluginManager import PluginManager
from lib.PluginNamespace import PluginNamespace
from lib.PluginSettingDefinitions import SettingsHeaderLink


def test_header_link_scopes_translations_and_preserves_destination():
    link = SettingsHeaderLink(text='@support.prompt', label='@support.link', url='https://example.org/support')
    settings = {'header_link': link}
    exported = PluginNamespace('alpha').presentation(settings)
    assert exported['header_link'] == {
        'text': 'plugin.alpha.support.prompt', 'label': 'plugin.alpha.support.link',
        'url': 'https://example.org/support',
    }
    assert link['text'] == '@support.prompt'


def test_list_confirmation_and_action_notification_scope_only_the_translation_keys():
    original = {'confirmation': '@delete', 'notification': '@added', 'params': {'title': '@literal'}}
    assert PluginNamespace('alpha').presentation(original) == {
        'confirmation': 'plugin.alpha.delete', 'notification': 'plugin.alpha.added', 'params': {'title': '@literal'},
    }
    assert original['confirmation'] == '@delete'


class LocalPlugin(PluginBase):
    def __init__(self, guid):
        super().__init__(PluginManifest(json.dumps({'guid': guid, 'name': 'Local plugin'})))
        self.settings_config = {'key': 'not-the-owner', 'label': '@title', 'grids': [{
            'key': 'general', 'label': '@general', 'fields': [{
                'key': 'status', 'type': 'paragraph', 'content': '@ready',
            }], 'content': [{
                'type': 'action', 'action': 'refresh', 'payload': {'label': '@user-data'},
                'text': {'key': '@refresh', 'text': '@literal', 'params': {'nested': {'key': '@title'}}},
            }],
        }]}

    def get_ui_translations(self):
        return {'en': {'title': 'Local plugin', 'general': 'General', 'ready': 'Ready', 'refresh': 'Refresh'}}

    def on_chat_start(self, helper):
        self.helper = helper


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr('lib.PluginManager.emit_message', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('lib.PluginManager.save_config', lambda _config: None)
    manager = PluginManager({'plugin_settings': {'alpha': {'nested': {'value': 1}}, 'beta': {'secret': 'private'}}})
    alpha, beta = LocalPlugin('alpha'), LocalPlugin('beta')
    manager.plugin_list = {'alpha': alpha, 'beta': beta}
    manager.register_settings()
    return manager, alpha, beta


def test_registration_scopes_presentation_without_mutating_plugin_data(manager):
    manager, alpha, _ = manager
    original = deepcopy(alpha.settings_config)
    settings = manager.plugin_settings_configs['alpha']
    assert settings['key'] == 'alpha'
    assert settings['label'] == 'plugin.alpha.title'
    assert settings['grids'][0]['fields'][0]['content'] == 'plugin.alpha.ready'
    node = settings['grids'][0]['content'][0]
    assert node['text']['params']['nested']['key'] == 'plugin.alpha.title'
    assert node['payload'] == {'label': '@user-data'}
    assert node['text']['text'] == '@literal'
    assert alpha.settings_config == original
    assert manager.plugin_settings_configs['beta']['label'] == 'plugin.beta.title'


def test_owner_identity_is_fixed_at_registration_and_settings_cannot_escape(manager):
    manager, alpha, beta = manager
    alpha.plugin_manifest.guid = 'beta'
    alpha.settings_config['key'] = 'beta'
    assert alpha.update_setting('plugin_settings.beta.secret', {'value': 2})
    assert manager.config['plugin_settings']['beta'] == {'secret': 'private'}
    assert manager.config['plugin_settings']['alpha']['plugin_settings.beta.secret'] == {'value': 2}
    alpha.settings['plugin_settings.beta.secret']['value'] = 3
    config = alpha.get_app_config()
    assert set(config['plugin_settings']) == {'alpha'}
    config['plugin_settings']['alpha']['plugin_settings.beta.secret']['value'] = 4
    assert manager.config['plugin_settings']['alpha']['plugin_settings.beta.secret'] == {'value': 2}
    alpha.publish_ui()
    alpha.publish_settings()
    assert manager.plugin_settings_configs['alpha']['key'] == 'alpha'
    assert beta.get_app_config()['plugin_settings'] == {'beta': {'secret': 'private'}}


def test_registration_rejects_duplicate_and_invalid_namespaces(manager):
    manager, _, _ = manager
    with pytest.raises(ValueError, match='Duplicate'):
        manager._register_plugin(LocalPlugin('alpha'))
    for guid in ['', '../beta', 'beta.child', 'beta:child']:
        with pytest.raises(ValueError, match='namespace'):
            manager._register_plugin(LocalPlugin(guid))


def test_loaded_manifest_owns_namespace_even_if_constructor_changes_it(manager, monkeypatch):
    manager, _, _ = manager

    class MisconfiguredPlugin(LocalPlugin):
        def __init__(self, manifest):
            super().__init__(manifest.guid)
            manifest.guid = 'beta'
            self.plugin_manifest = manifest

    monkeypatch.setattr('lib.PluginManager.importlib.import_module', lambda _name: SimpleNamespace(Plugin=MisconfiguredPlugin))
    plugin = manager.load_plugin_module(PluginManifest('{"guid":"gamma","name":"Gamma"}'), 'gamma/plugin.py')
    assert manager._namespaces[plugin].guid == 'gamma'
    assert plugin.update_setting('status', 'ready')
    assert manager.config['plugin_settings']['gamma']['status'] == 'ready'
    assert manager.config['plugin_settings']['beta'] == {'secret': 'private'}


def test_translations_cannot_replace_core_or_other_plugin_dictionaries():
    namespace = PluginNamespace('alpha')
    for translations in [
        {'en': {'plugin': {'beta': {'title': 'Hijacked'}}}},
        {'en': {'plugin': {'alpha': {'title': 'Own'}}, 'common': {'cancel': 'Hijacked'}}},
        {'en': {'plugin.beta.title': 'Hijacked'}},
    ]:
        with pytest.raises(ValueError):
            namespace.translations(translations)
    assert namespace.translations({'en': {'common': {'cancel': 'Own cancel'}}}) == {'en': {'common': {'cancel': 'Own cancel'}}}
    assert namespace.translations({'en': {'plugin': {'alpha': {'title': 'Legacy'}}}}) == {'en': {'title': 'Legacy'}}
    with pytest.raises(ValueError, match='owner'):
        namespace.presentation({'label': 'plugin.beta.title'})
    assert namespace.presentation({'label': 'common.cancel'}) == {'label': 'common.cancel'}


def test_two_runtime_helpers_scope_same_local_events_and_data_paths(manager, tmp_path, monkeypatch):
    manager, alpha, beta = manager
    prompts, replies = [], []
    events = SimpleNamespace(incoming=Queue())
    helper = PluginHelper(manager, SimpleNamespace(register_prompt_event_handler=prompts.append), {}, None,
                          events, None, None, None, None, SimpleNamespace(register_should_reply_handler=replies.append))
    monkeypatch.setattr(PluginHelper, 'PLUGIN_DATA_PATH', str(tmp_path))
    manager.on_chat_start(helper)
    for plugin in [alpha, beta]:
        plugin.helper.register_event('changed', lambda event: event.plugin_event_name == 'changed',
                                     lambda event: event.plugin_event_name)
    original = PluginEvent(plugin_event_name='changed', plugin_event_content={'value': 1})
    alpha.helper.dispatch_event(original)
    beta.helper.dispatch_event(original)
    first, second = events.incoming.get_nowait(), events.incoming.get_nowait()
    assert (first.plugin_event_name, second.plugin_event_name, original.plugin_event_name) == ('alpha.changed', 'beta.changed', 'changed')
    assert [handler(first) for handler in prompts] == ['changed', None]
    assert [handler(second) for handler in prompts] == [None, 'changed']
    assert [handler(first, {}) for handler in replies] == [True, None]
    alpha.helper.dispatch_event(PluginEvent(plugin_event_name='beta.changed', plugin_event_content={}))
    assert events.incoming.get_nowait().plugin_event_name == 'alpha.beta.changed'
    alpha.plugin_manifest.guid = 'beta'
    assert Path(alpha.helper.get_plugin_data_path()) == tmp_path / 'alpha'
    assert Path(beta.helper.get_plugin_data_path()) == tmp_path / 'beta'
    with pytest.raises(ValueError, match='owner'):
        alpha.helper._plugin_manager.update_plugin_setting('beta', 'secret', 'changed')
    with pytest.raises(ValueError, match='owner'):
        alpha.helper.get_plugin_data_path(beta.plugin_manifest)


def test_ui_errors_resolve_local_keys_and_reject_foreign_references(manager, monkeypatch):
    manager, alpha, _ = manager
    emitted = []
    monkeypatch.setattr('lib.PluginManager.emit_message', lambda kind, **payload: emitted.append((kind, payload)))

    def fail(_action, _payload):
        raise ValueError('@ready')

    alpha.on_ui_action = fail
    manager.on_ui_action('alpha', 'fail', {}, 'request')
    assert emitted[-1][1]['error'] == 'plugin.alpha.ready'

    def foreign(_action, _payload):
        raise ValueError('plugin.beta.secret')

    alpha.on_ui_action = foreign
    manager.on_ui_action('alpha', 'fail', {}, 'request-2')
    assert emitted[-1][1]['error'] == 'common.invalidAction'
