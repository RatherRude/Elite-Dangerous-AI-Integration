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
from lib.Models import create_llm_model, LLMModel, create_embedding_model, EmbeddingModel, create_stt_model, STTModel, create_tts_model, TTSModel

from lib.PluginHelper import PluginHelper
from lib.Config import Config, assign_ptt, get_ed_appdata_path, get_ed_journals_path, get_system_info, load_config, save_config, update_config, update_event_config, validate_config, update_character, reset_game_events
from lib.PluginManager import PluginManager
from lib.ActionManager import ActionManager


def parse_plugin_provider(provider: str) -> tuple[str, str] | None:
    """
    Parse a plugin provider string in format 'plugin:<guid>:<id>'.
    
    Returns:
        Tuple of (plugin_guid, provider_id) or None if not a plugin provider
    """
    if not provider.startswith('plugin:'):
        return None
    parts = provider.split(':', 2)
    if len(parts) != 3:
        return None
    return (parts[1], parts[2])
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
        disabled_events: list[str] = []
        event_reactions = self.character.get("event_reactions", {})
        if self.character.get("event_reaction_enabled_var", False):
            for event, state in event_reactions.items():
                if state == "on":
                    self.enabled_game_events.append(event)
                if state == "hidden":
                    disabled_events.append(event)

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
        # LLM model - check for plugin provider
        llm_plugin = parse_plugin_provider(self.config["llm_provider"])
        if llm_plugin:
            model = self.plugin_manager.create_plugin_model(llm_plugin[0], llm_plugin[1], 'llm')
            if model is None:
                show_chat_message("error", f"Failed to create LLM from plugin provider. Check logs for details.")
                raise RuntimeError(f"Failed to create LLM from plugin provider {self.config['llm_provider']}")
            self.llmModel = cast(LLMModel, model)
        else:
            self.llmModel = create_llm_model(self.config["llm_provider"], self.config, "llm")
        
        # Agent LLM model - check for plugin provider
        agent_llm_plugin = parse_plugin_provider(self.config["agent_llm_provider"])
        if agent_llm_plugin:
            model = self.plugin_manager.create_plugin_model(agent_llm_plugin[0], agent_llm_plugin[1], 'llm')
            if model is None:
                show_chat_message("error", f"Failed to create Agent LLM from plugin provider. Check logs for details.")
                raise RuntimeError(f"Failed to create Agent LLM from plugin provider {self.config['agent_llm_provider']}")
            self.agent_llm_model = cast(LLMModel, model)
        else:
            self.agent_llm_model = create_llm_model(self.config["agent_llm_provider"], self.config, "agent_llm")

        # embeddings
        self.embeddingModel: EmbeddingModel | None = None
        embedding_provider = self.config.get("embedding_provider", "")
        embedding_plugin = parse_plugin_provider(embedding_provider)
        if embedding_plugin:
            model = self.plugin_manager.create_plugin_model(embedding_plugin[0], embedding_plugin[1], 'embedding')
            if model is None:
                show_chat_message("warning", f"Failed to create Embedding model from plugin provider. Embeddings disabled.")
            else:
                self.embeddingModel = cast(EmbeddingModel, model)
        elif embedding_provider in ['openai', 'custom', 'google-ai-studio', 'local-ai-server']:
            self.embeddingModel = create_embedding_model(embedding_provider, self.config, "embedding")

        # vision
        self.visionModel: LLMModel | None = None
        if self.config["vision_var"]:
            vision_provider = self.config.get("vision_provider", "openai")
            vision_plugin = parse_plugin_provider(vision_provider)
            if vision_plugin:
                model = self.plugin_manager.create_plugin_model(vision_plugin[0], vision_plugin[1], 'llm')
                if model is None:
                    show_chat_message("warning", f"Failed to create Vision model from plugin provider. Vision disabled.")
                else:
                    self.visionModel = cast(LLMModel, model)
            else:
                self.visionModel = create_llm_model(vision_provider, self.config, "vision")
            

        log("debug", "Initializing Speech processing...")
        self.sttModel: STTModel | None = None
        if self.config["stt_provider"] != 'none':
            stt_plugin = parse_plugin_provider(self.config["stt_provider"])
            if stt_plugin:
                model = self.plugin_manager.create_plugin_model(stt_plugin[0], stt_plugin[1], 'stt')
                if model is None:
                    show_chat_message("warning", f"Failed to create STT model from plugin provider. STT disabled.")
                else:
                    self.sttModel = cast(STTModel, model)
            else:
                self.sttModel = create_stt_model(self.config["stt_provider"], self.config, "stt")

        self.ttsModel: TTSModel | None = None
        if self.config["tts_provider"] != 'none':
            tts_plugin = parse_plugin_provider(self.config["tts_provider"])
            if tts_plugin:
                model = self.plugin_manager.create_plugin_model(tts_plugin[0], tts_plugin[1], 'tts')
                if model is None:
                    show_chat_message("warning", f"Failed to create TTS model from plugin provider. TTS disabled.")
                else:
                    self.ttsModel = cast(TTSModel, model)
            else:
                # Create a config copy with character specific settings
                tts_config = dict(self.config.copy())
                tts_config["tts_speed"] = float(self.character["tts_speed"])
                tts_config["tts_voice_instructions"] = self.character["tts_prompt"]
                self.ttsModel = create_tts_model(self.config["tts_provider"], tts_config, "tts")
            
        self.tts = TTS(tts_model=self.ttsModel, voice=self.character["tts_voice"], speed=float(self.character["tts_speed"]), output_device=self.config["output_device_name"])
        self.stt = STT(stt_model=self.sttModel, input_device_name=self.config["input_device_name"], required_word=self.config["stt_required_word"])

        log("debug", "Initializing SystemDatabase...")
        self.system_database = SystemDatabase()
        log("debug", "Initializing EDKeys...")
        self.ed_keys = EDKeys(
            get_ed_appdata_path(config),
            prefer_primary_bindings=self.config.get("prefer_primary_bindings", False),
        )
        log("debug", "Initializing status parser...")
        self.status_parser = StatusParser(get_ed_journals_path(config))
        log("debug", "Initializing prompt generator...")
        self.prompt_generator = PromptGenerator(self.config["commander_name"], self.character["character"], important_game_events=self.enabled_game_events, system_db=self.system_database, weapon_types=cast(list[dict], self.config.get("weapon_types", [])), disabled_game_events=disabled_events)

        log("debug", "Initializing event manager...")
        self.event_manager = EventManager(
            game_events=self.enabled_game_events,
        )

        log("debug", message="Initializing assistant...")
        self.assistant = Assistant(
            config=self.config,
            enabled_game_events=self.enabled_game_events,
            event_manager=self.event_manager,
            action_manager=self.action_manager,
            llmModel=self.llmModel,
            tts=self.tts,
            prompt_generator=self.prompt_generator,
            embeddingModel=self.embeddingModel,
            disabled_game_events=disabled_events
        )
        self.is_replying = False
        self.listening = False

        log("debug", "Registering side effect...")
        self.event_manager.register_sideeffect(self.on_event)
        self.event_manager.register_sideeffect(self.assistant.on_event)
        
        self.plugin_helper = PluginHelper(self.plugin_manager, self.prompt_generator, config, self.action_manager, self.event_manager, self.llmModel, self.visionModel, self.system_database, self.ed_keys, self.assistant)
        log("debug", "Plugin helper is ready...")

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

        if isinstance(event, GameEvent) and event.content.get('event') == 'FSSDiscoveryScan':
            self.system_database.record_discovery_scan(cast(dict[str, Any], event.content))
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSSSignalDiscovered':
            self.system_database.record_signal(cast(dict[str, Any], event.content))
        if isinstance(event, GameEvent) and event.content.get('event') == 'Scan':
            self.system_database.record_scan(cast(dict[str, Any], event.content))
        if isinstance(event, GameEvent) and event.content.get('event') == 'ScanBaryCentre':
            bary_event = dict(event.content)
            body_id = bary_event.get("BodyID")
            if body_id is not None:
                bary_event.setdefault("BodyName", f"Barycentre {body_id}")
            bary_event.setdefault("BodyType", "Barycentre")
            self.system_database.record_scan(cast(dict[str, Any], bary_event))
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDTarget':
            self.system_database.record_fsd_target(cast(dict[str, Any], event.content))
        if isinstance(event, GameEvent) and event.content.get('event') == 'SAASignalsFound':
            self.system_database.record_saa_signals_found(cast(dict[str, Any], event.content))
        if isinstance(event, GameEvent) and event.content.get('event') == 'ScanOrganic':
            self.system_database.record_scan_organic(cast(dict[str, Any], event.content))

    def submit_input(self, input: str):
        self.event_manager.add_conversation_event('user', input)
    
    def query_memories(self, query: str, top_k: int = 5):
        """Query long-term memories without triggering LLM interaction"""
        if not self.embeddingModel:
            return {"error": "Embeddings model not configured"}
        
        try:
            # Create embedding for the query
            (model_name, embedding) = self.embeddingModel.create_embedding(query)
            
            # Search the vector store
            results = self.event_manager.long_term_memory.search(
                query,
                model_name, 
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

    def get_system_event_data(self, system_address: int | str | None):
        """Fetch cached system event data for a given system address."""
        if system_address is None:
            return {"error": "system_address is required"}
        try:
            address_int = int(system_address)
        except (TypeError, ValueError):
            return {"error": "Invalid system_address"}

        try:
            record = self.system_database.get_system_by_address(address_int)
            if record is None:
                return {"data": None}
            return {"data": record}
        except Exception as e:
            log('error', f'Error fetching system event data: {e}')
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
        registerProjections(
            self.event_manager,
            self.system_database,
            self.character.get('idle_timeout_var', 300),
        )

        self.event_manager.process()

        if self.config['tools_var']:
            log('info', "Register actions...")

            register_actions(
                actionManager=self.action_manager,
                eventManager=self.event_manager,
                promptGenerator=self.prompt_generator,
                llmModel=self.llmModel,
                visionModel=self.visionModel,
                visionModelName=self.config["vision_model_name"],
                embeddingModel=self.embeddingModel,
                edKeys=self.ed_keys,
                discovery_primary_var_flag=self.config.get("discovery_primary_var", True),
                discovery_firegroup_var_flag=self.config.get("discovery_firegroup_var", 1),
                chat_local_tabbed_flag=self.config.get("chat_local_tabbed_var", False),
                chat_wing_tabbed_flag=self.config.get("chat_wing_tabbed_var", False),
                chat_system_tabbed_flag=self.config.get("chat_system_tabbed_var", True),
                chat_squadron_tabbed_flag=self.config.get("chat_squadron_tabbed_var", False),
                chat_direct_tabbed_flag=self.config.get("chat_direct_tabbed_var", False),
                overlay_show_hud=self.config.get("overlay_show_hud", False),
                weapon_types_list=self.config.get("weapon_types", []),
                agent_llm_model=self.agent_llm_model,
                agent_llm_max_tries=self.config.get("agent_llm_max_tries", 7),
            )

            log('info', "Actions ready.")
            show_chat_message('info', "Actions ready.")


        # Execute plugin helper ready hooks
        self.plugin_manager.on_chat_start(self.plugin_helper)
        show_chat_message('info', "Plugins ready.")

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

    def web_search(self, query: str):
        """Perform a web search using the assistant's action manager"""
        _, projected_states = self.event_manager.get_current_state()
        self.assistant.web_search(query, projected_states)


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
            if data.get("type") == "get_system_events":
                system_address = data.get("system_address")
                results = chat.get_system_event_data(system_address)
                print(json.dumps({
                    "type": "system_events",
                    "timestamp": datetime.now().isoformat(),
                    "system_address": system_address,
                    "data": results
                }) + '\n', flush=True)
            if data.get("type") == "init_overlay":
                print(json.dumps({"type": "running_config", "config": config})+'\n', flush=True)
            if data.get("type") == "web_search":
                query = data.get("query", "")
                if query:
                    chat.web_search(query)

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
        # Wait for start signal on stdin
        config = load_config()
        print(json.dumps({"type": "config", "config": config})+'\n', flush=True)
        system = get_system_info()
        print(json.dumps({"type": "system", "system": system})+'\n', flush=True)

        ed_keys = EDKeys(
            get_ed_appdata_path(config),
            prefer_primary_bindings=config.get("prefer_primary_bindings", False),
        )
        # Load plugins.
        log('debug', "Loading plugins...")
        plugin_manager = PluginManager(config=config)
        plugin_manager.load_plugins()
        log('debug', "Registering plugin settings for the UI...")
        plugin_manager.register_settings()
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
                    plugin_manager.on_settings_changed(config)
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
                if data.get("type") == "enable_remote_tracing":
                    from lib.Logger import enable_remote_tracing
                    enable_remote_tracing(config['commander_name'], data.get('resourceAttributes', {}))

            except json.JSONDecodeError:
                continue
        
        # Once start signal received, initialize and run chat
        save_config(config)
        plugin_manager.on_settings_changed(config)
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
