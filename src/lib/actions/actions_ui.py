from ..ActionManager import ActionManager
from ..EventManager import EventManager
from ..UI import send_message
from typing import Optional

event_manager: Optional[EventManager] = None

# Checking status projection to exit game actions early if not applicable
def checkStatus(projected_states: dict[str, dict], blocked_status_dict: dict[str, bool]):
    current_status = projected_states.get("CurrentStatus")

    if current_status:
        for blocked_status, expected_value in blocked_status_dict.items():
            for flag_group in ['flags', 'flags2']:
                if flag_group in current_status and blocked_status in current_status[flag_group]:
                    if current_status[flag_group][blocked_status] == expected_value:
                        raise Exception(f"Action not possible due to {'not ' if not expected_value else ''}being in a state of {blocked_status}!")


def show_ui(obj, projected_states):
    """Show a specific UI tab: chat | status | storage | station"""
    tab: str = (obj or {}).get('tab', 'chat')
    valid_tabs = {"chat", "status", "storage", "station"}

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
        "Display a specific tab",
        {
            "type": "object",
            "properties": {
                "tab": {
                    "type": "string",
                    "description": "4 tabs to display. 1) Chat: current conversation 2)status: ship/suit loadout and state 3)storage: colony constructions materials and engineers 4)station: outfitting and market info of docked station)",
                    "enum": ["chat", "status", "storage", "station"],
                }
            },
            "required": ["tab"]
        },
        show_ui,
        'ui',
        cache_prefill={
            "show chat": {"tab": "chat"},
        }
    )

