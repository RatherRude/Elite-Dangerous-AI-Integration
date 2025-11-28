import queue
import threading
import time
import traceback
from typing import Any, override, Optional, Iterable

from lib.PluginHelper import PluginHelper, TTSModel, LLMModel, STTModel, EmbeddingModel
from lib.PluginSettingDefinitions import (
    PluginSettings, 
    SettingsGrid, 
    ToggleSetting, 
    ParagraphSetting,
    ModelProviderDefinition,
)
from lib.Logger import log, show_chat_message
from lib.PluginBase import PluginBase, PluginManifest

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


def get_process_id() -> (int | None):
    """Check if EDCoPilot is running"""
    try:
        import psutil

        for proc in psutil.process_iter():
            if "EDCoPilot" in proc.name():
                return proc.pid
        return None
    except Exception:
        return None


class EDCoPilotDominantTTSModel(TTSModel):
    """
    TTS model that generates silence, allowing EDCoPilot to handle speech output.
    This is used when EDCoPilot is in "Dominant" mode.
    """
    
    def __init__(self, speed: float = 1.0):
        super().__init__("edcopilot-dominant")
        self.speed = speed
    
    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        """Generate silent audio based on text length, mimicking speech duration."""
        word_count = len(text.split())
        words_per_minute = 150 * float(self.speed)
        audio_duration = word_count / words_per_minute * 60
        # Generate silent audio for the duration of the text (24kHz, 16-bit mono)
        # Each chunk is 1024 bytes of silence
        for _ in range(int(audio_duration * 24_000 / 1024)):
            yield b"\x00" * 1024


