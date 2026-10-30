from copy import deepcopy
import json
import threading
import unicodedata
import uuid

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_function_tool_call import Function
from pydantic import BaseModel

from ..ActionManager import ActionManager
from ..EventManager import EventManager
from ..UI import send_message
from ..Logger import log
from ..Projections import get_state_dict, ProjectedStates
from typing import Optional

event_manager: Optional[EventManager] = None
plugin_manager = None
_section_requests: dict[str, tuple[threading.Event, dict]] = {}
_section_lock = threading.Lock()
_section_timeout = 5


def _section_prefills():
    phrases = {}
    for index, fr, en in ((1, 'premi\u00e8re', 'first'), (2, 'deuxi\u00e8me', 'second'),
                          (3, 'troisi\u00e8me', 'third'), (4, 'quatri\u00e8me', 'fourth'),
                          (5, 'cinqui\u00e8me', 'fifth')):
        for expanded, verbs in ((True, ('d\u00e9ploie', 'ouvre')), (False, ('replie', 'rabats', 'ferme'))):
            for verb in verbs:
                for phrase in (f'{verb} la section {index}', f'{verb} la {index}e section', f'{verb} la {fr} section'):
                    for variant in (phrase, ''.join(char for char in unicodedata.normalize('NFKD', phrase)
                                                   if not unicodedata.combining(char))):
                        phrases[variant] = {'expanded': expanded, 'index': index}
        for expanded, verb in ((True, 'expand'), (True, 'open'), (False, 'collapse'), (False, 'close')):
            for phrase in (f'{verb} section {index}', f'{verb} the {en} section'):
                phrases[phrase] = {'expanded': expanded, 'index': index}
    return phrases

SHOW_UI_PREFILLS = {
    **{f"show {tab}": {"tab": tab} for tab in (
        "chat", "status", "navigation", "storage", "tasks", "logbook", "search", "actions",
    )},
    **{
        f"show {submenu.replace('-', ' ')}": {"tab": tab, "submenu": submenu}
        for tab, submenus in {
            "navigation": ("location", "list", "route"),
            "storage": ("colonisation", "cargo", "carriers", "materials", "raw material",
                        "manufactured material", "encoded material", "locker", "engineers",
                        "blueprints", "modules", "ships"),
            "tasks": ("missions", "quests", "community-goals"),
        }.items()
        for submenu in submenus
    },
}


def _navigation_labels(manager, target: str, label: str) -> dict[str, str]:
    guid = target.split(':', 2)[1]
    prefix = f'plugin.{guid}.'
    if not label.startswith(prefix):
        return {'en': label, 'fr': label}
    labels = {}
    for language, translations in manager.plugin_ui[guid]['translations'].items():
        value = translations
        for segment in label.removeprefix(prefix).split('.'):
            value = value.get(segment) if isinstance(value, dict) else None
        if isinstance(value, str) and value:
            labels[language] = value
    return labels


def _navigation_key(action_manager, name):
    return action_manager.clean_user_input(''.join(
        char for char in unicodedata.normalize('NFKD', name) if not unicodedata.combining(char)
    ))


