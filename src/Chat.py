import sys
from time import sleep
from typing import Any, cast, final
import os
import threading
import json
import io
import traceback

from EDMesg.CovasNext import ExternalChatNotification, ExternalBackgroundChatNotification
from openai import OpenAI

from lib.PluginHelper import PluginHelper
from lib.Config import Config, assign_ptt, get_ed_appdata_path, get_ed_journals_path, get_system_info, load_config, save_config, update_config, update_event_config, validate_config, update_character, reset_game_events
from lib.PluginManager import PluginManager
from lib.ActionManager import ActionManager
from lib.actions.Actions import register_actions
from lib.ControllerManager import ControllerManager
from lib.EDCoPilot import EDCoPilot
from lib.EDKeys import EDKeys
from lib.Event import ConversationEvent, Event, ExternalEvent, GameEvent, ProjectedEvent, StatusEvent, ToolEvent
from lib.Logger import show_chat_message
from lib.Projections import registerProjections
from lib.PromptGenerator import PromptGenerator
from lib.STT import STT
from lib.TTS import TTS
from lib.StatusParser import StatusParser
from lib.EDJournal import *
from lib.EventManager import EventManager
from lib.UI import send_message
from lib.SystemDatabase import SystemDatabase
from lib.Assistant import Assistant

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', write_through=True)


