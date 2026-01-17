import json
import traceback
from datetime import datetime
from openai.types.chat import ChatCompletion, ChatCompletionMessageToolCall
from time import time

from pydantic import BaseModel
from .Models import LLMModel, EmbeddingModel, LLMError
from .Logger import log, observe, show_chat_message
from .Config import Config
from .Event import ConversationEvent, Event, GameEvent, StatusEvent, ToolEvent, ExternalEvent, ProjectedEvent, MemoryEvent
from .EventManager import EventManager
from .ActionManager import ActionManager
from .PromptGenerator import PromptGenerator
from .TTS import TTS
from typing import Any,  Callable, final
from threading import Thread
from .actions.Actions import set_speed, fire_weapons, get_visuals
from .Projections import get_state_dict, ProjectedStates

@final
class Assistant:
    def __init__(self, config: Config, enabled_game_events: list[str], event_manager: EventManager, action_manager: ActionManager, llmModel: LLMModel, tts: TTS, prompt_generator: PromptGenerator, embeddingModel: EmbeddingModel | None = None, disabled_game_events: list[str] | None = None):
        self.config = config
        self.enabled_game_events = enabled_game_events
        self.disabled_game_events = disabled_game_events if disabled_game_events is not None else []
        self.event_manager = event_manager
        self.action_manager = action_manager
        self.llmModel = llmModel
        self.tts = tts
        self.prompt_generator = prompt_generator
        self.embeddingModel = embeddingModel
        self.is_replying = False
        self.reply_pending = False
        self.pending: list[Event] = []
        self.registered_should_reply_handlers: list[Callable[[Event, dict[str, Any]], bool | None]] = []
        self.is_summarizing = False
        self.short_term_memories = []

    def on_event(self, event: Event, projected_states: ProjectedStates):
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
                if self.config.get("qol_autobrake"):
                    speed_args = {"speed": "Zero"}
                    set_speed(speed_args, projected_states)

                if self.config.get("qol_autoscane"):
                    fire_args = {
                        "weaponType": "discovery_scanner",
                        "action": "fire",
                        "discoveryPrimary": self.config.get("discovery_primary_var", True),
                        "discoveryFiregroup": self.config.get("discovery_firegroup_var", 1),
                    }
                    fire_weapons(fire_args, projected_states)
        except Exception as e:
            log('error', 'Auto actions on FSDJump failed', e, traceback.format_exc())

        # Auto action on Screenshot: get visual description
        try:
            if (isinstance(event, GameEvent) and event.content.get('event') == 'Screenshot' and
                    self.config.get("vision_provider", '') != 'none') and self.config['characters'][0].get('event_reactions', {}).get('Screenshot') == 'on':

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
            
            if not self.llmModel:
                log('warn', 'LLM model not configured, cannot summarize memories.')
                return
            
            if not self.embeddingModel:
                log('warn', 'Embeddings model not configured, cannot summarize memories.')
                return

            response_text, _ = self.llmModel.generate(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant in Elite Dangerous that summarizes events and conversation into short concise notes for long-term memory storage. Only include important information that is not already stored in long-term memory. Do not include unimportant information, irrelevant details or repeated information. Do not include any timestamps in the summary.\nKeep it short to about 5 sentences."},
                    {"role": "user", "content": "Summarize the following events into short concise notes for long-term memory storage:\n<conversation>\n"+(chat_text)+'\n</conversation>'}],
            )

            (model_name, embedding) = self.embeddingModel.create_embedding(response_text or "")

            self.event_manager.add_memory_event(
                model_name=model_name,
                last_processed_at=memory_until,
                content=response_text or 'Error',
                metadata={"original_text": chat_text, "event_count": len(memory), "time_until": memory_until, "time_since": memory_since},
                embedding=embedding
            )
            log('info', f'Summarized {len(memory)} events into long-term memory up to {memory_until}')
        except Exception as e:
            log("error", "Error during memory summarization:", e, traceback.format_exc())
        finally:
            self.is_summarizing = False


    @observe()
    def execute_actions(self, actions: list[ChatCompletionMessageToolCall], projected_states: ProjectedStates):
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

        try:
            _, response_actions = self.llmModel.generate(
                messages=[prompt[0]] + [{"role": "user", "content": user_input}],
                tools=tools
            )
            
            if response_actions:
                self.action_manager.confirm_action_in_cache(user_input, response_actions[0], tools)
        except LLMError as e:
            log("error", "Cache: error during action verification:", e, traceback.format_exc())
            return


    def reply(self, events: list[Event], projected_states: ProjectedStates):
        if self.is_replying:
            log('debug', 'Cache: Reply already in progress, skipping new reply')
            return
        thread = Thread(target=self.reply_thread, args=(events, projected_states), daemon=True)
        thread.start()
        
    @observe()
    def reply_thread(self, events: list[Event], projected_states: ProjectedStates):
        self.reply_pending = False
        self.is_replying = True
        try:
            events = self.event_manager.get_short_term_memory(150)
            events = list(reversed(events))
            new_events = [event for event in events if event.responded_at == None]
            self.pending = []
            
            memories = self.event_manager.get_latest_memories(limit=5)


            log('debug', 'Starting reply...')
            max_conversation_processed = max([event.processed_at for event in events]+[0.0])
            prompt = self.prompt_generator.generate_prompt(events=events, projected_states=projected_states, pending_events=new_events, memories=memories)

            user_input: list[str] = [event.content for event in new_events if isinstance(event, ConversationEvent) and event.kind == 'user']
            tool_uses: int = len([event for event in new_events if event.kind == 'tool'])
            reasons = []
            for event in new_events:
                if event.kind in ['user', 'game', 'tool', 'status']:
                    if isinstance(event, GameEvent):
                        reasons.append(event.content.get('event', event.kind))
                    else:
                        reasons.append(event.kind)
            
            use_tools = self.config["tools_var"] and ('user' in reasons or 'tool' in reasons)

            current_status = get_state_dict(projected_states, "CurrentStatus")
            flags = current_status.get("flags", {})
            flags2 = current_status.get("flags2", {})

            active_mode = None
            if flags:
                if flags.get("InMainShip"):
                    active_mode = "mainship"
                elif flags.get("InFighter"):
                    active_mode = "fighter"
                elif flags.get("InSRV"):
                    active_mode = "buggy"
            if flags2:
                if flags2.get("OnFoot"):
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
                    
                try:
                    response_text, response_actions = self.llmModel.generate(
                        messages=prompt,
                        tools=tool_list,  # pyright: ignore[reportArgumentType]
                    )
                    if not response_text and not response_actions:
                        response_text = "..."
                    end_time = time()
                    log('debug', 'Response time LLM', end_time - start_time)
                except LLMError as e:
                    show_chat_message('error', 'LLM Error:', str(e))
                    return

            if response_text and not response_actions:
                self.tts.say(response_text)
                self.event_manager.add_conversation_event('assistant', response_text, reasons=reasons, processed_at=max_conversation_processed)
                self.tts.wait_for_completion()
                self.event_manager.add_assistant_complete_event()

            if response_actions:
                self.event_manager.add_assistant_acting(processed_at=max_conversation_processed)
                self.execute_actions(response_actions, projected_states)

                if not predicted_actions and self.config["use_action_cache_var"] and tool_list:
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
                if getattr(event, 'do_not_reply', False):
                    continue
                return True

            if isinstance(event, ToolEvent):
                if getattr(event, 'do_not_reply', False):
                    continue
                return True

            if isinstance(event, GameEvent) and event.content.get("event") in self.enabled_game_events:
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
    
    def register_should_reply_handler(self, handler: Callable[[Event, ProjectedStates], bool | None]):
        self.registered_should_reply_handlers.append(handler)

    @observe()
    def web_search(self, query: str, projected_states: ProjectedStates):
        action_name = 'web_search_agent'
        action_descriptor = self.action_manager.actions.get(action_name)
        
        if not action_descriptor:
            log('error', f"Action {action_name} not found")
            return


        method = action_descriptor.get('method')
        args = {'query': query}
        self.tts.say(f"Searching: {query}")
        
        try:
            result_content = method(args, projected_states)
        except Exception as e:
            log('error', f"Error executing {action_name}", e)
            result_content = f"Error: {e}"

        request = [{
            "id": f"call_{int(datetime.now().timestamp())}",
            "type": "function",
            "function": {
                "name": action_name,
                "arguments": json.dumps(args)
            }
        }]
        
        results = [{
            "tool_call_id": request[0]['id'],
            "role": "tool",
            "name": action_name,
            "content": result_content
        }]
        
        # Add tool event, also not triggering a reply
        self.event_manager.add_conversation_event('user', query)
        self.event_manager.add_tool_call(request, results, [f"Searching: {query}"])
