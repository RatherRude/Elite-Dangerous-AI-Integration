import json
import traceback
from openai.types.chat import ChatCompletion, ChatCompletionMessageToolCall
from time import time

from .Logger import log, observe, show_chat_message
from .Config import Config
from .Event import ConversationEvent, Event, GameEvent, StatusEvent, ToolEvent, ExternalEvent, ProjectedEvent, MemoryEvent
from .EventManager import EventManager
from .ActionManager import ActionManager
from .PromptGenerator import PromptGenerator
from .TTS import TTS
from openai import APIStatusError, BadRequestError, OpenAI, RateLimitError
from typing import Any,  Callable, final
from threading import Thread
from .actions.Actions import set_speed, fire_weapons, get_visuals

@final
class Assistant:
    def __init__(self, config: Config, enabled_game_events: list[str], event_manager: EventManager, action_manager: ActionManager, llmClient: OpenAI, tts: TTS, prompt_generator: PromptGenerator, embeddingClient: OpenAI | None = None, disabled_game_events: list[str] | None = None):
        self.config = config
        self.enabled_game_events = enabled_game_events
        self.disabled_game_events = disabled_game_events if disabled_game_events is not None else []
        self.event_manager = event_manager
        self.action_manager = action_manager
        self.llmClient = llmClient
        self.tts = tts
        self.prompt_generator = prompt_generator
        self.embeddingClient = embeddingClient
        self.is_replying = False
        self.reply_pending = False
        self.pending: list[Event] = []
        self.registered_should_reply_handlers: list[Callable[[Event, dict[str, Any]], bool | None]] = []
        self.is_summarizing = False
        self.short_term_memories = []

    def on_event(self, event: Event, projected_states: dict[str, Any]):
        # Skip disabled game events from entering the pending state
        if isinstance(event, GameEvent) or isinstance(event, StatusEvent):
            event_type = event.content.get('event') if isinstance(event, GameEvent) else event.status.get('event')
            if event_type in self.disabled_game_events:
                return

        self.pending.append(event)
        self.reply_pending = self.should_reply(projected_states)

        if isinstance(event, MemoryEvent):
            self.short_term_memories.append(event)
            self.short_term_memories = self.short_term_memories[-5:]

        # Auto actions after a hyperspace jump: optional autobrake and/or autoscan
        try:
            if (isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump' and
                    (self.config.get("qol_autoscan", False) or self.config.get("qol_autobrake", False))):
                # Build actions according to QoL flags
                request, results, descriptions, labels = [], [], [], []

                if self.config.get("qol_autobrake"):
                    speed_args = {"speed": "Zero"}
                    speed_result = set_speed(speed_args, projected_states)
                    request.append({"id": "auto-fsd-1", "type": "function", "function": {"name": "setSpeed", "arguments": json.dumps(speed_args)}})
                    results.append({"tool_call_id": "auto-fsd-1", "role": "tool", "name": "setSpeed", "content": speed_result})
                    descriptions.append("Reducing speed to 0")
                    labels.append("SetSpeedZero")

                if self.config.get("qol_autoscan"):
                    fire_args = {
                        "weaponType": "discovery_scanner",
                        "action": "fire",
                        "discoveryPrimary": self.config.get("discovery_primary_var", True),
                        "discoveryFiregroup": self.config.get("discovery_firegroup_var", 1),
                    }
                    fire_result = fire_weapons(fire_args, projected_states)
                    request.append({"id": "auto-fsd-2", "type": "function", "function": {"name": "fireWeapons", "arguments": json.dumps(fire_args)}})
                    results.append({"tool_call_id": "auto-fsd-2", "role": "tool", "name": "fireWeapons", "content": fire_result})
                    descriptions.append("Performing discovery scan")
                    labels.append("DiscoveryScan")

                if request:
                    self.event_manager.add_tool_call(request, results, descriptions)
        except Exception as e:
            log('error', 'Auto actions on FSDJump failed', e, traceback.format_exc())

        # Auto action on Screenshot: get visual description
        try:
            if (isinstance(event, GameEvent) and event.content.get('event') == 'Screenshot' and
                    self.config.get("vision_provider", '') != 'none'):

                visual_args = {"query": "Describe what you see in the game."}
                visual_result = get_visuals(visual_args, projected_states)

                request = [{"id": "auto-screenshot-1", "type": "function", "function": {"name": "getVisuals", "arguments": json.dumps(visual_args)}}]
                results = [{"tool_call_id": "auto-screenshot-1", "role": "tool", "name": "getVisuals", "content": visual_result}]
                descriptions = ["Analyzing screenshot"]
                
                self.event_manager.add_tool_call(request, results, descriptions)
        except Exception as e:
            log('error', 'Auto action on Screenshot failed', e, traceback.format_exc())

        if isinstance(event, ConversationEvent) and event.kind == 'assistant':
            short_term = self.event_manager.get_short_term_memory(1000)
            # Rate-limit by wall-clock time since the last MemoryEvent summary
            last_memory_time = self.short_term_memories[-1].processed_at if len(self.short_term_memories) else 0.0
            conversational_messages = [1 for e in short_term if isinstance(e, ConversationEvent) or isinstance(e, ToolEvent)]
            
            log(prefix='info', message=f'Short-term memory length: {len(short_term)} events ({len(conversational_messages)} conversational) since {last_memory_time}, already summarizing: {self.is_summarizing}')
            if (len(conversational_messages) > 40 or len(short_term) > 120) and not self.is_summarizing and (time() - last_memory_time) >= 60:
                log('info', f'Starting summarization of {len(short_term[30:])} events into long-term memory')
                self.is_summarizing = True
                Thread(target=self.summarize_memory, args=(short_term[30:],), daemon=True).start()

    @observe()
    def summarize_memory(self, memory: list[Event]):
        try:
            memory_until = 0.0
            memory_since = float("inf")
            for event in memory:
                memory_since = min(memory_since, event.processed_at) if event.processed_at > 0 else memory_since
                memory_until = max(memory_until, event.processed_at)

            if memory_since > memory_until:
                memory_since = memory_until

            chat = []

            for event in memory:
                if isinstance(event, GameEvent) or isinstance(event, ProjectedEvent):
                    event_description = self.prompt_generator.get_event_template(event)
                    if event_description:
                        chat.append(f"{event.content.get('timestamp', '')}: {event_description}")
                elif isinstance(event, StatusEvent):
                    if event.status.get('event','').lower() == 'status':
                        continue
                    event_description = self.prompt_generator.get_status_event_template(event)
                    if event_description:
                        chat.append(f"{event.status.get('timestamp', '')}: {event_description}")
                elif isinstance(event, ConversationEvent):
                    if event.kind not in ['user', 'assistant']:
                        continue
                    chat.append(event.timestamp +' '+ event.kind +': '+ event.content)
            for mem in self.short_term_memories:
                chat.append(mem.timestamp +' [Previous Memory]: '+ mem.content)

            chat_text = '\n'.join(reversed(chat))

            response = self.llmClient.chat.completions.create(  # pyright: ignore[reportCallIssue]
                model=self.config["llm_model_name"],
                messages=[
                    {"role": "system", "content": "You are a helpful assistant in Elite Dangerous that summarizes events and conversation into short concise notes for long-term memory storage. Only include important information that is not already stored in long-term memory. Do not include unimportant information, irrelevant details or repeated information. Do not include any timestamps in the summary.\nKeep it short to about 5 sentences."},
                    {"role": "user", "content": "Summarize the following events into short concise notes for long-term memory storage:\n<conversation>\n"+(chat_text)+'\n</conversation>'}],
                temperature=self.config["llm_temperature"],
            )

            embedding_response = self.embeddingClient.embeddings.create(
                model=self.config["embedding_model_name"],
                input=response.choices[0].message.content
            )
            embedding = embedding_response.data[0].embedding

            self.event_manager.add_memory_event(
                embedding_response.model,
                last_processed_at=memory_until,
                content=response.choices[0].message.content or 'Error',
                metadata={"original_text": chat_text, "event_count": len(memory), "time_until": memory_until, "time_since": memory_since},
                embedding=embedding
            )
            log('info', f'Summarized {len(memory)} events into long-term memory up to {memory_until}')
        except Exception as e:
            log("debug", "Error during memory summarization:", e, traceback.format_exc())
        finally:
            self.is_summarizing = False


    @observe()
    def execute_actions(self, actions: list[dict[str, Any]], projected_states: dict[str, dict]):
        action_descriptions: list[str | None] = []
        action_results: list[Any] = []
        for action in actions:
            action_input_desc = self.action_manager.getActionDesc(action, projected_states)
            action_descriptions.append(action_input_desc)
            if action_input_desc:
                self.tts.say(action_input_desc)
            action_result = self.action_manager.runAction(action, projected_states)
            action_results.append(action_result)

            self.event_manager.add_tool_call([action.model_dump()], [action_result], [action_input_desc] if action_input_desc else None)


    def verify_action(self, user_input: str, action: ChatCompletionMessageToolCall, prompt: list, tools: list):
        """ Verify the action prediction by sending the user input without any context to the model and check if the action is still predicted """
        log("debug", "Cache: Verifying action", user_input, action)
        
        cache_state = self.action_manager.has_action_in_cache(user_input, action, tools)
        if cache_state == False:
            self.action_manager.suggest_action_for_cache(user_input, action, tools)
            return
        
        if cache_state == "confirmed":
            log("debug", "Cache: Action already confirmed in cache, skipping verification")
            return
        
        # confirm the action by sending the user input to the model without any context

        completion = self.llmClient.chat.completions.create(
            model=self.config["llm_model_name"],
            messages=[prompt[0]] + [{"role": "user", "content": user_input}],
            temperature=0,
            tools=tools
        )
        
        if not isinstance(completion, ChatCompletion) or hasattr(completion, 'error'):
            log("debug", "Cache: error during action verification:", completion)
            return
        if not completion.choices:
            log("debug", "Cache: LLM completion has no choices:", completion)
            return

        if completion.choices[0].message.tool_calls:
            self.action_manager.confirm_action_in_cache(user_input, completion.choices[0].message.tool_calls[0], tools)


    def reply(self, events: list[Event], projected_states: dict[str, dict]):
        if self.is_replying:
            log('debug', 'Cache: Reply already in progress, skipping new reply')
            return
        thread = Thread(target=self.reply_thread, args=(events, projected_states), daemon=True)
        thread.start()
        
    @observe()
    def reply_thread(self, events: list[Event], projected_states: dict[str, dict]):
        self.reply_pending = False
        self.is_replying = True
        try:
            events = self.event_manager.get_short_term_memory(150)
            events = list(reversed(events))
            new_events = [event for event in events if event.responded_at == None]
            self.pending = []


            log('debug', 'Starting reply...')
            max_conversation_processed = max([event.processed_at for event in events]+[0.0])
            prompt = self.prompt_generator.generate_prompt(events=events, projected_states=projected_states, pending_events=new_events)

            user_input: list[str] = [event.content for event in new_events if event.kind == 'user']
            tool_uses: int = len([event for event in new_events if event.kind == 'tool'])
            reasons = [event.content.get('event', event.kind) if event.kind=='game' else event.kind for event in new_events if event.kind in ['user', 'game', 'tool', 'status']]
            use_tools = self.config["tools_var"] and ('user' in reasons or 'tool' in reasons)

            current_status = projected_states.get("CurrentStatus")
            flags = current_status["flags"]
            flags2 = current_status["flags2"]

            active_mode = None
            if flags:
                if flags["InMainShip"]:
                    active_mode = "mainship"
                elif flags["InFighter"]:
                    active_mode = "fighter"
                elif flags["InSRV"]:
                    active_mode = "buggy"
            if flags2:
                if flags2["OnFoot"]:
                    active_mode = "humanoid"

            uses_actions = self.config["game_actions_var"]
            uses_web_actions = self.config["web_search_actions_var"]
            uses_ui_actions = self.config["ui_actions_var"]
            # append allowed actions from config
            allowed_actions = self.config.get("allowed_actions", [])
            tool_list = self.action_manager.getToolsList(active_mode, uses_actions, uses_web_actions, uses_ui_actions, allowed_actions) if use_tools else None
            predicted_actions = None
            if tool_list and user_input and not tool_uses and self.config["use_action_cache_var"]:
                predicted_actions = self.action_manager.predict_action(user_input[-1], tool_list)
                
            if predicted_actions:
                #log('info', 'predicted_actions', predicted_actions)
                response_text = None
                response_actions = predicted_actions
            else:
                start_time = time()
                llm_params: dict[str, str] = {}
                if self.config["llm_model_name"] in ['gpt-5', 'gpt-5-mini', 'gpt-5-nano']:
                    llm_params["verbosity"] = "low"
                    llm_params["reasoning_effort"] = "minimal"
                    
                try:
                    response = self.llmClient.chat.completions.with_raw_response.create(  # pyright: ignore[reportCallIssue]
                        model=self.config["llm_model_name"],
                        messages=prompt,
                        temperature=self.config["llm_temperature"],
                        tools=tool_list,  # pyright: ignore[reportArgumentType]
                        **llm_params,  # pyright: ignore[reportArgumentType]
                    )
                    end_time = time()
                    log('debug', 'Response time LLM', end_time - start_time)
                except APIStatusError as e:
                    log("debug", "LLM error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
                    log("debug", "LLM error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
                    
                    try:
                        error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                        message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
                    except:
                        message = e.message
                    
                    show_chat_message('error', f'LLM {e.response.reason_phrase}:', message)
                    return
                
                completion = response.parse()
                
                if not isinstance(completion, ChatCompletion) or hasattr(completion, 'error'):
                    log("debug", "LLM completion error request:", response.http_request.method, response.http_request.url, response.http_request.headers, response.http_request.read().decode('utf-8', errors='replace'))
                    log("debug", "LLM completion error:", completion)
                    show_chat_message("error", "LLM error: No valid completion received")
                    return
                if not completion.choices:
                    log("debug", "LLM completion has no choices:", completion)
                    show_chat_message("covas", "...")
                    return
                if not hasattr(completion.choices[0], 'message') or not completion.choices[0].message:
                    log("debug", "LLM completion choice has no message:", completion)
                    show_chat_message("covas", "...")
                    return
                
                if hasattr(completion, 'usage') and completion.usage:
                    log("debug", f'LLM completion usage', completion.usage)
                
                if hasattr(completion.choices[0].message, 'content'):
                    response_text = completion.choices[0].message.content
                    if completion.choices[0].message.content is None or completion.choices[0].message.content == "":
                        log("debug", "LLM completion no content:", completion)
                        show_chat_message("covas", "...")
                else:
                    log("debug", f'LLM completion without text')
                    response_text = None

                if hasattr(completion.choices[0].message, 'tool_calls'):
                    response_actions = completion.choices[0].message.tool_calls
                else:
                    response_actions = None

            if response_text and not response_actions:
                self.tts.say(response_text)
                self.event_manager.add_conversation_event('assistant', completion.choices[0].message.content, reasons=reasons, processed_at=max_conversation_processed)
                self.tts.wait_for_completion()
                self.event_manager.add_assistant_complete_event()

            if response_actions:
                self.event_manager.add_assistant_acting(processed_at=max_conversation_processed)
                self.execute_actions(response_actions, projected_states)

                if not predicted_actions and self.config["use_action_cache_var"]:
                    if len(response_actions) == 1 and len(user_input):
                        self.verify_action(user_input[-1], response_actions[0], prompt, tool_list)
                    
        except Exception as e:
            log("debug", "LLM error during reply:", e, traceback.format_exc())
            show_chat_message("error", "LLM error: An unknown error occurred during reply")
        finally:
            self.is_replying = False

    def should_reply(self, states:dict[str, Any]):
        character = self.config['characters'][self.config['active_character_index']]
        if len(self.pending) == 0:
            return False

        for event in self.pending:
            # check if pending contains conversational events
            if isinstance(event, ConversationEvent) and event.kind == "user":
                return True

            if isinstance(event, ToolEvent):
                return True

            if isinstance(event, GameEvent) and event.content.get("event") in self.enabled_game_events:
                if event.content.get("event") == "ReceiveText":
                    if event.content.get("Channel") not in ['wing', 'voicechat', 'friend', 'player'] and (
                        (not character["react_to_text_local_var"] and event.content.get("Channel") == 'local') or
                        (not character["react_to_text_starsystem_var"] and event.content.get("Channel") == 'starsystem') or
                        (not character["react_to_text_npc_var"] and event.content.get("Channel") == 'npc') or
                        (not character["react_to_text_squadron_var"] and event.content.get("Channel") == 'squadron')):
                        continue

                if event.content.get("event") == "ProspectedAsteroid":
                    chunks = [chunk.strip() for chunk in character["react_to_material"].split(",")]
                    contains_material = False
                    for chunk in chunks:
                        for material in event.content.get("Materials"):
                            if chunk.lower() in material["Name"].lower():
                                contains_material = True
                        if event.content.get("MotherlodeMaterial", False):
                            if chunk.lower() in event.content['MotherlodeMaterial'].lower():
                                contains_material = True

                    if not contains_material:
                        continue

                if event.content.get("event") == "ScanOrganic":
                    continue

                return True

            if isinstance(event, StatusEvent) and event.status.get("event") in self.enabled_game_events:
                if event.status.get("event") in ["InDanger", "OutOfDanger"]:
                    if not character["react_to_danger_mining_var"]:
                        if states.get('ShipInfo', {}).get('IsMiningShip', False) and states.get('Location', {}).get('PlanetaryRing', False):
                            continue
                    if not character["react_to_danger_onfoot_var"]:
                        if states.get('CurrentStatus', {}).get('flags2').get('OnFoot'):
                            continue
                    if not character["react_to_danger_supercruise_var"]:
                        if states.get('CurrentStatus', {}).get('flags').get('Supercruise') and len(states.get('NavInfo', {"NavRoute": []}).get('NavRoute', [])):
                            continue
                return True

            if isinstance(event, ExternalEvent):
                if event.content.get("event") == "ExternalTwitchMessage":
                    continue
                return True

            if isinstance(event, ProjectedEvent):
                if event.content.get("event").startswith('ScanOrganic') and 'ScanOrganic' in self.enabled_game_events:
                    return True
                if event.content.get("event") in self.enabled_game_events:
                    return True
            
            # run should_reply handlers for each plugin
            for handler in self.registered_should_reply_handlers:
                should_reply_according_to_plugins = handler(event, states)
                if should_reply_according_to_plugins :
                    return True
                elif should_reply_according_to_plugins is False:
                    pass
                else:
                    continue

        return False
    
    def register_should_reply_handler(self, handler: Callable[[Event, dict[str, Any]], bool | None]):
        self.registered_should_reply_handlers.append(handler)
