import json
import sys
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / 'src'))

from lib.Event import ConversationEvent, GameEvent, ToolEvent
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper
from lib.PluginManager import PluginManager
from lib.PluginSettingDefinitions import PluginSettings
from lib.PluginUIDefinitions import List as UIList, PluginUIView, UINode, UIText, UIViewSection
from lib.PluginUIDefinitions import TextInput, Button, Progress, Select, SelectOption, Toggle, List, ListRow
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


@pytest.fixture
def ui_actions(monkeypatch):
    cache = {}
    messages = []
    monkeypatch.setattr('lib.ActionManager.KeyValueStore', lambda name: SimpleNamespace(
        get=cache.get, set=cache.__setitem__,
    ))
    monkeypatch.setattr(actions_ui.ActionManager, 'actions', {})
    monkeypatch.setattr(actions_ui, 'plugin_manager', None)
    monkeypatch.setattr(actions_ui, 'event_manager', None)
    monkeypatch.setattr(actions_ui, 'send_message', messages.append)
    action_manager = actions_ui.ActionManager()
    actions_ui.register_ui_actions(action_manager, None)
    return action_manager, messages, cache


def register_upgrade_view(manager, guid='upgrades-guid', title='Am\u00e9liorations'):
    plugin = register(manager, guid)
    plugin.get_ui_views = lambda: [PluginUIView(id='upgrades', label='@runtime.title', sections=[
        UIViewSection(key='route', label='@route.title'),
        UIViewSection(key='session', label='@progress.title', grids=['session'],
                      voice_aliases=["progression de l'am\u00e9lioration du vaisseau", 'suivi des am\u00e9liorations']),
        UIViewSection(key='broker', label='@broker.grid'),
        UIViewSection(key='plans', label='@grid.plans'),
    ])]
    plugin.get_ui_translations = lambda: {
        'en': {'runtime': {'title': 'Ship upgrades'}, 'route': {'title': 'Route'},
               'progress': {'title': 'Progress'}, 'broker': {'grid': 'Unlockable blueprints'},
               'grid': {'plans': 'Plans'}},
        'fr': {'runtime': {'title': title}, 'route': {'title': 'Route'},
               'progress': {'title': 'Progression'}, 'broker': {'grid': 'Plans \u00e0 d\u00e9bloquer'},
               'grid': {'plans': 'Plans'}},
    }
    manager.publish_plugin_ui(plugin)
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


def test_action_notifications_are_scoped_to_owner_and_never_published(manager):
    manager, emitted = manager
    plugin = register(manager, 'alpha')
    result = {'notification': '@added', 'params': {'name': '@literal-user-title'}}
    plugin.on_ui_action = lambda _action, _payload: result
    manager.on_ui_action('alpha', 'add', {}, 'notify')
    assert emitted[-1][1]['result'] == {
        'notification': 'plugin.alpha.added', 'params': {'name': '@literal-user-title'},
    }
    assert result['notification'] == '@added'
    assert 'notification' not in manager.plugin_ui['alpha']


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


def test_navigation_uses_registered_targets_and_validates_sections(manager, ui_actions):
    manager, _ = manager
    register(manager, 'other-guid')
    action_manager, messages, _ = ui_actions
    actions_ui.configure_plugin_ui(manager, action_manager)
    schema = action_manager.actions['showUI']['tool']['function']['parameters']['properties']
    assert 'plugin:other-guid:dashboard' in schema['tab']['enum']
    actions_ui.show_ui({'tab': 'plugin:other-guid:dashboard', 'submenu': 'details'}, {})
    assert messages == [{'type': 'ui', 'show': 'plugin:other-guid:dashboard', 'submenu': 'details'}]
    with pytest.raises(Exception, match='Unknown submenu'):
        actions_ui.show_ui({'tab': 'plugin:other-guid:dashboard', 'submenu': 'missing'}, {})
    manager.plugin_ui = {}
    manager.broadcast_plugin_ui()
    schema = action_manager.actions['showUI']['tool']['function']['parameters']['properties']
    assert 'plugin:other-guid:dashboard' not in schema['tab']['enum']
    with pytest.raises(Exception, match='Unknown tab'):
        actions_ui.show_ui({'tab': 'plugin:other-guid:dashboard'}, {})