def _plugin_navigation_prefills(action_manager, targets, labels, section_labels):
    candidates: dict[str, dict[str, str] | None] = {}
    phrases: dict[str, dict[str, str]] = {}
    reserved = {_navigation_key(action_manager, name) for name in (
        *SHOW_UI_PREFILLS,
        *(args.get('submenu', args['tab']) for args in SHOW_UI_PREFILLS.values()),
    )}

    def add(names, arguments, qualified=False):
        for language, name in names.items():
            language = language.split('-')[0].split('_')[0]
            prefixes = (
                (*(
                    f"{verb} {article}"
                    for verb in ('affiche', 'affiche-moi', 'affiche moi', 'montre', 'montre-moi', 'montre moi',
                                 'ouvre', 'ouvre-moi', 'ouvre moi')
                    for article in ('', 'le ', 'la ', 'les ', "l'")
                ), "affiche l'onglet ", "affiche le sous-onglet ")
                if language == 'fr' else ("show ", "show the ", "show me ", "show me the ",
                                          "open ", "open the ", "show the subtab ")
                if language == 'en' else ()
            )
            for variant in (name, ''.join(char for char in unicodedata.normalize('NFKD', name)
                                          if not unicodedata.combining(char))):
                for prefix in prefixes:
                    phrase = prefix + variant
                    key = _navigation_key(action_manager, phrase)
                    if key not in candidates:
                        candidates[key] = arguments
                    elif candidates[key] != arguments:
                        candidates[key] = None
                    if qualified or len(targets) == 1:
                        phrases[phrase] = arguments

    for target, view in targets.items():
        add(labels[target], {'tab': target})
        for alias in view.get('voice_aliases', []):
            add({'en': alias, 'fr': alias}, {'tab': target})
        for section in view['sections']:
            arguments = {'tab': target, 'submenu': section['key']}
            names = [section_labels[target, section['key']],
                     *({'en': alias, 'fr': alias} for alias in section.get('voice_aliases', []))]
            for localized in names:
                add({language: name for language, name in localized.items()
                     if _navigation_key(action_manager, name) not in reserved}, arguments)
                for language, name in localized.items():
                    view_name = labels[target].get(language)
                    if view_name:
                        for joiner in (' des ', ' du module ') if language.startswith('fr') else (' in ', ' of '):
                            add({language: name + joiner + view_name}, arguments, qualified=True)
    return {phrase: arguments for phrase, arguments in phrases.items()
            if _navigation_key(action_manager, phrase) not in reserved
            and candidates[_navigation_key(action_manager, phrase)] == arguments}


def predict_plugin_ui_action(
    user_input: str, action_manager: ActionManager, tools: list,
) -> list[ChatCompletionMessageFunctionToolCall] | None:
    if plugin_manager is None or not any(tool['function']['name'] == 'showUI' for tool in tools):
        return None
    targets = plugin_manager.get_ui_targets()
    labels = {target: _navigation_labels(plugin_manager, target, view['label']) for target, view in targets.items()}
    section_labels = {(target, section['key']): _navigation_labels(plugin_manager, target, section['label'])
                      for target, view in targets.items() for section in view['sections']}
    key = _navigation_key(action_manager, user_input)
    for phrase, arguments in _plugin_navigation_prefills(action_manager, targets, labels, section_labels).items():
        if _navigation_key(action_manager, phrase) == key:
            log('debug', 'Explicit plugin display request:', user_input, arguments)
            return [ChatCompletionMessageFunctionToolCall(
                type='function', id=str(uuid.uuid4()),
                function=Function(name='showUI', arguments=json.dumps(arguments)),
            )]
    return None


