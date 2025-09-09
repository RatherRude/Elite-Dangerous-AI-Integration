import queue
import threading
import time
import traceback
from typing import Optional
from typing import final

from EDMesg.CovasNext import (
    ExternalChatNotification,
    ExternalBackgroundChatNotification,
    create_covasnext_provider,
    create_covasnext_client,
    CommanderSpoke,
    CovasReplied,
    ConfigurationUpdated
)
from EDMesg.EDCoPilot import create_edcopilot_client, OpenPanelAction, PanelNavigationAction
from EDMesg.base import EDMesgWelcomeAction

from .ActionManager import ActionManager
from .Logger import log, show_chat_message


def get_install_path() -> (str | None):
    """Check the windows registry for COMPUTER / HKEY_CURRENT_USER / SOFTWARE / EDCoPilot"""
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "SOFTWARE\\EDCoPilot")
        value, _ = winreg.QueryValueEx(key, "EDCoPilotLib")
        winreg.CloseKey(key)
        return value
    except Exception:
        return None

@final
class EDCoPilot:
    def __init__(self, is_enabled: bool, is_edcopilot_dominant: bool=False, enabled_game_events: list[str]=[], action_manager: Optional[ActionManager]=None, has_actions: bool=False):
        self.install_path = get_install_path()
        self.proc_id = self.get_process_id()
        self.is_enabled = is_enabled and self.is_installed()
        self.client = None
        self.provider = None
        self.is_edcopilot_dominant = is_edcopilot_dominant
        self.enabled_game_events = enabled_game_events
        self.has_actions = has_actions
        self.action_manager = action_manager
        self.event_publication_queue: queue.Queue[ExternalChatNotification|ExternalBackgroundChatNotification] = queue.Queue()

        try:
            if self.is_enabled:
                self.client = create_edcopilot_client()
                self.provider = create_covasnext_provider()
        except Exception:
            self.is_enabled = False
            self.is_edcopilot_dominant = False
            show_chat_message("error", "Could not connect to EDMesg, third party applications may not work.")

        if self.is_enabled:
            thread = threading.Thread(target=self.listen_actions)
            thread.daemon = True
            thread.start()

            # Register EDCoPilot-specific actions if action_manager is provided
        if self.has_actions and self.action_manager:
            self.register_actions()



    def listen_actions(self):
        while True:
            if self.provider and not self.provider.pending_actions.empty():
                action = self.provider.pending_actions.get()
                if isinstance(action, EDMesgWelcomeAction):
                    self.share_config()
                if isinstance(action, ExternalChatNotification):
                    self.event_publication_queue.put(action)
                if isinstance(action, ExternalBackgroundChatNotification):
                    self.event_publication_queue.put(action)
            time.sleep(0.1)

    def is_installed(self) -> bool:
        """Check if EDCoPilot is installed"""
        return self.install_path is not None

    def is_running(self) -> bool:
        """Check if EDCoPilot is running"""
        if self.proc_id:
            import psutil

            if psutil.pid_exists(self.proc_id):
                return True

        self.proc_id = self.get_process_id()
        return self.proc_id is not None

    def get_process_id(self) -> (int | None):
        """Check if EDCoPilot is running"""
        try:
            import psutil

            for proc in psutil.process_iter():
                if "EDCoPilot" in proc.name():
                    return proc.pid
            return None
        except Exception:
            return None

    def share_config(self):
        """send Config"""
        if self.provider:
            return self.provider.publish(
                ConfigurationUpdated(is_dominant=not self.is_edcopilot_dominant ,enabled_game_events=self.enabled_game_events)
            )

    def output_commander(self, message: str):
        """send PrintThis: "message" request"""
        if self.provider:
            return self.provider.publish(
                CommanderSpoke(muted=self.is_edcopilot_dominant, text=message)
            )

    def output_covas(self, message: str, reasons: list[str]):
        """send SpeakThis: "message" request"""
        if self.provider:
            return self.provider.publish(
                CovasReplied(
                    muted=self.is_edcopilot_dominant, text=message, reasons=reasons
                )
            )

    def edcopilot_open_panel(self, args: dict, projected_states: dict) -> str:
        """Open a specific panel in EDCoPilot"""
        panel_name = args.get("panelName", "")
        details = args.get("details", "")
        if not panel_name or not self.provider:
            return "Failed to open panel: No panel specified or EDCoPilot provider not available"

        try:
            # Log the request for debugging
            log('info', f'Opening EDCoPilot panel: {panel_name}')

            self.client.publish(OpenPanelAction(panelName=panel_name, details=details))

            return f"Successfully requested to open {panel_name} panel in EDCoPilot"
        except Exception as e:
            return f"Failed to open panel: {str(e)}{traceback.format_exc()}"

    def edcopilot_navigate_panel(self, args: dict, projected_states: dict) -> str:
        """Open a specific panel in EDCoPilot"""
        select_item = args.get("selectItem", 0)
        navigate = args.get("navigate", "")

        try:
            # Log the request for debugging
            log('info', f'Navigating on EDCoPilot panel: {select_item}{navigate}')
            self.client.publish(PanelNavigationAction(navigate=navigate, selectItem=select_item))

            return f"Successfully requested to navigate in panel: {navigate}{select_item}"
        except Exception as e:
            return f"Failed to open panel: {str(e)}{traceback.format_exc()}"

    def register_actions(self):
        log('info', 'register actions')
        """Register EDCoPilot-specific actions with the action_manager"""
        if not self.action_manager:
            return

        # Register the open panel action
        self.action_manager.registerAction(
            "edcopilot_open_panel",
            "Open a specific panel in EDCoPilot",
            {
                "type": "object",
                "properties": {
                    "panelName": {
                        "type": "string",
                        "enum": [
                            # "bookmarks", "voicelog", "activity"
                            "bookmarks", "bookmarkgroups", "voicelog", "eventlog", "sessionprogress",
                            "systemhistory", "traderoute", "discoveryestimator", "miningstats", "miningprices",
                            "placesofinterest", "locationsearch", "locationresults", "guidancecomputer", "timetrials",
                            "systeminfo", "stations", "bodies", "factionsystems", "miningprices",
                            "stationfacts", "bodydata", "blueprints", "shiplist", "storedmodules",
                            "materials", "shiplocker", "suitlist", "weaponlist", "aboutedcopilot", "permits",
                            "messages", "prospectorannouncements", "music", "historyrefresh",
                            "commandreference", "settings"
                        ],
                        "description": "The name of the panel to open in EDCoPilot"
                    },
                    "details": {
                        "type": "string",
                        "description": "Additional inputs for panel, like system names"
                    }
                },
                "required": ["panelName"]
            },
            self.edcopilot_open_panel,
            "global",  # Make this action available in all modes
            lambda args, _: f"Opening EDCoPilot panel: {args.get('panelName', '')} {args.get('details', '')}"
        )

        # Register the open panel action
        self.action_manager.registerAction(
            "edcopilot_navigate_panel",
            "Navigate the current panel in EDCoPilot",
            {
                "type": "object",
                "properties": {
                    "navigate": {
                        "type": "string",
                        "enum": [
                            "scrolldown", "scrollup", "scrolltop", "scrollbottom", "back", "selectItem"
                        ],
                        "description": "Type of navigation"
                    },
                    "selectItem": {
                        "type": "number",
                        "description": "Item to select (only if navigate is selectItem)"
                    }
                },
                "required": ["navigate"]
            },
            self.edcopilot_navigate_panel,
            "global",  # Make this action available in all modes
            lambda args, _: f"Navigating in EDCoPilot panel: {args.get('navigate', '')}{args.get('selectItem', '')}"
        )

if __name__ == "__main__":
    client = create_covasnext_client()
    while True:
        while not client.pending_events.empty():
            print("incoming event")
            print(client.pending_events.get())
        time.sleep(0.1)