@pytest.mark.parametrize('command,section', [
    ('affiche la progression', 'session'),
    ("AFFICHE L'ONGLET PROGRESSION !", 'session'),
    ('montre la progression', 'session'),
    ('ouvre la progression', 'session'),
    ('affiche le sous-onglet progression', 'session'),
    ('affiche la progression des am\u00e9liorations', 'session'),
    ('affiche la progression du module ameliorations', 'session'),
    ("affiche la progression de l'am\u00e9lioration du vaisseau", 'session'),
    ("affiche la progression de l'amelioration du vaisseau", 'session'),
    ("affiche le suivi des am\u00e9liorations", 'session'),
    ("Affiche-moi la progression de l'am\u00e9lioration du vaisseau.", 'session'),
    ("affiche moi la progression de l'amelioration du vaisseau", 'session'),
    ("Montre-moi la progression de l'am\u00e9lioration du vaisseau.", 'session'),
    ('affiche les plans', 'plans'),
    ('affiche les plans \u00e0 d\u00e9bloquer', 'broker'),
    ('affiche les plans a debloquer', 'broker'),
    ('affiche la route des am\u00e9liorations', 'route'),
    ('affiche la route des ameliorations', 'route'),
    ('show progress', 'session'),
    ('show the progress', 'session'),
    ('show me the progress', 'session'),
    ('open plans', 'plans'),
    ('show unlockable blueprints', 'broker'),
    ('show route in ship upgrades', 'route'),
])
def test_localized_upgrade_subtabs_predict_the_exact_tab_and_submenu(manager, ui_actions, command, section):
    manager, _ = manager
    register_upgrade_view(manager)
    action_manager, messages, _ = ui_actions
    actions_ui.configure_plugin_ui(manager, action_manager)
    tools = action_manager.getToolsList('mainship', False, False, True)
    predictions = action_manager.predict_action(command, tools)
    assert predictions is not None and len(predictions) == 1
    assert predictions[0].function.name == 'showUI'
    assert json.loads(predictions[0].function.arguments) == {
        'tab': 'plugin:upgrades-guid:upgrades', 'submenu': section,
    }
    result = action_manager.runAction(predictions[0], {})
    assert not result['content'].startswith('ERROR:')
    assert messages == [{'type': 'ui', 'show': 'plugin:upgrades-guid:upgrades', 'submenu': section}]
    assert action_manager.predict_action(command, action_manager.getToolsList('mainship', True, False, False)) is None


def test_model_sees_localized_labels_mapped_to_section_keys_even_without_action_cache(manager, ui_actions):
    manager, _ = manager
    register_upgrade_view(manager)
    action_manager, _, cache = ui_actions
    actions_ui.configure_plugin_ui(manager, action_manager)
    properties = action_manager.actions['showUI']['tool']['function']['parameters']['properties']
    assert 'Ship upgrades / Am\u00e9liorations' in properties['tab']['description']
    assert 'session = Progress / Progression' in properties['tab']['description']
    assert 'broker = Unlockable blueprints / Plans \u00e0 d\u00e9bloquer' in properties['tab']['description']
    assert 'paired with the owning tab' in properties['submenu']['description']
    previous_count = len(cache)
    manager.broadcast_plugin_ui()
    assert len(cache) == previous_count
    tools = action_manager.getToolsList('mainship', False, False, True)
    for command in ('ne montre pas la progression', 'comment afficher la progression',
                    'calcule la route des ameliorations', 'commence les ameliorations'):
        assert action_manager.predict_action(command, tools) is None
    for command, args in actions_ui.SHOW_UI_PREFILLS.items():
        prediction = action_manager.predict_action(command, tools)
        assert prediction is not None
        assert json.loads(prediction[0].function.arguments) == args


