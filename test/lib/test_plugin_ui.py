import json
import sys
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / 'src'))

from lib.Event import GameEvent
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper
from lib.PluginManager import PluginManager
from lib.PluginSettingDefinitions import PluginSettings
from lib.PluginUIDefinitions import PluginUIView, UINode, UIText, UIViewSection
from lib.PluginUIDefinitions import TextInput, Button, Progress, Select, SelectOption, Toggle
from lib.PluginSettingDefinitions import SettingsGrid, ModelProviderDefinition
from lib.actions import actions_ui


class DashboardPlugin(PluginBase):
    def __init__(self, guid):
        super().__init__(PluginManifest(json.dumps({'guid': guid, 'name': 'Dashboard'})))
        self.count = 0
        self.buttons = []
        self.settings_config = PluginSettings(key=guid, label='Dashboard', icon='dashboard', grids=[])

    def get_ui_views(self):
        return [PluginUIView(id='dashboard', label='@title', sections=[
            UIViewSection(key='overview', label='Overview', content=[UINode(type='text', text=UIText(text=str(self.count)))]),
            UIViewSection(key='details', label='Details', grids=[]),
        ])]

    def get_ui_translations(self):
        return {lang: {'title': title}
                for lang, title in [('en', 'Dashboard'), ('fr', 'Tableau de bord')]}

    def on_ui_action(self, action, payload):
        if action == 'increment':
            self.count += payload['amount']
            return {'count': self.count}
        return super().on_ui_action(action, payload)

    def on_settings_button(self, key, value=None):
        self.buttons.append((key, value))

    def on_chat_start(self, helper):
        def on_event(event, states):
            if isinstance(event, GameEvent) and event.content.get('event') == 'Docked':
                self.count += 1
                self.publish_ui()
        helper.register_sideeffect(on_event)


@pytest.fixture
def manager(monkeypatch):
    emitted = []
    monkeypatch.setattr('lib.PluginManager.emit_message', lambda kind, **payload: emitted.append((kind, deepcopy(payload))))
    manager = PluginManager({'plugin_settings': {}})
    return manager, emitted


def register(manager, guid):
    plugin = DashboardPlugin(guid)
    manager.plugin_list[guid] = plugin
    manager.register_settings()
    return plugin


def test_plugins_register_same_local_view_id_without_collision_and_publish_translations(manager):
    manager, emitted = manager
    register(manager, 'alpha-guid')
    register(manager, 'beta-guid')
    assert set(manager.get_ui_targets()) == {'plugin:alpha-guid:dashboard', 'plugin:beta-guid:dashboard'}
    contributions = next(payload for kind, payload in reversed(emitted) if kind == 'plugin_ui')['plugins']
    assert contributions['alpha-guid']['translations']['fr']['title'] == 'Tableau de bord'
    assert contributions['alpha-guid']['views'][0]['label'] == 'plugin.alpha-guid.title'
    assert manager.config == {'plugin_settings': {}}


def test_ui_interactions_route_to_owner_and_correlate_success_and_errors(manager):
    manager, emitted = manager
    alpha = register(manager, 'alpha')
    beta = register(manager, 'beta')
    manager.on_ui_action('alpha', 'increment', {'amount': 3}, 'request-1')
    assert alpha.count == 3 and beta.count == 0
    assert emitted[-1] == ('plugin_ui_result', {'request_id': 'request-1', 'plugin_guid': 'alpha',
                                               'success': True, 'result': {'count': 3}})
    manager.on_ui_action('alpha', 'settings_button', {'key': 'rename:item', 'value': 'Title'}, 'request-2')
    assert alpha.buttons == [('rename:item', 'Title')]
    manager.on_ui_action('alpha', 'settings_button', {'key': 123}, 'request-3')
    assert emitted[-1][1]['success'] is False
    assert emitted[-1][1]['request_id'] == 'request-3'
    manager.on_ui_action('missing', 'increment', {'amount': 1}, 'request-4')
    assert emitted[-1][1]['success'] is False
    assert alpha.count == 3 and beta.count == 0


