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
