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


# open chat tab
def show_chat(obj, projected_states):
    send_message({
        "type": "ui",
        "show": "chat",
    })

    return "Chat is now being displayed"

# open status tab
def show_status(obj, projected_states):
    send_message({
        "type": "ui",
        "show": "status",
    })

    return "Status is now being displayed"

# open storage tab
def show_storage(obj, projected_states):
    send_message({
        "type": "ui",
        "show": "storage",
    })

    return "Storage is now being displayed"

# open station tab
def show_station(obj, projected_states):
    checkStatus(projected_states, {'Docked': False})
    send_message({
        "type": "ui",
        "show": "station",
    })

    return "Station is now being displayed"

def register_ui_actions(actionManager: ActionManager, eventManager: EventManager):
    global event_manager
    event_manager = eventManager

    # Register actions - Web Tools
    actionManager.registerAction(
        'showChat',
        "Display an overview of the current conversation",
        {},
        show_chat,
        'ui',
    )
    actionManager.registerAction(
        'showStatus',
        "Display current ship or suit loadout details and state, alerts, and key telemetry",
        {},
        show_status,
        'ui',
    )
    actionManager.registerAction(
        'showStorage',
        "Display construction efforts, ship and suits materials and engineer info",
        {},
        show_storage,
        'ui',
    )
    actionManager.registerAction(
        'showStation',
        "Display docked station's outfitting and market information",
        {},
        show_station,
        'ui',
    )