@pytest.mark.parametrize('cache_enabled', [False, True])
def test_explicit_display_opens_the_plugin_before_state_queries_and_keeps_the_followup_summary(
    manager, ui_actions, monkeypatch, cache_enabled,
):
    from lib.Assistant import Assistant
    from lib.Logger import PromptUsageStats

    manager, _ = manager
    register_upgrade_view(manager)
    action_manager, messages, cache = ui_actions
    actions_ui.configure_plugin_ui(manager, action_manager)
    cache.clear()
    command = "Affiche-moi la progression de l'am\u00e9lioration du vaisseau."
    state_query = Mock(return_value='Plan progress')
    action_manager.registerAction('plugin_state', 'Read state', {'type': 'object', 'properties': {}},
                                  state_query, 'ship', cache_prefill={command: {}})
    user_event = ConversationEvent(kind='user', content=command, responded_at=None)
    event_manager = Mock()
    event_manager.get_short_term_memory.return_value = [user_event]
    event_manager.get_latest_memories.return_value = []
    assistant = Assistant.__new__(Assistant)
    assistant.is_replying = False
    assistant.config = {
        'game_actions_var': True, 'web_search_actions_var': False,
        'ui_actions_var': True, 'use_action_cache_var': cache_enabled,
    }
    assistant.event_manager = event_manager
    assistant.action_manager = action_manager
    assistant.llmModel = Mock()
    assistant.tts = Mock()
    assistant.prompt_generator = Mock()
    assistant.prompt_generator.generate_prompt.return_value = (
        [{'role': 'user', 'content': command}], PromptUsageStats(),
    )
    assistant._get_tts_postprocessing_layers = Mock(return_value=[])
    assistant.verify_action = Mock()
    cache_usage = Mock()
    monkeypatch.setattr('lib.Assistant.log_action_cache_usage', cache_usage)
    monkeypatch.setattr('lib.Assistant.log_llm_usage', Mock())
    states = {'CurrentStatus': {'flags': {'InMainShip': True}, 'flags2': {}}}

    assistant.reply_thread(states)

    assert messages == [{'type': 'ui', 'show': 'plugin:upgrades-guid:upgrades', 'submenu': 'session'}]
    assistant.llmModel.generate.assert_not_called()
    state_query.assert_not_called()
    assistant.verify_action.assert_not_called()
    cache_usage.assert_not_called()
    request, results, _ = event_manager.add_tool_call.call_args.args
    assert request[0]['function']['name'] == 'showUI'
    assert not results[0]['content'].startswith('ERROR:')
    user_event.responded_at = 1.0
    tool_event = ToolEvent(request=request, results=results, responded_at=None)
    event_manager.get_short_term_memory.return_value = [tool_event, user_event]
    summary = 'Quarante-sept niveaux sur quatre-vingt-quatorze valid\u00e9s.'
    assistant.llmModel.generate.return_value = (summary, [], None)

    assistant.reply_thread(states)

    assert len(messages) == 1
    assistant.llmModel.generate.assert_called_once()
    assistant.tts.say.assert_called_once_with(summary, context='assistant', postprocessing_layers=[])
    event_manager.add_assistant_complete_event.assert_called_once()


