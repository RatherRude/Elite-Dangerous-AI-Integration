import json
import traceback
from openai.types.chat import ChatCompletion
from time import time

from .Logger import log
from .Config import Config
from .Event import ConversationEvent, Event, GameEvent, StatusEvent, ToolEvent, ExternalEvent, ProjectedEvent, ArchiveEvent
from .EventManager import EventManager
from .ActionManager import ActionManager
from .PromptGenerator import PromptGenerator
from .TTS import TTS
from .EDCoPilot import EDCoPilot
from openai import APIStatusError, BadRequestError, OpenAI, RateLimitError
from typing import Any,  Callable, final
from threading import Thread

@final
class Assistant:
    def __init__(self, config: Config, enabled_game_events: list[str], event_manager: EventManager, action_manager: ActionManager, llmClient: OpenAI, tts: TTS, prompt_generator: PromptGenerator, copilot: EDCoPilot):
        self.config = config
        self.enabled_game_events = enabled_game_events
        self.event_manager = event_manager
        self.action_manager = action_manager
        self.llmClient = llmClient
        self.tts = tts
        self.prompt_generator = prompt_generator
        self.copilot = copilot
        self.is_replying = False
        self.reply_pending = False
        self.pending: list[Event] = []
        self.registered_should_reply_handlers: list[Callable[[Event, dict[str, Any]], bool | None]] = []
    
    def on_event(self, event: Event, projected_states: dict[str, Any]):
        self.pending.append(event)
        self.reply_pending = self.should_reply(projected_states)

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

            if action_result['content'] != '': # We don't add a response if the return from an action is blank
                self.event_manager.add_tool_call([action.model_dump()], [action_result], [action_input_desc] if action_input_desc else None)


    def verify_action(self, user_input: list[str], action: dict[str, Any], prompt: list, tools: list):
        """ Verify the action prediction by sending the user input without any context to the model and check if the action is still predicted """
        log("debug", "Verifying action:", user_input, action)
        
        draft_action = self.action_manager.has_prediction_draft(user_input, tools)
        if not draft_action:
            self.action_manager.save_prediction_draft(user_input, action, tools)
            return
        
        completion = self.llmClient.chat.completions.create(
            model=self.config["llm_model_name"],
            messages=[prompt[0]] + [{"role": "user", "content": user} for user in user_input],
            tools=tools
        )
        
        if not isinstance(completion, ChatCompletion) or hasattr(completion, 'error'):
            log("debug", "error during action verification:", completion)
            return

        self.action_manager.save_prediction_verification(user_input, action, completion.choices[0].message.tool_calls, tools)


    def reply(self, events: list[Event], projected_states: dict[str, dict]):
        if self.is_replying:
            log('debug', 'Reply already in progress, skipping new reply')
            return
        thread = Thread(target=self.reply_thread, args=(events, projected_states), daemon=True)
        thread.start()
        
        
    def reply_thread(self, events: list[Event], projected_states: dict[str, dict]):
        self.reply_pending = False
        self.is_replying = True
        try:
            new_events = self.pending.copy()
            self.pending = []
            
            log('debug', 'Starting reply...')
            prompt = self.prompt_generator.generate_prompt(events=events, projected_states=projected_states, pending_events=new_events)

            user_input: list[str] = [event.content for event in new_events if event.kind == 'user']
            use_tools = self.config["tools_var"] and len(user_input)
            reasons = [event.content.get('event', event.kind) if event.kind=='game' else event.kind for event in new_events if event.kind in ['user', 'game', 'tool', 'status']]

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
            tool_list = self.action_manager.getToolsList(active_mode, uses_actions, uses_web_actions) if use_tools else None
            predicted_actions = None
            if tool_list and user_input:
                predicted_actions = self.action_manager.predict_action(user_input, tool_list)
                
            if predicted_actions:
                #log('info', 'predicted_actions', predicted_actions)
                response_text = None
                response_actions = predicted_actions
            else:
                start_time = time()
                try:
                    response = self.llmClient.chat.completions.with_raw_response.create(
                        model=self.config["llm_model_name"],
                        messages=prompt,
                        temperature=0,
                        tools=tool_list
                    )
                    end_time = time()
                    log('debug', 'Response time LLM', end_time - start_time)
                except APIStatusError as e:
                    log("debug", "LLM error request:", e.request.method, e.request.url, e.request.headers, e.request.content.decode('utf-8', errors='replace'))
                    log("debug", "LLM error response:", e.response.status_code, e.response.headers, e.response.content.decode('utf-8', errors='replace'))
                    
                    try:
                        error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                        message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
                    except:
                        message = e.message
                    
                    log('error', f'LLM {e.response.reason_phrase}:', message)
                    return
                
                completion = response.parse()
                
                if not isinstance(completion, ChatCompletion) or hasattr(completion, 'error'):
                    log("debug", "LLM completion error request:", response.http_request.method, response.http_request.url, response.http_request.headers, response.http_request.content.decode('utf-8', errors='replace'))
                    log("debug", "LLM completion error:", completion)
                    log("error", "LLM error: No valid completion received")
                    return
                if not completion.choices:
                    log("debug", "LLM completion has no choices:", completion)
                    log("error", "LLM error: No valid response choices received")
                    return
                if not hasattr(completion.choices[0], 'message') or not completion.choices[0].message:
                    log("debug", "LLM completion choice has no message:", completion)
                    log("error", "LLM error: No valid response message received")
                    return
                
                if hasattr(completion, 'usage') and completion.usage:
                    log("debug", f'LLM completion usage', completion.usage)
                
                if hasattr(completion.choices[0].message, 'content'):
                    response_text = completion.choices[0].message.content
                else:
                    log("debug", f'LLM completion without text')
                    response_text = None

                if hasattr(completion.choices[0].message, 'tool_calls'):
                    response_actions = completion.choices[0].message.tool_calls
                else:
                    response_actions = None

            if response_text and not response_actions:
                self.tts.say(response_text)
                self.event_manager.add_conversation_event('assistant', completion.choices[0].message.content)
                self.copilot.output_covas(response_text, reasons)

            if response_actions:
                self.execute_actions(response_actions, projected_states)

                if not predicted_actions and self.config["use_action_cache_var"]:
                    self.verify_action(user_input, response_actions, prompt, tool_list)
        except Exception as e:
            log("debug", "LLM error during reply:", e, traceback.format_exc())
            log("error", "LLM error: An unknown error occurred during reply")
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
                    chunks = [chunk.strip() for chunk in self.config["react_to_material"].split(",")]
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
                    return False
                else:
                    continue

        return False
    
    def register_should_reply_handler(self, handler: Callable[[Event, dict[str, Any]], bool | None]):
        self.registered_should_reply_handlers.append(handler)