def configure_plugin_ui(manager, action_manager):
    global plugin_manager
    plugin_manager = manager
    manager.ui_action_manager = action_manager
    targets = manager.get_ui_targets()
    _configure_section_names(manager, action_manager, targets)
    function = action_manager.actions['showUI']['tool']['function']
    parameters = deepcopy(function['parameters'])
    properties = parameters['properties']
    properties['tab']['enum'] = [
        'chat', 'status', 'navigation', 'storage', 'station', 'tasks', 'logbook', 'search', 'actions', *targets,
    ]
    properties['submenu']['enum'] = sorted({
        'location', 'list', 'route', 'colonisation', 'cargo', 'carriers', 'materials',
        'raw material', 'manufactured material', 'encoded material', 'locker', 'engineers',
        'blueprints', 'modules', 'ships', 'missions', 'quests', 'community-goals',
        *(section['key'] for view in targets.values() for section in view['sections']),
    })
    labels = {target: _navigation_labels(manager, target, view['label']) for target, view in targets.items()}
    section_labels = {(target, section['key']): _navigation_labels(manager, target, section['label'])
                      for target, view in targets.items() for section in view['sections']}
    plugin_names = {plugin.plugin_manifest.guid: plugin.plugin_manifest.name for plugin in manager.plugin_list.values()}
    descriptions = '; '.join(
        f"{target}: {' / '.join(dict.fromkeys(labels[target].values())) or view['label']}. "
        f"Owner plugin: {plugin_names[target.split(':', 2)[1]]}. "
        f"{view.get('description', '')} Voice aliases: {', '.join(view.get('voice_aliases', []))}. Submenus: " + ', '.join(
            f"{section['key']} = {' / '.join(dict.fromkeys(section_labels[target, section['key']].values())) or section['label']}"
            f" (voice aliases: {', '.join(section.get('voice_aliases', []))})"
            for section in view['sections'])
        for target, view in targets.items()
    )
    properties['tab']['description'] = (
        'Built-in application panels and registered plugin views. ' + descriptions
    )
    properties['submenu']['description'] = (
        'Select a subtab using its key, paired with the owning tab. '
        'The plugin labels and their keys are listed in the tab description. '
        'For a display request use showUI, not a plugin operation that calculates or modifies data.'
    )
    if parameters == function['parameters']:
        return
    action_manager.registerAction(
        'showUI', function['description'], parameters, show_ui, 'ui',
        cache_prefill={**SHOW_UI_PREFILLS, **_plugin_navigation_prefills(action_manager, targets, labels, section_labels)},
    )


def _configure_section_names(manager, action_manager, targets):
    action = action_manager.actions.get('setUISectionExpanded')
    if action is None:
        return
    names = []
    for target, view in targets.items():
        guid = target.split(':', 2)[1]
        grids = {grid['key']: grid for grid in manager.plugin_settings_configs.get(guid, {}).get('grids', [])}
        for section in view['sections']:
            labels: dict[str, str] = {}

            def collect(node):
                if isinstance(node, list):
                    for child in node:
                        collect(child)
                elif isinstance(node, dict):
                    if node.get('collapsible'):
                        labels[node['key']] = node.get('label', node['key'])
                    for row in node.get('items', []):
                        if row.get('group'):
                            labels[row['group']] = row['group']
                        if node.get('details_collapsible') and row.get('details'):
                            labels[row['key']] = row.get('title_key', row.get('title', row['key']))
                    for key in ('fields', 'content', 'children', 'details'):
                        collect(node.get(key, []))

            collect(section.get('content', []))
            for key in section.get('grids', []):
                collect(grids.get(key, {}))
            if labels:
                names.append(f"{target} / {section['key']}: " + ', '.join(
                    f"{key} = {' / '.join(dict.fromkeys(_navigation_labels(manager, target, label).values())) or label}"
                    for key, label in labels.items()))
    function = action['tool']['function']
    parameters = deepcopy(function['parameters'])
    parameters['properties']['name']['description'] = (
        'Section name or key, not a tab. Match the user meaning across languages using these available sections: '
        + '; '.join(names)
    )
    if parameters != function['parameters']:
        action_manager.registerAction('setUISectionExpanded', function['description'], parameters,
                                      set_ui_section_expanded, 'ui', cache_prefill=_section_prefills())


def handle_ui_section_result(message: dict) -> None:
    request_id = message.get('request_id')
    if not isinstance(request_id, str):
        raise ValueError('Missing UI section request ID.')
    with _section_lock:
        pending = _section_requests.get(request_id)
        if pending is None:
            log('warn', 'Ignoring an outdated UI section result.')
            return
        pending[1].update(message)
        pending[0].set()