def test_direct_display_resolver_respects_ui_permissions_negation_and_ambiguity(manager, ui_actions):
    manager, _ = manager
    register_upgrade_view(manager)
    action_manager, messages, _ = ui_actions
    actions_ui.configure_plugin_ui(manager, action_manager)
    disabled_tools = action_manager.getToolsList('mainship', True, False, False)
    command = "affiche-moi la progression de l'am\u00e9lioration du vaisseau"
    assert actions_ui.predict_plugin_ui_action(command, action_manager, disabled_tools) is None
    tools = action_manager.getToolsList('mainship', True, False, True)
    for query in ('ne montre pas la progression', 'ne m\'affiche pas la progression',
                  'comment afficher la progression', 'quelle est la progression',
                  'calcule la route des ameliorations'):
        assert actions_ui.predict_plugin_ui_action(query, action_manager, tools) is None
    register_upgrade_view(manager, guid='exploration', title='Exploration')
    tools = action_manager.getToolsList('mainship', True, False, True)
    assert actions_ui.predict_plugin_ui_action(command, action_manager, tools) is None
    assert actions_ui.predict_plugin_ui_action('affiche-moi la progression', action_manager, tools) is None
    prediction = actions_ui.predict_plugin_ui_action(
        'affiche-moi la progression du module exploration', action_manager, tools,
    )
    assert prediction is not None
    action_manager.runAction(prediction[0], {})
    assert messages == [{'type': 'ui', 'show': 'plugin:exploration:upgrades', 'submenu': 'session'}]
    manager.plugin_ui = {}
    manager.broadcast_plugin_ui()
    assert actions_ui.predict_plugin_ui_action(command, action_manager, tools) is None


def test_system_prompt_requires_display_and_allows_ambiguity_clarification():
    from lib.PromptGenerator import PromptGenerator

    generator = PromptGenerator.__new__(PromptGenerator)
    generator.commander_name = 'Commander'
    generator.character_prompt = 'Assist {commander_name}.'
    generator.registered_prompt_event_handlers = []
    generator.generate_status_message = Mock(return_value='Current ship status')
    event = ConversationEvent(kind='user', content='Show progress')
    prompt, _ = generator.generate_prompt(events=[event], projected_states={}, pending_events=[event], memories=[])
    system = next(message['content'] for message in prompt if message['role'] == 'system')
    assert 'opening that panel with showUI' in system
    assert 'a spoken summary alone does not fulfill it' in system
    assert 'summarize its state after opening it' in system
    assert 'Ask a short clarification question' in system
    assert 'without executing it or changing the UI until clarified' in system
    assert 'You do not ask questions or initiate conversations' not in system


def test_ambiguous_subtab_names_need_qualification_and_removed_views_cannot_be_predicted(manager, ui_actions):
    manager, _ = manager
    register_upgrade_view(manager)
    action_manager, _, _ = ui_actions
    actions_ui.configure_plugin_ui(manager, action_manager)
    tools = action_manager.getToolsList('mainship', False, False, True)
    assert action_manager.predict_action('affiche la progression', tools) is not None
    register_upgrade_view(manager, guid='other-guid', title='Exploration')
    tools = action_manager.getToolsList('mainship', False, False, True)
    assert action_manager.predict_action('affiche la progression', tools) is None
    for title, guid in [('ameliorations', 'upgrades-guid'), ('exploration', 'other-guid')]:
        prediction = action_manager.predict_action(f'affiche la progression du module {title}', tools)
        assert prediction is not None
        assert json.loads(prediction[0].function.arguments) == {'tab': f'plugin:{guid}:upgrades', 'submenu': 'session'}
    del manager.plugin_ui['other-guid']
    manager.broadcast_plugin_ui()
    tools = action_manager.getToolsList('mainship', False, False, True)
    assert action_manager.predict_action('affiche la progression', tools) is not None
    manager.plugin_ui = {}
    manager.broadcast_plugin_ui()
    tools = action_manager.getToolsList('mainship', False, False, True)
    assert action_manager.predict_action('affiche la progression', tools) is None
    assert action_manager.predict_action('affiche la progression du module exploration', tools) is None
    assert action_manager.predict_action('show route', tools) is not None