def test_event_hook_updates_plugin_view_through_public_api(manager):
    manager, emitted = manager
    plugin = register(manager, 'events-guid')
    callbacks = []
    states = {'Location': {'StarSystem': 'Sol'}}
    events = SimpleNamespace(register_sideeffect=callbacks.append, get_current_state=lambda: ([], states))
    helper = PluginHelper(manager, None, {}, None, events, None, None, None, None, None)
    manager.on_chat_start(helper)
    assert helper.get_current_state() == ([], states)
    callbacks[0](GameEvent(content={'event': 'Docked'}, historic=False), states)
    assert plugin.count == 1
    view = next(payload for kind, payload in reversed(emitted) if kind == 'plugin_ui')['plugins']['events-guid']['views'][0]
    assert view['sections'][0]['content'][0]['text']['text'] == '1'


def test_navigation_uses_registered_targets_and_validates_sections(manager, monkeypatch):
    manager, _ = manager
    register(manager, 'other-guid')
    messages = []
    monkeypatch.setattr(actions_ui, 'send_message', messages.append)
    monkeypatch.setattr(actions_ui, 'plugin_manager', None)
    action_manager = SimpleNamespace(actions={'showUI': {'tool': {'function': {'parameters': {'properties': {'tab': {}, 'submenu': {}}}}}}})
    actions_ui.configure_plugin_ui(manager, action_manager)
    schema = action_manager.actions['showUI']['tool']['function']['parameters']['properties']
    assert 'plugin:other-guid:dashboard' in schema['tab']['enum']
    actions_ui.show_ui({'tab': 'plugin:other-guid:dashboard', 'submenu': 'details'}, {})
    assert messages == [{'type': 'ui', 'show': 'plugin:other-guid:dashboard', 'submenu': 'details'}]
    with pytest.raises(Exception, match='Unknown submenu'):
        actions_ui.show_ui({'tab': 'plugin:other-guid:dashboard', 'submenu': 'missing'}, {})
    manager.plugin_ui = {}
    manager.broadcast_plugin_ui()
    assert 'plugin:other-guid:dashboard' not in schema['tab']['enum']
    with pytest.raises(Exception, match='Unknown tab'):
        actions_ui.show_ui({'tab': 'plugin:other-guid:dashboard'}, {})


def test_application_without_plugins_has_no_views(manager):
    manager, emitted = manager
    manager.register_settings()
    assert manager.get_ui_targets() == {}
    assert next(payload for kind, payload in emitted if kind == 'plugin_ui') == {'plugins': {}}


def test_duplicate_view_ids_are_rejected(manager):
    manager, _ = manager
    plugin = register(manager, 'example')
    views = plugin.get_ui_views()
    plugin.get_ui_views = lambda: views * 2
    with pytest.raises(ValueError, match='unique'):
        manager.publish_plugin_ui(plugin)


def test_legacy_single_argument_settings_button_works_with_both_transports(manager):
    manager, emitted = manager
    plugin = register(manager, 'legacy')
    clicks = []
    plugin.on_settings_button = clicks.append
    manager.on_settings_button('legacy', 'refresh')
    manager.on_ui_action('legacy', 'settings_button', {'key': 'refresh'}, 'legacy-request')
    assert clicks == ['refresh', 'refresh']
    assert emitted[-1][1]['success'] is True


def test_historical_component_names_are_exact_aliases():
    from lib import PluginSettingDefinitions as legacy, PluginUIDefinitions as ui

    for old, new in {
        'SettingBase': 'InputBase', 'TextSetting': 'TextInput', 'TextAreaSetting': 'TextArea',
        'NumericalSetting': 'NumberInput', 'ToggleSetting': 'Toggle', 'SelectSetting': 'Select',
        'ButtonSetting': 'Button', 'ParagraphSetting': 'Paragraph', 'ErrorSetting': 'Error',
    }.items():
        assert getattr(legacy, old) is getattr(ui, new)
    password = legacy.TextSetting(key='password', label='Password', type='text', readonly=False,
                                  placeholder=None, default_value='', max_length=None, min_length=None, hidden=True)
    assert password['hidden'] is True
    assert isinstance(password, dict)