def set_ui_section_expanded(obj, projected_states):
    obj = obj or {}
    expanded, name, index = obj.get('expanded'), obj.get('name'), obj.get('index')
    if not isinstance(expanded, bool):
        raise ValueError('expanded must be a boolean.')
    if (name is None) == (index is None):
        raise ValueError('Specify exactly one section name or one-based index.')
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValueError('The section name must be nonempty.')
    if index is not None and (isinstance(index, bool) or not isinstance(index, int) or index < 1):
        raise ValueError('Section indices start at 1 and must be integers.')
    request_id = uuid.uuid4().hex
    event = threading.Event()
    result = {}
    with _section_lock:
        _section_requests[request_id] = (event, result)
    try:
        send_message({'type': 'ui', 'section': {
            'request_id': request_id, 'expanded': expanded,
            **({'name': name.strip()} if name is not None else {'index': index}),
        }})
        if not event.wait(_section_timeout):
            raise TimeoutError('The UI did not confirm the section change. No success can be confirmed.')
        if result.get('success') is not True:
            raise ValueError(result.get('error', 'The UI could not find or change the requested section.'))
        if result.get('expanded') is not expanded or not isinstance(result.get('label'), str):
            raise ValueError('Invalid UI section acknowledgement.')
        return f"Section {result['label']} is now {'expanded' if expanded else 'collapsed'}."
    finally:
        with _section_lock:
            _section_requests.pop(request_id, None)

# Checking status projection to exit game actions early if not applicable
def checkStatus(projected_states: ProjectedStates, blocked_status_dict: dict[str, bool]):
    current_status = get_state_dict(projected_states, 'CurrentStatus')

    if current_status:
        # Convert BaseModel to dict for flag checking
        status_dict = current_status.model_dump() if hasattr(current_status, 'model_dump') else current_status
        for blocked_status, expected_value in blocked_status_dict.items():
            for flag_group in ['flags', 'flags2']:
                flags = status_dict.get(flag_group, {})
                if flags and blocked_status in flags:
                    if flags[blocked_status] == expected_value:
                        raise Exception(f"Action not possible due to {'not ' if not expected_value else ''}being in a state of {blocked_status}!")


def show_ui(obj, projected_states):
    """Show a specific UI tab, optionally selecting one of its supported submenus."""
    tab: str = (obj or {}).get('tab', 'chat')
    submenu: str | None = (obj or {}).get('submenu')
    material_submenu_aliases = {
        "raw_material": "raw material",
        "manufactured_material": "manufactured material",
        "encoded_material": "encoded material",
    }
    if submenu:
        submenu = material_submenu_aliases.get(submenu, submenu)
    valid_tabs = {"chat", "status", "navigation", "storage", "station", "tasks", "logbook", "search", "actions"}
    targets = plugin_manager.get_ui_targets() if plugin_manager is not None else {}
    valid_tabs.update(targets)
    valid_submenus = {
        "navigation": {"location", "list", "route"},
        "storage": {"colonisation", "cargo", "carriers", "materials", "raw material", "manufactured material", "encoded material", "locker", "engineers", "blueprints", "modules", "ships"},
        "tasks": {"missions", "quests", "community-goals"},
    }
    for target, view in targets.items():
        valid_submenus[target] = {section['key'] for section in view['sections']}

    if tab not in valid_tabs:
        raise Exception(f"Unknown tab '{tab}'. Expected one of: {', '.join(sorted(valid_tabs))}.")
    if submenu and submenu not in valid_submenus.get(tab, set()):
        raise Exception(f"Unknown submenu '{submenu}' for {tab}.")

    # Guard for station tab when not docked
    if tab == 'station':
        checkStatus(projected_states, {'Docked': False})

    message = {
        "type": "ui",
        "show": tab,
    }
    if submenu:
        message["submenu"] = submenu
    send_message(message)

    return f"{tab.capitalize()}{f' ({submenu})' if submenu else ''} is now being displayed"


def scroll_ui(obj, projected_states):
    """Scroll the currently displayed UI tab."""
    direction: str = (obj or {}).get('direction', 'down')
    valid_directions = {"top", "up", "down", "bottom"}
    if direction not in valid_directions:
        raise Exception(f"Unknown scroll direction '{direction}'. Expected one of: {', '.join(sorted(valid_directions))}.")

    send_message({
        "type": "ui",
        "scroll": direction,
    })
    return f"Scrolled {direction}"