@pytest.mark.parametrize('aliases', [
    ('progr\u00e8s', 'progres'),
    ('progression', 'progr\u00e8s'),
])
def test_multiple_plugin_views_require_semantic_resolution_or_explicit_qualification(manager, ui_actions, aliases):
    manager, _ = manager
    action_manager, messages, _ = ui_actions
    for guid, title, alias in zip(('fleet', 'exploration'), ('Fleet', 'Exploration'), aliases):
        plugin = register(manager, guid)
        plugin.plugin_manifest.name = f'{title} extension'
        view = PluginUIView(id='overview', label=title, sections=[
            UIViewSection(key='progress', label=f'{title} report', voice_aliases=[alias]),
        ])
        plugin.get_ui_views = lambda view=view: [view]
        manager.publish_plugin_ui(plugin)
        manager.plugin_list[f'{guid}.entrypoint'] = manager.plugin_list.pop(guid)
    actions_ui.configure_plugin_ui(manager, action_manager)
    tools = action_manager.getToolsList('mainship', False, False, True)
    function = action_manager.actions['showUI']['tool']['function']
    assert 'ask the player which plugin, view or subtab' in function['description']
    assert 'Do not call this tool or change the UI until the player clarifies' in function['description']
    assert 'Never guess from plugin order, the current tab or similar aliases' in function['description']
    for title in ('Fleet', 'Exploration'):
        assert f'Owner plugin: {title} extension' in function['parameters']['properties']['tab']['description']
        assert action_manager.predict_action(f'open {title}', tools) is None
    for alias in aliases:
        for variant in (alias, alias.replace('\u00e8', 'e')):
            assert action_manager.predict_action(f'affiche les {variant}', tools) is None
            assert action_manager.predict_action(f'show {variant}', tools) is None
    assert messages == []
    for guid, title, alias in zip(('fleet', 'exploration'), ('Fleet', 'Exploration'), aliases):
        prediction = action_manager.predict_action(f'affiche les {alias} du module {title}', tools)
        assert prediction is not None
        assert json.loads(prediction[0].function.arguments) == {'tab': f'plugin:{guid}:overview', 'submenu': 'progress'}
        action_manager.runAction(prediction[0], {})
        assert messages[-1] == {'type': 'ui', 'show': f'plugin:{guid}:overview', 'submenu': 'progress'}
    del manager.plugin_ui['exploration']
    manager.broadcast_plugin_ui()
    tools = action_manager.getToolsList('mainship', False, False, True)
    assert action_manager.predict_action(f'affiche les {aliases[0]}', tools) is not None


@pytest.mark.parametrize('separate_plugins', [False, True])
def test_accent_variants_never_resolve_an_alias_collision_even_with_a_shared_view_qualifier(
    manager, ui_actions, separate_plugins,
):
    manager, _ = manager
    action_manager, messages, _ = ui_actions
    for index, alias in enumerate(('progr\u00e8s', 'progres')):
        guid = f'plugin-{index}' if separate_plugins else 'single-plugin'
        plugin = manager.plugin_list.get(guid) or register(manager, guid)
        section = UIViewSection(key=f'section-{index}', label=f'Report {index}', voice_aliases=[alias])
        if separate_plugins or index == 0:
            view = PluginUIView(id='overview', label='Overview', sections=[section])
            plugin.get_ui_views = lambda view=view: [view]
        else:
            plugin.get_ui_views()[0]['sections'].append(section)
        manager.publish_plugin_ui(plugin)
    actions_ui.configure_plugin_ui(manager, action_manager)
    tools = action_manager.getToolsList('mainship', False, False, True)
    for alias in ('progr\u00e8s', 'progres'):
        for suffix in ('', ' du module Overview'):
            assert action_manager.predict_action(f'affiche les {alias}{suffix}', tools) is None
        assert action_manager.predict_action(f'show {alias} in Overview', tools) is None
    assert messages == []
    prediction = action_manager.predict_action('show Report 0 in Overview', tools)
    assert prediction is not None
    assert json.loads(prediction[0].function.arguments) == {
        'tab': 'plugin:plugin-0:overview' if separate_plugins else 'plugin:single-plugin:overview',
        'submenu': 'section-0',
    }