@final
class Chat:
    def __init__(self, config: Config, plugin_manager: PluginManager):
        self.config = config # todo: remove
        self.plugin_manager = plugin_manager
        if self.config["api_key"] == '':
            self.config["api_key"] = '-'
        self.character = self.config['characters'][self.config['active_character_index']]

        self.voice_instructions = self.character["tts_prompt"]

        self.backstory = self.character["character"].replace("{commander_name}", self.config['commander_name'])

        self.enabled_game_events: list[str] = []
        if self.character["event_reaction_enabled_var"]:
            for event, state in self.character["game_events"].items():
                if state:
                    self.enabled_game_events.append(event)

        log("debug", "Initializing Controller Manager...")
        self.controller_manager = ControllerManager()

        log("debug", "Initializing Action Manager...")
        self.action_manager = ActionManager()

        log("debug", "Initializing EDJournal...")
        self.jn = EDJournal(get_ed_journals_path(config))
            
        log("debug", "Initializing Third Party Services...")
        self.copilot = EDCoPilot(self.config["edcopilot"], is_edcopilot_dominant=self.config["edcopilot_dominant"],
                            enabled_game_events=self.enabled_game_events)

        # gets API Key from config.json
        self.llmClient = OpenAI(
            base_url="https://api.openai.com/v1" if self.config["llm_endpoint"] == '' else self.config["llm_endpoint"],
            api_key=self.config["api_key"] if self.config["llm_api_key"] == '' else self.config["llm_api_key"],
        )
        
        # vision
        self.visionClient: OpenAI | None = None
        if self.config["vision_var"]:
            self.visionClient = OpenAI(
                base_url="https://api.openai.com/v1" if self.config["vision_endpoint"] == '' else self.config["vision_endpoint"],
                api_key=self.config["api_key"] if self.config["vision_api_key"] == '' else self.config["vision_api_key"],
            )
            

        log("debug", "Initializing Speech processing...")
        self.sttClient: OpenAI | None = None
        if self.config["stt_provider"] in ['openai', 'custom', 'custom-multi-modal', 'google-ai-studio', 'local-ai-server']:
            self.sttClient = OpenAI(
                base_url=self.config["stt_endpoint"],
                api_key=self.config["api_key"] if self.config["stt_api_key"] == '' else self.config["stt_api_key"],
            )

        self.ttsClient: OpenAI | None = None
        if self.config["tts_provider"] in ['openai', 'custom', 'local-ai-server']:
            self.ttsClient = OpenAI(
                base_url=self.config["tts_endpoint"],
                api_key=self.config["api_key"] if self.config["tts_api_key"] == '' else self.config["tts_api_key"],
            )
            
        tts_provider = 'none' if self.config["edcopilot"] and self.config["edcopilot_dominant"] else self.config["tts_provider"]
        self.tts = TTS(openai_client=self.ttsClient, provider=tts_provider, model=self.config["tts_model_name"], voice=self.character["tts_voice"], voice_instructions=self.character["tts_prompt"], speed=self.character["tts_speed"], output_device=self.config["output_device_name"])
        self.stt = STT(openai_client=self.sttClient, provider=self.config["stt_provider"], input_device_name=self.config["input_device_name"], model=self.config["stt_model_name"], language=self.config["stt_language"], custom_prompt=self.config["stt_custom_prompt"], required_word=self.config["stt_required_word"])

        log("debug", "Initializing SystemDatabase...")
        self.system_database = SystemDatabase()
        log("debug", "Initializing EDKeys...")
        self.ed_keys = EDKeys(get_ed_appdata_path(config))
        log("debug", "Initializing status parser...")
        self.status_parser = StatusParser(get_ed_journals_path(config))
        log("debug", "Initializing prompt generator...")
        self.prompt_generator = PromptGenerator(self.config["commander_name"], self.character["character"], important_game_events=self.enabled_game_events, system_db=self.system_database)
        
        log("debug", "Getting plugin event classes...")
        plugin_event_classes = self.plugin_manager.register_event_classes()

        log("debug", "Initializing event manager...")
        self.event_manager = EventManager(
            game_events=self.enabled_game_events,
            plugin_event_classes=plugin_event_classes,
        )

        log("debug", message="Initializing assistant...")
        self.assistant = Assistant(
            config=self.config,
            enabled_game_events=self.enabled_game_events,
            event_manager=self.event_manager,
            action_manager=self.action_manager,
            llmClient=self.llmClient,
            tts=self.tts,
            prompt_generator=self.prompt_generator,
            copilot=self.copilot,
        )
        self.is_replying = False
        self.listening = False

        log("debug", "Registering side effect...")
        self.event_manager.register_sideeffect(self.on_event)
        self.event_manager.register_sideeffect(self.assistant.on_event)
        
        self.plugin_helper = PluginHelper(self.prompt_generator, config, self.action_manager, self.event_manager, self.llmClient, self.config["llm_model_name"], self.visionClient, self.config["vision_model_name"], self.system_database, self.ed_keys, self.assistant)
        log("debug", "Plugin helper is ready...")

        # Execute plugin helper ready hooks
        self.plugin_manager.on_plugin_helper_ready(self.plugin_helper)

        log("debug", "Registering plugin provided should_reply event handlers...")
        self.plugin_manager.register_should_reply_handlers(self.plugin_helper)
        
        log("debug", "Registering plugin provided side effect...")
        self.plugin_manager.register_sideeffects(self.plugin_helper)
        
        log("debug", "Registering plugin provided prompt event handlers...")
        self.plugin_manager.register_prompt_event_handlers(self.plugin_helper)
        
        log("debug", "Registering plugin provided status generators...")
        self.plugin_manager.register_status_generators(self.plugin_helper)

        self.previous_states = {}

    def on_event(self, event: Event, projected_states: dict[str, Any]):
        for key, value in projected_states.items():
            if self.previous_states.get(key, None) != value:
                send_message({
                    "type": "states",
                    "states": {key: value},
                })
        self.previous_states = projected_states
        send_message({
            "type": "event",
            "event": event,
        })
        if event.kind=='assistant':
            event = cast(ConversationEvent, event)
            show_chat_message('covas', event.content)
        if event.kind=='user':
            event = cast(ConversationEvent, event)
            show_chat_message('cmdr', event.content)
        if event.kind=='tool':
            event = cast(ToolEvent, event)
            show_chat_message('action', '\n'.join(event.text if event.text else [r.get('function',{}).get('name', 'Unknown') for r in event.request]))
        if event.kind=='game':
            event = cast(GameEvent, event)
            show_chat_message('event', event.content.get('event', 'Unknown'))
        if event.kind=='status':
            event = cast(StatusEvent, event)
            if event.status.get('event', 'Unknown') != 'Status':
                show_chat_message('event', event.status.get('event', 'Unknown'))
        if event.kind=='external':
            event = cast(ExternalEvent, event)
            show_chat_message('event', event.content.get('event', 'Unknown'))
        if event.kind=='projected':
            event = cast(ProjectedEvent, event)
            show_chat_message('event', event.content.get('event', 'Unknown'))

    def submit_input(self, input: str):
        self.event_manager.add_conversation_event('user', input)
        
    def run(self):
        show_chat_message('info', f"Initializing CMDR {self.config['commander_name']}'s personal AI...\n")
        show_chat_message('info', "API Key: Loaded")
        show_chat_message('info', f"Using Push-to-Talk: {self.config['ptt_var']}")
        show_chat_message('info', f"Using Function Calling: {self.config['tools_var']}")
        show_chat_message('info', f"Current model: {self.config['llm_model_name']}")
        show_chat_message('info', f"Current TTS voice: {self.character['tts_voice']}")
        show_chat_message('info', f"Current TTS Speed: {self.character['tts_speed']}")
        show_chat_message('info', "Current backstory: " + self.backstory)

        # TTS Setup
        show_chat_message('info', "Basic configuration complete.")
        show_chat_message('info', "Loading voice output...")
        if self.config["edcopilot"] and self.config["edcopilot_dominant"]:
            show_chat_message('info', "EDCoPilot is dominant, voice output will be handled by EDCoPilot.")

        if self.config['ptt_var'] and self.config['ptt_key']:
            show_chat_message('info', f"Setting push-to-talk hotkey {self.config['ptt_key']}.")
            self.controller_manager.register_hotkey(
                self.config["ptt_key"], 
                lambda _: self.stt.listen_once_start(),
                lambda _: self.stt.listen_once_end()
            )
        else:
            self.stt.listen_continuous()
        show_chat_message('info', "Voice interface ready.")

        registerProjections(self.event_manager, self.system_database, self.character.get('idle_timeout_var', 300))
        self.plugin_manager.register_projections(self.plugin_helper)

        if self.config['tools_var']:
            log('info', "Register actions...")
            register_actions(self.action_manager, self.event_manager, self.llmClient, self.config["llm_model_name"], self.visionClient, self.config["vision_model_name"], self.ed_keys)

            log('info', "Built-in Actions ready.")
            self.plugin_manager.register_actions(self.plugin_helper)
            log('info', "Plugin provided Actions ready.")
            show_chat_message('info', "Actions ready.")

        show_chat_message('info', 'Initializing states...')
        while self.jn.historic_events:
            self.event_manager.add_historic_game_event(self.jn.historic_events.pop(0))
            
        self.event_manager.add_status_event(self.status_parser.current_status)
        self.event_manager.process()

        # Cue the user that we're ready to go.
        show_chat_message('info', "System Ready.")

        while True:
            try:
                status = None
                # check status file for updates
                while not self.status_parser.status_queue.empty():
                    status = self.status_parser.status_queue.get()
                    self.event_manager.add_status_event(status)
                    
                # mute continuous listening during response
                if self.config["mute_during_response_var"]:
                    if self.tts.get_is_playing():
                        self.stt.pause_continuous_listening(True)
                    else:
                        self.stt.pause_continuous_listening(False)

                # check STT recording
                if self.stt.recording:
                    if not self.listening:
                        self.listening = True
                        self.event_manager.add_user_speaking()
                    if self.tts.get_is_playing():
                        log('debug', 'interrupting TTS')
                        self.tts.abort()
                else:
                    self.listening = False

                # check STT result queue
                if not self.stt.resultQueue.empty():
                    text = self.stt.resultQueue.get().text
                    self.tts.abort()
                    self.copilot.output_commander(text)
                    self.event_manager.add_conversation_event('user', text)

                # check EDJournal files for updates
                while not self.jn.events.empty():
                    event = self.jn.events.get()
                    self.event_manager.add_game_event(event)

                while not self.copilot.event_publication_queue.empty():
                    event = self.copilot.event_publication_queue.get()
                    if isinstance(event, ExternalChatNotification):
                        self.event_manager.add_external_event('External' + event.service.capitalize() + 'Notification',
                                                              event.model_dump())
                    if isinstance(event, ExternalBackgroundChatNotification):
                        self.event_manager.add_external_event('External' + event.service.capitalize() + 'Message',
                                                          event.model_dump())

                self.event_manager.process()

                if self.assistant.reply_pending and not self.assistant.is_replying and not self.stt.recording:
                    all_events, projected_states = self.event_manager.get_current_state()
                    self.assistant.reply(all_events, projected_states)
                    
                # Infinite loops are bad for processors, must sleep.
                sleep(0.1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                log("error", e, traceback.format_exc())
                break

        # Teardown TTS
        self.tts.quit()

        # Execute plugin chat stop hooks
        self.plugin_manager.on_chat_stop(self.plugin_helper)


def read_stdin(chat: Chat):
    log("debug", "Reading stdin...")
    print(json.dumps({"type": "running_config", "config": config}) + '\n', flush=True)
    while True:
        line = sys.stdin.readline().strip()
        if line:
            data = json.loads(line)
            if data.get("type") == "submit_input":
                chat.submit_input(data["input"])
            if data.get("type") == "init_overlay":
                print(json.dumps({"type": "running_config", "config": config})+'\n', flush=True)

def check_zombie_status():
    """Checks if the current process is a zombie and exits if it is."""
    log("debug", "Starting zombie process checker thread...")
    while True:
        if os.getppid() == 1:
            log("info", "Parent process exited. Exiting.")
            sleep(1)  # Give some time for the parent to exit
            os._exit(0)  # Use os._exit to avoid cleanup issues in threads
        sleep(5)  # Check every 5 seconds

if __name__ == "__main__":
    try:
        print(json.dumps({"type": "ready"})+'\n')
        # Load plugins.
        log('debug', "Loading plugins...")
        plugin_manager = PluginManager()
        plugin_manager.load_plugins()
        log('debug', "Registering plugin settings for the UI...")
        plugin_manager.register_settings()
        # Wait for start signal on stdin
        config = load_config()
        print(json.dumps({"type": "config", "config": config})+'\n', flush=True)
        system = get_system_info()
        print(json.dumps({"type": "system", "system": system})+'\n', flush=True)
        while True:
            # print(f"Waiting for command...")
            line = sys.stdin.readline().strip()
            # print(f"Received command: {line}")
            if not line:
                continue
                
            try:
                data = json.loads(line)
                if data.get("type") == "start":
                    if data.get('oldUi'):
                        config = load_config()
                        break
                    else: 
                        new_config = validate_config(config)
                        if new_config:
                            config = new_config
                            break
                if data.get("type") == "assign_ptt": 
                    config = assign_ptt(config, ControllerManager())
                if data.get("type") == "change_config":
                    config = update_config(config, data["config"])
                if data.get("type") == "change_event_config":
                    config = update_event_config(config, data["section"], data["event"], data["value"])
                if data.get("type") == "change_character":
                    config = update_character(config, data)
                if data.get("type") == "reset_game_events":
                    config = reset_game_events(config, data["character_index"])
                if data.get("type") == "clear_history":
                    EventManager.clear_history()
                    #ActionManager.clear_action_cache()
                if data.get("type") == "init_overlay":
                    update_config(config, {}) # Ensure that the overlay gets a new config on start
                
            except json.JSONDecodeError:
                continue
        
        # Once start signal received, initialize and run chat
        save_config(config)
        print(json.dumps({"type": "start"})+'\n', flush=True)
        
        chat = Chat(config, plugin_manager)
        # run chat in a thread
        stdin_thread = threading.Thread(target=read_stdin, args=(chat,), daemon=True)
        stdin_thread.start()

        if sys.platform.startswith('linux'):
            zombie_check_thread = threading.Thread(target=check_zombie_status, daemon=True)
            zombie_check_thread.start()

        log("debug", "Running chat...")
        chat.run()
    except Exception as e:
        log("error", e, traceback.format_exc())
        sys.exit(1)