class UnifiedPlugin(DashboardPlugin):
    def __init__(self, guid):
        super().__init__(guid)
        self.options = ['first']
        self.progress = 0
        self.status = 'initial'
        self.changes = []
        self.settings_calls = 0
        self.model_providers = [ModelProviderDefinition(
            kind='llm', id='model', label='Model', settings_config=[
                SettingsGrid(key='provider', label='Provider', fields=[
                    Toggle(key='enabled', type='toggle', default_value=False),
                ]),
            ],
        )]

    def components(self):
        return [
            TextInput(key='search', type='text', label='Search', default_value='',
                      min_length=None, max_length=None),
            Select(key='choice', type='select', default_value='first', multi_select=False,
                   select_options=[SelectOption(key=key, label=key, value=key, disabled=False) for key in self.options]),
            Button(key='refresh', type='button', label='Refresh'),
            Progress(key='progress', type='progress', value=self.progress, maximum=10,
                     text=UIText(text=self.status)),
        ]

    def get_ui_settings(self):
        return PluginSettings(key='settings', label='Settings', icon='settings', grids=[
            SettingsGrid(key='shared', label='Shared', fields=self.components()),
        ])

    def get_ui_views(self):
        return [PluginUIView(id='dashboard', label='Dashboard', sections=[
            UIViewSection(key='main', label='Main', content=self.components() + [
                TextInput(key='transient', type='text', default_value='view only', min_length=None, max_length=None),
            ]),
        ])]

    def on_ui_changed(self, key, value, state):
        self.changes.append((key, value, state))
        if key == 'choice':
            self.update_setting(key, value)
        self.status = state['search']

    def on_settings_changed(self):
        self.settings_calls += 1


def register_unified(manager, guid='unified'):
    plugin = UnifiedPlugin(guid)
    manager.plugin_list[guid] = plugin
    manager.register_settings()
    return plugin


def test_shared_callback_exposes_current_state_without_automatic_persistence(manager, monkeypatch):
    manager, emitted = manager
    saved = []
    monkeypatch.setattr('lib.PluginManager.save_config', lambda config: saved.append(deepcopy(config)))
    plugin = register_unified(manager)
    other = register_unified(manager, 'other')

    manager.on_ui_action('unified', 'ui_changed', {'key': 'search', 'value': 'filter', 'state': {'choice': 'forged'}}, 'search')
    assert plugin.changes == [('search', 'filter', {
        'search': 'filter', 'choice': 'first', 'enabled': False, 'transient': 'view only',
    })]
    assert plugin.settings == {} and saved == []
    assert other.get_ui_state()['search'] == ''
    assert emitted[-1][1]['success'] is True
    manager.on_settings_changed(manager.config)
    assert plugin.get_ui_state()['search'] == 'filter'

    manager.on_ui_action('unified', 'ui_changed', {'key': 'choice', 'value': 'second'}, 'choice')
    assert plugin.settings == {'choice': 'second'}
    assert len(saved) == 1 and plugin.settings_calls == 2
    assert plugin.changes[-1][2]['search'] == 'filter'
    snapshot = plugin.get_ui_state()
    snapshot['search'] = 'mutated'
    assert plugin.get_ui_state()['search'] == 'filter'


def test_default_ui_callback_preserves_legacy_persistence_and_hook(manager, monkeypatch):
    manager, emitted = manager
    monkeypatch.setattr('lib.PluginManager.save_config', lambda config: None)
    plugin = register_unified(manager)
    plugin.on_ui_changed = PluginBase.on_ui_changed.__get__(plugin)
    manager.on_ui_action('unified', 'ui_changed', {'key': 'search', 'value': 'saved'}, 'legacy-edit')
    manager.on_ui_action('unified', 'ui_changed', {'key': 'enabled', 'value': True}, 'provider-edit')
    manager.on_ui_action('unified', 'ui_changed', {'key': 'transient', 'value': 'not saved'}, 'view-edit')
    assert plugin.settings == {'search': 'saved', 'enabled': True}
    assert plugin.settings_calls == 2
    assert plugin.get_ui_state()['transient'] == 'not saved'
    manager.on_settings_changed({'plugin_settings': {'unified': {'search': 'external', 'enabled': False}}})
    assert plugin.get_ui_state()['search'] == 'external'
    assert plugin.get_ui_state()['enabled'] is False
    assert plugin.settings_calls == 3
    assert emitted[-1][0] == 'plugin_model_providers'