@pytest.mark.parametrize('command,expanded,index', [
    ('d\u00e9ploie la deuxi\u00e8me section', True, 2),
    ('deploie la 2e section', True, 2), ('ouvre la section 2', True, 2),
    ('replie la premi\u00e8re section', False, 1),
    ('rabats la deuxieme section', False, 2),
    ('expand the second section', True, 2), ('collapse section 3', False, 3),
])
def test_section_commands_wait_for_the_real_ui_acknowledgement(manager, ui_actions, monkeypatch, command, expanded, index):
    manager, _ = manager
    register_upgrade_view(manager)
    action_manager, _, _ = ui_actions
    actions_ui.configure_plugin_ui(manager, action_manager)
    messages = []

    def respond(message):
        messages.append(message)
        request = message['section']
        actions_ui.handle_ui_section_result({
            'request_id': request['request_id'], 'success': True, 'expanded': request['expanded'], 'label': 'Core Internal',
        })

    monkeypatch.setattr(actions_ui, 'send_message', respond)
    tools = action_manager.getToolsList('mainship', False, False, True)
    prediction = action_manager.predict_action(command, tools)
    assert prediction is not None
    assert prediction[0].function.name == 'setUISectionExpanded'
    assert json.loads(prediction[0].function.arguments) == {'expanded': expanded, 'index': index}
    result = action_manager.runAction(prediction[0], {})
    assert ('expanded' if expanded else 'collapsed') in result['content']
    assert messages[0]['section']['index'] == index
    assert not actions_ui._section_requests


def test_collapsible_section_catalog_translates_groups_and_keeps_index_commands_available(manager, ui_actions):
    manager, _ = manager
    plugin = register_upgrade_view(manager)
    translations = plugin.get_ui_translations()
    translations['en']['category'] = {'core': 'Core Internal'}
    translations['fr']['category'] = {'core': 'Compartiments essentiels'}
    plugin.get_ui_translations = lambda: translations
    plugin.settings_config['grids'] = [
        SettingsGrid(key='session', label='@progress.title', collapsible=True, fields=[
            UIList(key='modules', type='list', items=[{'key': 'reactor', 'title': 'Power Plant', 'group': '@category.core'}]),
        ]),
    ]
    manager.publish_plugin_ui(plugin)
    action_manager, _, _ = ui_actions
    actions_ui.configure_plugin_ui(manager, action_manager)
    description = action_manager.actions['setUISectionExpanded']['tool']['function']['parameters']['properties']['name']['description']
    assert 'plugin:upgrades-guid:upgrades / session' in description
    assert 'Core Internal / Compartiments essentiels' in description
    assert 'session = Progress / Progression' in description
    tools = action_manager.getToolsList('mainship', False, False, True)
    assert action_manager.predict_action('deploie la 2e section', tools) is not None
    manager.broadcast_plugin_ui()
    assert action_manager.predict_action('replie la section 2', tools) is not None

@pytest.mark.parametrize('arguments', [
    {}, {'expanded': True}, {'expanded': 'true', 'index': 1},
    {'expanded': True, 'index': 0}, {'expanded': True, 'index': True},
    {'expanded': True, 'index': 1.5}, {'expanded': True, 'name': ''},
    {'expanded': True, 'name': 'core', 'index': 1},
])
def test_invalid_section_controls_do_not_emit_ui_messages(monkeypatch, arguments):
    messages = []
    monkeypatch.setattr(actions_ui, 'send_message', messages.append)
    with pytest.raises(ValueError):
        actions_ui.set_ui_section_expanded(arguments, {})
    assert not messages and not actions_ui._section_requests


