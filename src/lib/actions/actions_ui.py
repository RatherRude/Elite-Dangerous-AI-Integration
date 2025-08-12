from ..ActionManager import ActionManager
from ..EventManager import EventManager
from ..UI import send_message

event_manager: EventManager = None

# open chat tab
def show_chat(obj, projected_states):
    send_message({
        "type": "ui",
        "show": "chat",
    })

    return "Chat is now being displayed"

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

