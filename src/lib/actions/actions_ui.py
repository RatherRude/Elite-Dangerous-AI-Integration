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
    """Show a specific UI tab: chat | status | navigation | storage | station | tasks | logbook | search"""
    tab: str = (obj or {}).get('tab', 'chat')
    valid_tabs = {"chat", "status", "navigation", "storage", "station", "tasks", "logbook", "search"}

    if tab not in valid_tabs:
        raise Exception(f"Unknown tab '{tab}'. Expected one of: {', '.join(sorted(valid_tabs))}.")

    # Guard for station tab when not docked
    if tab == 'station':
        checkStatus(projected_states, {'Docked': False})

    send_message({
        "type": "ui",
        "show": tab,
    })

    return f"{tab.capitalize()} is now being displayed"


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
                    "description": "Chat: current conversation; Status: ship/suit loadout and state; Navigation: currrent system information; Storage: colony construction, materials and engineers; Station: outfitting and market info of docked station; Tasks: active missions and objectives; Logbook: user history and memories; Search: manual search agent and results",
                    "enum": ["chat", "status", "navigation", "storage", "station", "tasks", "logbook", "search"],
                }
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
        }
    )