def test_missing_failed_or_malformed_section_acknowledgements_are_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(actions_ui, '_section_timeout', 0)
    monkeypatch.setattr(actions_ui, 'send_message', lambda message: None)
    with pytest.raises(TimeoutError, match='not confirm'):
        actions_ui.set_ui_section_expanded({'expanded': True, 'index': 2}, {})
    assert not actions_ui._section_requests
    for result, error in [
        ({'success': False, 'error': 'Section not found'}, 'Section not found'),
        ({'success': True, 'expanded': False, 'label': 'Core'}, 'Invalid UI section'),
    ]:
        monkeypatch.setattr(actions_ui, 'send_message', lambda message: actions_ui.handle_ui_section_result({
            'request_id': message['section']['request_id'], **result,
        }))
        with pytest.raises(ValueError, match=error):
            actions_ui.set_ui_section_expanded({'expanded': True, 'name': 'Compartiments essentiels'}, {})
        assert not actions_ui._section_requests


def test_application_without_plugins_has_no_views(manager):
    manager, emitted = manager
    manager.register_settings()
    assert manager.get_ui_targets() == {}
    assert next(payload for kind, payload in emitted if kind == 'plugin_ui') == {'plugins': {}}


def test_voice_navigation_and_scrolling_use_shared_ui_messages(monkeypatch):
    messages = []
    monkeypatch.setattr(actions_ui, 'send_message', messages.append)
    monkeypatch.setattr(actions_ui, 'plugin_manager', None)
    actions_ui.show_ui({'tab': 'navigation', 'submenu': 'route'}, {})
    for direction in ('down', 'up', 'top', 'bottom'):
        actions_ui.scroll_ui({'direction': direction}, {})
    assert messages == [
        {'type': 'ui', 'show': 'navigation', 'submenu': 'route'},
        *({'type': 'ui', 'scroll': direction} for direction in ('down', 'up', 'top', 'bottom')),
    ]


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


def test_plugin_can_reset_a_declared_input_without_persistence_or_callbacks(manager, monkeypatch):
    manager, emitted = manager
    plugin = register_unified(manager)
    other = register_unified(manager, 'other')
    saved = []
    monkeypatch.setattr('lib.PluginManager.save_config', lambda config: saved.append(deepcopy(config)))
    manager.on_ui_action('unified', 'ui_changed', {'key': 'search', 'value': 'filter'}, 'filter')
    changes = deepcopy(plugin.changes)
    emitted.clear()
    plugin.set_ui_value('search', '')
    plugin.set_ui_value('transient', 'cleared')
    assert plugin.get_ui_state()['search'] == ''
    assert plugin.get_ui_state()['transient'] == 'cleared'
    assert other.get_ui_state()['transient'] == 'view only'
    assert plugin.changes == changes
    assert plugin.settings == {} and saved == [] and emitted == []
    plugin.publish_ui()
    assert manager.plugin_ui['unified']['state']['search'] == ''
    assert manager.plugin_ui['unified']['state']['transient'] == 'cleared'
    for key in ('missing', 'refresh', 'progress'):
        with pytest.raises(ValueError, match='common.invalidAction'):
            plugin.set_ui_value(key, '')
    plugin.model_providers[0]['settings_config'][0]['fields'][0]['readonly'] = True
    with pytest.raises(ValueError, match='common.invalidAction'):
        plugin.set_ui_value('enabled', True)


def test_list_summary_uses_the_shared_input_state_and_callback(manager):
    manager, emitted = manager
    plugin = register_unified(manager)
    views = plugin.get_ui_views()
    views[0]['sections'][0]['content'].append(List(type='list', items=[
        ListRow(key='item', title='Item', summary=[
            TextInput(key='nested', type='text', default_value='initial', min_length=None, max_length=None),
        ]),
    ]))
    plugin.get_ui_views = lambda: views
    plugin.publish_ui()
    assert manager.plugin_ui['unified']['state']['nested'] == 'initial'
    manager.on_ui_action('unified', 'ui_changed', {'key': 'nested', 'value': 'changed'}, 'summary-input')
    assert emitted[-1][1]['success'] is True
    assert plugin.changes[-1][:2] == ('nested', 'changed')
    plugin.set_ui_value('nested', 'reset')
    plugin.publish_ui()
    assert manager.plugin_ui['unified']['state']['nested'] == 'reset'
    assert plugin.settings == {}


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
