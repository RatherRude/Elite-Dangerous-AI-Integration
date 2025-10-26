import copy
import sys
from time import sleep
from typing import Any, cast, final
import os
import threading
import json
import io
import traceback
from datetime import datetime

from EDMesg.CovasNext import ExternalChatNotification, ExternalBackgroundChatNotification
from openai import OpenAI

from lib.PluginHelper import PluginHelper
from lib.Config import Config, assign_ptt, get_ed_appdata_path, get_ed_journals_path, get_system_info, load_config, save_config, update_config, update_event_config, validate_config, update_character, reset_game_events
from lib.PluginManager import PluginManager
from lib.ActionManager import ActionManager
from lib.actions.Actions import register_actions
from lib.ControllerManager import ControllerManager
from lib.EDKeys import EDKeys
from lib.Event import ConversationEvent, Event, ExternalEvent, GameEvent, MemoryEvent, ProjectedEvent, StatusEvent, ToolEvent
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
        disabled_events = self.character.get("disabled_game_events", [])
        if self.character["event_reaction_enabled_var"]:
            for event, state in self.character["game_events"].items():
                if state and event not in disabled_events:
                    self.enabled_game_events.append(event)

        log("debug", "Initializing Controller Manager...")
        self.controller_manager = ControllerManager()

        log("debug", "Initializing Action Manager...")
        self.action_manager = ActionManager()
        # Set allowed actions permissions from config (empty means allow all)
        try:
            self.action_manager.set_allowed_actions(self.config.get("allowed_actions", []))
        except Exception:
            self.action_manager.set_allowed_actions([])

        log("debug", "Initializing EDJournal...")
        self.jn = EDJournal(get_ed_journals_path(config))
            
        # gets API Key from config.json
        self.llmClient = OpenAI(
            base_url="https://api.openai.com/v1" if self.config["llm_endpoint"] == '' else self.config["llm_endpoint"],
            api_key=self.config["api_key"] if self.config["llm_api_key"] == '' else self.config["llm_api_key"],
        )
        # embeddings
        self.embeddingClient: OpenAI | None = None
        if self.config.get("embedding_provider") in ['openai', 'custom', 'google-ai-studio', 'local-ai-server']:
            self.embeddingClient = OpenAI(
                base_url=self.config["embedding_endpoint"],
                api_key=self.config["api_key"] if self.config["embedding_api_key"] == '' else self.config["embedding_api_key"],
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
            
        tts_provider = self.config["tts_provider"]
        self.tts = TTS(openai_client=self.ttsClient, provider=tts_provider, model=self.config["tts_model_name"], voice=self.character["tts_voice"], voice_instructions=self.character["tts_prompt"], speed=self.character["tts_speed"], output_device=self.config["output_device_name"])
        self.stt = STT(openai_client=self.sttClient, provider=self.config["stt_provider"], input_device_name=self.config["input_device_name"], model=self.config["stt_model_name"], language=self.config["stt_language"], custom_prompt=self.config["stt_custom_prompt"], required_word=self.config["stt_required_word"])

        log("debug", "Initializing SystemDatabase...")
        self.system_database = SystemDatabase()
        log("debug", "Initializing EDKeys...")
        self.ed_keys = EDKeys(get_ed_appdata_path(config))
        log("debug", "Initializing status parser...")
        self.status_parser = StatusParser(get_ed_journals_path(config))
        log("debug", "Initializing prompt generator...")
        self.prompt_generator = PromptGenerator(self.config["commander_name"], self.character["character"], important_game_events=self.enabled_game_events, system_db=self.system_database, weapon_types=cast(list[dict], self.config.get("weapon_types", [])), disabled_game_events=disabled_events)
        
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
            embeddingClient=self.embeddingClient,
            disabled_game_events=disabled_events
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
        self.previous_states = copy.deepcopy(projected_states)
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
        if event.kind=='memory':
            event = cast(MemoryEvent, event)
            show_chat_message('memory', event.content)

    def submit_input(self, input: str):
        self.event_manager.add_conversation_event('user', input)
    
    def query_memories(self, query: str, top_k: int = 5):
        """Query long-term memories without triggering LLM interaction"""
        if not self.embeddingClient:
            return {"error": "Embeddings model not configured"}
        
        embedding_model = self.config.get("embedding_model_name")
        if not embedding_model:
            return {"error": "Embedding model name not configured"}
        
        try:
            # Create embedding for the query
            embedding_response = self.embeddingClient.embeddings.create(
                model=embedding_model,
                input=query
            )
            embedding = embedding_response.data[0].embedding
            
            # Search the vector store
            results = self.event_manager.long_term_memory.search(
                query,
                embedding_response.model, 
                embedding, 
                n=min(max(1, top_k), 20)
            )
            
            if not results:
                return {"results": []}
            
            formatted = []
            for result in results:
                # Fetch inserted_at timestamp for this entry
                time_until: float = result["metadata"].get('time_until', result["inserted_at"])
                time_since: float = result["metadata"].get('time_since', result["inserted_at"])
                item = {
                    'score': round(result["score"], 3),
                    'summary': result["content"],
                    'inserted_at': result["inserted_at"],
                    'time_until': time_until,
                    'time_since': time_since
                }
                
                formatted.append(item)
            
            return {"results": formatted}
            
        except Exception as e:
            log('error', f'Error querying memories: {e}')
            import traceback
            log('error', traceback.format_exc())
            return {"error": str(e)}
    
    def get_memories_by_date(self, date_str: str):
        """Fetch all memory entries for a specific date"""
        try:
            # Parse the date string (format: YYYY-MM-DD)
            target_date = datetime.fromisoformat(date_str).date()
            entries = self.event_manager.long_term_memory.get_entries_by_date(target_date)
            return {"entries": [{
                "id": e["id"],
                "content": e["content"],
                "inserted_at": e["inserted_at"],
                "time_since": e["metadata"].get('time_since', e["inserted_at"]),
                "time_until": e["metadata"].get('time_until', e["inserted_at"]),
            } for e in entries], "date": date_str}
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD."}
        except Exception as e:
            log('error', f'Error fetching memories by date: {e}')
            import traceback
            log('error', traceback.format_exc())
            return {"error": str(e)}
    
    def get_available_dates(self):
        """Fetch all dates that have memory entries"""
        try:
            dates = self.event_manager.long_term_memory.get_available_dates()
            return {"dates": dates}
        except Exception as e:
            log('error', f'Error fetching available dates: {e}')
            import traceback
            log('error', traceback.format_exc())
            return {"error": str(e)}
        
    def run(self):
        show_chat_message('info', f"Initializing CMDR {self.config['commander_name']}'s personal AI...\n")
        show_chat_message('info', "API Key: Loaded")
        show_chat_message('info', f"Mic Mode: {self.config['ptt_var']}")
        show_chat_message('info', f"Using Function Calling: {self.config['tools_var']}")
        show_chat_message('info', f"Current model: {self.config['llm_model_name']}")
        show_chat_message('info', f"Current TTS voice: {self.character['tts_voice']}")
        show_chat_message('info', f"Current TTS Speed: {self.character['tts_speed']}")
        show_chat_message('info', "Current backstory: " + self.backstory)

        # TTS Setup
        show_chat_message('info', "Basic configuration complete.")
        show_chat_message('info', "Loading voice output...")

        # Microphone/Listening setup based on mode
        mode = self.config.get('ptt_var', 'voice_activation')
        ptt_key = self.config.get('ptt_key', '')
        if mode == 'push_to_talk' and ptt_key:
            log('info', f"Setting push-to-talk hotkey {ptt_key}.")
            self.controller_manager.register_hotkey(
                ptt_key,
                lambda _: self.stt.listen_once_start(),
                lambda _: self.stt.listen_once_end()
            )
        elif mode == 'push_to_mute' and ptt_key:
            log('info', f"Setting push-to-mute hotkey {ptt_key}.")
            self.stt.listen_continuous()
            self.controller_manager.register_hotkey(
                ptt_key,
                lambda _: self.stt.pause_continuous_listening(True),
                lambda _: self.stt.pause_continuous_listening(False)
            )
        elif mode == 'toggle' and ptt_key:
            log('info', f"Setting hotkey {ptt_key} to toggle voice activation.")
            self.stt.listen_continuous()
            self.stt.pause_continuous_listening(self.config.get('ptt_inverted_var', False))
            self.controller_manager.register_hotkey(
                ptt_key,
                lambda _: _,
                lambda _: self.stt.pause_continuous_listening(not self.stt.continuous_listening_paused)
            )
        else:
            log('info', f"Setting automatic voice activation.")
            self.stt.listen_continuous()
        show_chat_message('info', "Voice interface ready.")

        show_chat_message('info', 'Initializing states...')
        self.event_manager.add_historic_game_events(self.jn.historic_events)

        self.event_manager.add_status_event(self.status_parser.current_status)

        show_chat_message('info', 'Register projections...')
        registerProjections(self.event_manager, self.system_database, self.character.get('idle_timeout_var', 300))
        self.plugin_manager.register_projections(self.plugin_helper)

        self.event_manager.process()

        if self.config['tools_var']:
            log('info', "Register actions...")

            register_actions(
                self.action_manager,
                self.event_manager,
                self.llmClient,
                self.config["llm_model_name"],
                self.visionClient,
                self.config["vision_model_name"],
                self.embeddingClient,
                self.config["embedding_model_name"],
                self.ed_keys,
                self.config.get("discovery_primary_var", True),
                self.config.get("discovery_firegroup_var", 1),
                self.config.get("chat_local_tabbed_var", False),
                self.config.get("chat_wing_tabbed_var", False),
                self.config.get("chat_system_tabbed_var", True),
                self.config.get("chat_squadron_tabbed_var", False),
                self.config.get("chat_direct_tabbed_var", False),
                self.config.get("weapon_types", [])
            )

            log('info', "Built-in Actions ready.")
            self.plugin_manager.register_actions(self.plugin_helper)
            log('info', "Plugin provided Actions ready.")
            show_chat_message('info', "Actions ready.")


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
                if self.config.get("mute_during_response_var"):
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
                    self.event_manager.add_conversation_event('user', text)

                # check EDJournal files for updates
                while not self.jn.events.empty():
                    event = self.jn.events.get()
                    self.event_manager.add_game_event(event)

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
            if data.get("type") == "query_memories":
                query = data.get("query", "")
                top_k = data.get("top_k", 5)
                if query:
                    results = chat.query_memories(query, top_k)
                    print(json.dumps({
                        "type": "memory_results",
                        "timestamp": datetime.now().isoformat(),
                        "results": results
                    }) + '\n', flush=True)
            if data.get("type") == "get_memories_by_date":
                date_str = data.get("date", "")
                if date_str:
                    results = chat.get_memories_by_date(date_str)
                    print(json.dumps({
                        "type": "memories_by_date",
                        "timestamp": datetime.now().isoformat(),
                        "data": results
                    }) + '\n', flush=True)
            if data.get("type") == "get_available_dates":
                results = chat.get_available_dates()
                print(json.dumps({
                    "type": "available_dates",
                    "timestamp": datetime.now().isoformat(),
                    "data": results
                }) + '\n', flush=True)
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