def test_view_only_input_can_explicitly_persist_a_preference(manager, monkeypatch):
    manager, emitted = manager
    monkeypatch.setattr('lib.PluginManager.save_config', lambda config: None)
    plugin = register_unified(manager)

    def persist(key, value, state):
        assert state[key] == value
        plugin.update_setting(key, value.strip())

    plugin.on_ui_changed = persist
    manager.on_ui_action('unified', 'ui_changed', {'key': 'transient', 'value': ' saved in view '}, 'persist-view')
    assert emitted[-1][1]['success'] is True
    assert plugin.settings['transient'] == 'saved in view'
    assert plugin.get_ui_state()['transient'] == 'saved in view'
    manager.on_settings_changed({'plugin_settings': {'unified': {'transient': 'external'}}})
    assert plugin.get_ui_state()['transient'] == 'external'


def test_one_publication_updates_settings_views_options_progress_and_provider(manager, monkeypatch):
    manager, emitted = manager
    monkeypatch.setattr('lib.PluginManager.save_config', lambda config: pytest.fail('Publication must not persist'))
    plugin = register_unified(manager)
    manager.on_ui_action('unified', 'ui_changed', {'key': 'search', 'value': 'live'}, 'edit')
    plugin.options.append('second')
    plugin.progress = 7
    plugin.model_providers[0]['settings_config'][0]['label'] = 'Updated provider'
    emitted.clear()
    plugin.publish_ui()
    ui = next(payload for kind, payload in emitted if kind == 'plugin_ui')['plugins']['unified']
    settings = next(payload for kind, payload in emitted if kind == 'plugin_settings_configs')['plugin_settings_configs']['unified']
    view_components = ui['views'][0]['sections'][0]['content']
    assert settings['grids'][0]['fields'] == view_components[:4]
    assert view_components[1]['select_options'][-1]['value'] == 'second'
    assert view_components[3]['value'] == 7 and view_components[3]['text']['text'] == 'live'
    assert ui['state']['search'] == 'live'
    providers = next(payload for kind, payload in emitted if kind == 'plugin_model_providers')['providers']
    assert providers[0]['settings_config'][0]['label'] == 'Updated provider'
    emitted.clear()
    plugin.publish_settings()
    assert {kind for kind, _ in emitted} == {'plugin_ui', 'plugin_settings_configs', 'plugin_model_providers'}
    plugin.get_ui_settings = lambda: None
    plugin.get_ui_views = lambda: []
    plugin.publish_ui()
    assert 'unified' not in manager.plugin_settings_configs
    assert manager.plugin_ui['unified']['views'] == []


def test_ui_change_rejects_unknown_readonly_inputs_and_reports_callback_errors(manager):
    manager, emitted = manager
    plugin = register_unified(manager)
    for payload in ({'key': 'unknown', 'value': 'bad'}, {'key': 'search'}, {'key': 'progress', 'value': 8}):
        manager.on_ui_action('unified', 'ui_changed', payload, 'invalid')
        assert emitted[-1][1]['success'] is False
    original = plugin.get_ui_settings()
    original['grids'][0]['fields'][0]['readonly'] = True
    plugin.get_ui_settings = lambda: original
    plugin.get_ui_views = lambda: []
    manager.on_ui_action('unified', 'ui_changed', {'key': 'search', 'value': 'bad'}, 'readonly')
    assert emitted[-1][1]['success'] is False
    assert plugin.changes == []
    original['grids'][0]['fields'][0]['readonly'] = False

    def fail(key, value, state):
        raise ValueError('@invalid')

    plugin.on_ui_changed = fail
    manager.on_ui_action('unified', 'ui_changed', {'key': 'search', 'value': 'bad'}, 'failure')
    assert emitted[-1][1]['error'] == 'plugin.unified.invalid'
    assert plugin.get_ui_state()['search'] == ''
