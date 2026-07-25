from pydantic import BaseModel

from ..ActionManager import ActionManager
from ..EventManager import EventManager
from ..UI import send_message
from ..Projections import get_state_dict, ProjectedStates
from typing import Optional

event_manager: Optional[EventManager] = None

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
    valid_tabs = {"chat", "status", "navigation", "storage", "station", "tasks", "logbook", "search"}
    valid_submenus = {
        "navigation": {"location", "list", "route"},
        "storage": {"colonisation", "cargo", "carriers", "materials", "locker", "engineers", "blueprints", "modules", "ships"},
        "tasks": {"missions", "quests", "community-goals"},
    }

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
    global event_manager
    event_manager = eventManager

    # Single parameterized UI action
    actionManager.registerAction(
        'showUI',
        "Display a specific tab to the user via UI",
        {
            "type": "object",
            "properties": {
                "tab": {
                    "type": "string",
                    "description": "Chat: current conversation; Status: ship/suit loadout and state; Navigation: current system information; Storage: colony construction, materials and engineers; Station: outfitting and market info of docked station; Tasks: active missions and objectives; Logbook: user history and memories; Search: manual search agent and results",
                    "enum": ["chat", "status", "navigation", "storage", "station", "tasks", "logbook", "search"],
                },
                "submenu": {
                    "type": "string",
                    "description": "Optional submenu. Navigation: location, list, route. Storage: colonisation, cargo, carriers, materials, locker, engineers, blueprints, modules, ships. Tasks: missions, quests, community-goals.",
                    "enum": ["location", "list", "route", "colonisation", "cargo", "carriers", "materials", "locker", "engineers", "blueprints", "modules", "ships", "missions", "quests", "community-goals"],
                },
            },
            "required": ["tab"]
        },
        show_ui,
        'ui',
        cache_prefill={
            "show chat": {"tab": "chat"},
            "show status": {"tab": "status"},
            "show navigation": {"tab": "navigation"},
            "show storage": {"tab": "storage"},
            "show tasks": {"tab": "tasks"},
            "show logbook": {"tab": "logbook"},
            "show search": {"tab": "search"},
            "show location": {"tab": "navigation", "submenu": "location"},
            "show list": {"tab": "navigation", "submenu": "list"},
            "show route": {"tab": "navigation", "submenu": "route"},
            "show colonisation": {"tab": "storage", "submenu": "colonisation"},
            "show cargo": {"tab": "storage", "submenu": "cargo"},
            "show carriers": {"tab": "storage", "submenu": "carriers"},
            "show materials": {"tab": "storage", "submenu": "materials"},
            "show locker": {"tab": "storage", "submenu": "locker"},
            "show engineers": {"tab": "storage", "submenu": "engineers"},
            "show blueprints": {"tab": "storage", "submenu": "blueprints"},
            "show modules": {"tab": "storage", "submenu": "modules"},
            "show ships": {"tab": "storage", "submenu": "ships"},
            "show missions": {"tab": "tasks", "submenu": "missions"},
            "show quests": {"tab": "tasks", "submenu": "quests"},
            "show community goals": {"tab": "tasks", "submenu": "community-goals"},
        }
    )
    actionManager.registerAction(
        'scrollUI',
        "Scroll the currently displayed UI tab",
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