def register_ui_actions(actionManager: ActionManager, eventManager: EventManager):
    global event_manager, plugin_manager
    event_manager = eventManager
    plugin_manager = None

    actionManager.registerAction(
        'setUISectionExpanded',
        "Expand or collapse a collapsible section in the currently selected tab/subtab, without changing its data. "
        "Understand business names and synonyms regardless of the interface language. "
        "Use name for the section's name/key, or index for its one-based order among currently visible section headers "
        "(for example 'deploie la deuxieme section', 'replie la section 2', 'expand the second section'). "
        "expanded=true opens; expanded=false closes. First select the requested tab/subtab with showUI if needed. "
        "This applies to accordion panels, list categories and expandable row details. "
        "It waits for UI confirmation and reports missing, ambiguous or out-of-range sections explicitly.",
        {'type': 'object', 'properties': {
            'expanded': {'type': 'boolean'},
            'name': {'type': 'string', 'description': 'Section name or key in any registered language.'},
            'index': {'type': 'integer', 'minimum': 1, 'description': 'One-based section header number in the active subtab.'},
        }, 'required': ['expanded']},
        set_ui_section_expanded, 'ui',
        cache_prefill=_section_prefills(),
    )
    actionManager.registerAction(
        'showUI',
        "Show a COVAS interface tab or submenu, such as ship status, navigation, cargo, materials, missions, station information, or the logbook. "
        "This only changes the visible panel; "
        "it does not calculate or prepare routes, search stations, or plot navigation. "
        "Use the relevant registered operation to prepare data before displaying it. "
        "An explicit display/open request for an available panel requires this tool, even if a status-reading tool "
        "could provide a useful spoken summary. A summary is optional and never replaces opening the requested panel. "
        "Do not require a separate request to open the panel after reporting its state. "
        "Compare the user's meaning with all registered plugin views, subtabs and voice aliases. "
        "If more than one target is plausible and the user has not clearly identified one, "
        "ask the player which plugin, view or subtab they mean, naming the alternatives in their language. "
        "Do not call this tool or change the UI until the player clarifies. "
        "Never guess from plugin order, the current tab or similar aliases.",
        {
            "type": "object",
            "properties": {
                "tab": {
                    "type": "string",
                    "description": "Chat: current conversation; Status: ship/suit loadout and state; Navigation: current system information; Storage: colony construction, materials and engineers; Station: outfitting and market info of docked station; Tasks: active missions and objectives; Logbook: user history and memories; Search: manual search agent and results",
                    "enum": ["chat", "status", "navigation", "storage", "station", "tasks", "logbook", "search", "actions"],
                },
                "submenu": {
                    "type": "string",
                    "description": "Optional submenu. Navigation: location, list, route. Storage: colonisation, cargo, carriers, materials (all material types), raw material, manufactured material, encoded material, locker, engineers, blueprints, modules, ships. Tasks: missions, quests, community-goals.",
                    "enum": ["location", "list", "route", "colonisation", "cargo", "carriers", "materials", "raw material", "manufactured material", "encoded material", "locker", "engineers", "blueprints", "modules", "ships", "missions", "quests", "community-goals"],
                },
            },
            "required": ["tab"]
        },
        show_ui,
        'ui',
        cache_prefill=SHOW_UI_PREFILLS,
    )
    actionManager.registerAction(
        'scrollUI',
        "Scroll the currently displayed COVAS interface up or down, or jump to the top or bottom.",
        {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "Where to scroll the current tab",
                    "enum": ["top", "up", "down", "bottom"],
                },
            },
            "required": ["direction"],
        },
        scroll_ui,
        'ui',
        cache_prefill={
            "scroll to top": {"direction": "top"},
            "scroll up": {"direction": "up"},
            "scroll down": {"direction": "down"},
            "scroll to bottom": {"direction": "bottom"},
        },
    )