# Main plugin class
class EDCoPilotPlugin(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        
        # EDCoPilot state
        self.install_path = get_install_path()
        self.proc_id = get_process_id()
        self.client = None
        self.provider = None
        self.listener_thread = None
        self.event_publication_queue: queue.Queue[ExternalChatNotification|ExternalBackgroundChatNotification] = queue.Queue()

        # Define the plugin settings and model providers - conditional on installation
        if self.is_installed():
            self.settings_config: PluginSettings | None = PluginSettings(
                key="EDCoPilotPlugin",
                label="EDCoPilot",
                icon="smart_toy",
                grids=[
                    SettingsGrid(
                        key="general",
                        label="General",
                        fields=[
                            ParagraphSetting(
                                key="info_text",
                                label=None,
                                type="paragraph",
                                readonly=False,
                                placeholder=None,
                                
                                content="EDCoPilot does not share the contents of its UI, nor any other data. You can use it for its UI, but it adds zero functionality or knowledge to the AI. The EDCoPilot integration prevents both applications from talking at the same time and allows COVAS:NEXT to control EDCoPilot's UI."
                            ),
                            ToggleSetting(
                                key="enabled",
                                label="Enable EDCoPilot Integration",
                                type="toggle",
                                readonly=False,
                                placeholder=None,
                                default_value=False
                            ),
                            ParagraphSetting(
                                key="dominant_mode_hint",
                                label=None,
                                type="paragraph",
                                readonly=False,
                                placeholder=None,
                                
                                content="To enable EDCoPilot Dominant mode (where EDCoPilot handles speech output), go to <b>Advanced Settings → TTS Settings</b> and select <b>\"EDCoPilot (Dominant)\"</b> as the TTS Provider."
                            ),
                            ToggleSetting(
                                key="actions",
                                label="Enable EDCoPilot UI Actions",
                                type="toggle",
                                readonly=False,
                                placeholder=None,
                                default_value=True
                            ),
                            ParagraphSetting(
                                key="actions_warning",
                                label=None,
                                type="paragraph",
                                readonly=False,
                                placeholder=None,
                                
                                content="We strongly recommend to activate only one set of UI actions, either COVAS:NEXT's or EDCoPilot's."
                            ),
                        ]
                    ),
                ]
            )
            
            # Add TTS model provider for EDCoPilot Dominant mode
            self.model_providers: list[ModelProviderDefinition] | None = [
                ModelProviderDefinition(
                    kind='tts',
                    id='edcopilot-dominant',
                    label='EDCoPilot (Dominant)',
                    settings_config=[
                        SettingsGrid(
                            key='tts',
                            label='EDCoPilot Dominant Mode',
                            fields=[
                                ParagraphSetting(
                                    key="dominant_mode_hint",
                                    label=None,
                                    type="paragraph",
                                    readonly=False,
                                    placeholder=None,
                                    
                                    content="In Dominant mode, EDCoPilot handles all speech output. Slow or delayed responses are expected in this mode."
                                ),
                            ]
                        ),
                    ],
                ),
            ]

    def create_model(self, provider_id: str, settings: dict[str, Any]) -> LLMModel | STTModel | TTSModel | EmbeddingModel:
        """Create a model instance for the given provider."""
        if provider_id == 'edcopilot-dominant':
            # Get TTS speed from main config if available
            speed = 1.0
            return EDCoPilotDominantTTSModel(speed=speed)
        raise ValueError(f"Unknown provider_id: {provider_id}")
    
    def is_installed(self) -> bool:
        """Check if EDCoPilot is installed"""
        return self.install_path is not None
    
    def is_running(self) -> bool:
        """Check if EDCoPilot is running"""
        if self.proc_id:
            try:
                import psutil
                if psutil.pid_exists(self.proc_id):
                    return True
            except Exception:
                pass

        self.proc_id = get_process_id()
        return self.proc_id is not None

    def listen_actions(self):
        """Background thread to listen for EDCoPilot actions"""
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

    def is_edcopilot_dominant(self) -> bool:
        """Check if EDCoPilot Dominant TTS provider is selected in config."""
        if not hasattr(self, '_helper') or not self._helper:
            return False
        tts_provider = self._helper._config.get('tts_provider', '')
        # Plugin providers are formatted as 'plugin:<guid>:<provider_id>'
        return tts_provider == f'plugin:{self.plugin_manifest.guid}:edcopilot-dominant'

    def share_config(self):
        """Send configuration to EDCoPilot"""
        if self.provider:
            is_edcopilot_dominant = self.is_edcopilot_dominant()
            config = self._helper._config
            character = config['characters'][config['active_character_index']]

            enabled_game_events: list[str] = []
            disabled_events = character.get("disabled_game_events", [])
            if character.get("event_reaction_enabled_var", False):
                for event, state in character.get("game_events", {}).items():
                    if state and event not in disabled_events:
                        enabled_game_events.append(event)
            
            return self.provider.publish(
                ConfigurationUpdated(is_dominant=not is_edcopilot_dominant, enabled_game_events=enabled_game_events)
            )

    def output_commander(self, message: str):
        """Send commander message to EDCoPilot"""
        if self.provider:
            is_edcopilot_dominant = self.is_edcopilot_dominant()
            return self.provider.publish(
                CommanderSpoke(muted=is_edcopilot_dominant, text=message)
            )

    def output_covas(self, message: str, reasons: list[str]):
        """Send COVAS message to EDCoPilot"""
        if self.provider:
            is_edcopilot_dominant = self.is_edcopilot_dominant()
            return self.provider.publish(
                CovasReplied(muted=is_edcopilot_dominant, text=message, reasons=reasons)
            )

    def get_setting(self, key: str, default=None):
        """Helper to get plugin settings"""
        # This will be implemented via the PluginHelper in on_chat_start
        return self.settings.get(key, default)

    @override
    def on_chat_start(self, helper: PluginHelper):
        """Called when chat starts - initialize EDCoPilot connection and register actions"""
        self._helper = helper
        
        # Check if plugin is enabled
        enabled = self.settings.get("enabled", False)
        if not enabled:
            log('info', 'EDCoPilot plugin is disabled')
            return
        
        # Check if EDCoPilot is installed
        if not self.is_installed():
            log('warn', 'EDCoPilot is not installed')
            show_chat_message("warning", "EDCoPilot is not installed. Plugin will not be active.")
            return
        
        # Initialize EDCoPilot connection
        try:
            self.client = create_edcopilot_client()
            self.provider = create_covasnext_provider()
            log('info', 'Successfully connected to EDCoPilot via EDMesg')
        except Exception as e:
            log('error', f'Failed to connect to EDCoPilot: {e}')
            show_chat_message("error", "Could not connect to EDMesg, EDCoPilot integration will not work.")
            return
        
        # Start listener thread
        self.listener_thread = threading.Thread(target=self.listen_actions)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        
        # Register actions if enabled
        actions_enabled = self.settings.get("actions", True)
        if actions_enabled:
            self._register_actions(helper)
            log('info', f"EDCoPilot UI actions registered")
        else:
            log('info', f"EDCoPilot UI actions disabled")
        
        # Register side effect to monitor conversation events
        helper.register_sideeffect(
            self._on_event
        )
        
        log('info', f"EDCoPilot plugin initialized successfully")
        
    def _register_actions(self, helper: PluginHelper):
        """Register EDCoPilot-specific actions"""
        
        # Register open panel action
        helper.register_action(
            name='edcopilot_open_panel',
            description="Open a specific panel in EDCoPilot",
            parameters={
                "type": "object",
                "properties": {
                    "panelName": {
                        "type": "string",
                        "enum": [
                            "bookmarks", "bookmarkgroups", "voicelog", "eventlog", "sessionprogress",
                            "systemhistory", "traderoute", "discoveryestimator", "miningstats", "miningprices",
                            "placesofinterest", "locationsearch", "locationresults", "guidancecomputer", "timetrials",
                            "systeminfo", "stations", "bodies", "factionsystems",
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
            method=self.edcopilot_open_panel,
            action_type='global',
            input_template=lambda args, _: f"Opening EDCoPilot panel: {args.get('panelName', '')} {args.get('details', '')}"
        )
        
        # Register navigate panel action
        helper.register_action(
            name='edcopilot_navigate_panel',
            description="Navigate the current panel in EDCoPilot",
            parameters={
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
            method=self.edcopilot_navigate_panel,
            action_type='global',
            input_template=lambda args, _: f"Navigating in EDCoPilot panel: {args.get('navigate', '')}{args.get('selectItem', '')}"
        )
        
        log('debug', f"EDCoPilot actions registered")
        
    def _on_event(self, event: Any, context: dict[str, Any]):
        if event.kind in ['user', 'assistant']:
            self._on_conversation_event(event)
    
    def _on_conversation_event(self, event: Any):
        """Handle conversation events - forward messages to EDCoPilot"""
        if not self.provider:
            return
        
        role = event.kind
        content = event.content if hasattr(event, 'content') else ''
        
        try:
            
            # Handle user input
            if role == 'user':
                message = content
                if message:
                    self.output_commander(message)
                    log('debug', f'Sent commander message to EDCoPilot: {message[:50]}...')
            
            # Handle AI response
            elif role == 'assistant':
                response = content
                reasons = event.reasons if hasattr(event, 'reasons') else None
                if response:
                    self.output_covas(response, reasons or [])
                    log('debug', f'Sent COVAS response to EDCoPilot')
        
        except Exception as e:
            log('error', f'Failed to handle conversation event: {e}')
    
    @override
    def on_chat_stop(self, helper: PluginHelper):
        """Called when chat stops - cleanup resources"""
        self.client = None
        self.provider = None
        log('debug', 'EDCoPilot plugin stopped')

    # Action implementations
    def edcopilot_open_panel(self, args: dict, projected_states: dict) -> str:
        """Open a specific panel in EDCoPilot"""
        panel_name = args.get("panelName", "")
        details = args.get("details", "")
        
        if not panel_name:
            return "Failed to open panel: No panel specified"
        
        if not self.client:
            return "Failed to open panel: EDCoPilot client not available"

        try:
            log('info', f'Opening EDCoPilot panel: {panel_name}')
            self.client.publish(OpenPanelAction(panelName=panel_name, details=details))
            return f"Successfully requested to open {panel_name} panel in EDCoPilot"
        except Exception as e:
            log('error', f'Failed to open panel: {e}\n{traceback.format_exc()}')
            return f"Failed to open panel: {str(e)}"

    def edcopilot_navigate_panel(self, args: dict, projected_states: dict) -> str:
        """Navigate the current panel in EDCoPilot"""
        select_item = args.get("selectItem", 0)
        navigate = args.get("navigate", "")

        if not self.client:
            return "Failed to navigate panel: EDCoPilot client not available"

        try:
            log('info', f'Navigating on EDCoPilot panel: {navigate} {select_item}')
            self.client.publish(PanelNavigationAction(navigate=navigate, selectItem=select_item))
            return f"Successfully requested to navigate in panel: {navigate} {select_item}"
        except Exception as e:
            log('error', f'Failed to navigate panel: {e}\n{traceback.format_exc()}')
            return f"Failed to navigate panel: {str(e)}"