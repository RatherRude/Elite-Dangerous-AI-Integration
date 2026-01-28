import json
import traceback
from pathlib import Path
from datetime import datetime
from openai.types.chat import ChatCompletion, ChatCompletionMessageToolCall
from time import time

from pydantic import BaseModel
from .Models import LLMModel, EmbeddingModel, LLMError
from .Logger import log, observe, show_chat_message
from .Config import Config
from .Database import QuestDatabase, QuestState
from .Event import ConversationEvent, Event, GameEvent, StatusEvent, ToolEvent, ExternalEvent, ProjectedEvent, MemoryEvent
from .EventManager import EventManager
from .ActionManager import ActionManager
from .PromptGenerator import PromptGenerator
from .TTS import TTS
from typing import Any,  Callable, final
import yaml
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
        self.quest_db = QuestDatabase()
        self.quest_catalog: dict[str, dict[str, Any]] = {}
        self.quests_loaded = False
        self.quest_version = "0"

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

                if self.config.get("qol_autoscan"):
                    fire_args = {
                        "weaponType": "discovery_scanner",
                        "action": "fire",
                        "discoveryPrimary": self.config.get("discovery_primary_var", True),
                        "discoveryFiregroup": self.config.get("discovery_firegroup_var", 1),
                    }
                    fire_weapons(fire_args, projected_states)
            if isinstance(event, ProjectedEvent) and event.content.get('event') == 'CarrierJumpCooldownComplete':
                log('debug', 'here could be a carrer jump')

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

        if (isinstance(event, GameEvent) and event.content.get('event') == 'LoadGame'):
            self._load_quests()

        try:
            self._process_active_quests(event, projected_states)
        except Exception as e:
            log('error', 'Quest processing failed', e, traceback.format_exc())

    def _get_quests_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "data" / "quests.yaml"

    def _load_quests(self) -> None:
        try:
            quests_path = self._get_quests_path()
            if not quests_path.exists():
                log('warn', f"Quest file not found: {quests_path}")
                self.quest_catalog = {}
                self.quests_loaded = False
                return
            with quests_path.open('r', encoding='utf-8') as handle:
                data = yaml.safe_load(handle) or {}
            self.quest_version = str(data.get('version', '0'))
            raw_quests = data.get('quests', [])
            if not isinstance(raw_quests, list):
                log('warn', 'Quest file format invalid: quests is not a list')
                self.quest_catalog = {}
                self.quests_loaded = False
                return
            quests: list[dict[str, Any]] = []
            for quest in raw_quests:
                if not isinstance(quest, dict):
                    continue
                quest_id = quest.get('id')
                if isinstance(quest_id, str):
                    quests.append(quest)
            self.quest_catalog = {quest["id"]: quest for quest in quests}
            self._sync_quests_to_db()
            self.quests_loaded = True
            log('info', f"Loaded {len(self.quest_catalog)} quests from {quests_path}")
        except Exception as e:
            log('error', 'Failed to load quests', e, traceback.format_exc())
            self.quest_catalog = {}
            self.quests_loaded = False

    def _sync_quests_to_db(self) -> None:
        for quest_id, quest in self.quest_catalog.items():
            existing = self.quest_db.get(quest_id)
            stages = quest.get('stages', [])
            if not stages:
                log('warn', f"Quest '{quest_id}' has no stages, skipping")
                continue
            first_stage = stages[0]
            stage_id = first_stage.get('id')
            if not stage_id:
                log('warn', f"Quest '{quest_id}' first stage missing id, skipping")
                continue
            active = bool(quest.get('active', False))
            if existing is None:
                self.quest_db.set(quest_id, stage_id, active, self.quest_version)
                log('info', f"Quest '{quest_id}' initialized at stage '{stage_id}', active={active}")
                continue
            existing_version = existing.get('version')
            if self._is_newer_version(self.quest_version, existing_version):
                self.quest_db.set(quest_id, stage_id, active, self.quest_version)
                log('info', f"Quest '{quest_id}' updated to version {self.quest_version}")

    def _process_active_quests(self, event: Event, projected_states: ProjectedStates) -> None:
        if not self.quests_loaded or not self.quest_catalog:
            return
        quest_states = self.quest_db.get_all()
        for state in quest_states:
            if not state["active"]:
                continue
            quest_id = state["quest_id"]
            stage_id = state["stage_id"]
            quest_def = self.quest_catalog.get(quest_id)
            if not quest_def:
                log('warn', f"Quest '{quest_id}' missing from catalog")
                continue
            stage_def = self._get_stage_def(quest_def, stage_id)
            if not stage_def:
                log('warn', f"Quest '{quest_id}' stage '{stage_id}' missing from catalog")
                continue
            conditions = stage_def.get('conditions', [])
            if conditions and not self._conditions_met(conditions, event, projected_states):
                continue
            plan = stage_def.get('plan', [])
            if not plan:
                continue
            if not conditions and not any(isinstance(step, dict) and step.get('conditions') for step in plan):
                continue
            self._trigger_quest_stage_plan(quest_def, stage_def, state, event, projected_states)

    def _get_stage_def(self, quest_def: dict[str, Any], stage_id: str | None) -> dict[str, Any] | None:
        if not stage_id:
            return None
        for stage in quest_def.get('stages', []):
            if stage.get('id') == stage_id:
                return stage
        return None

    def _conditions_met(self, conditions: list[dict[str, Any]], event: Event, projected_states: ProjectedStates) -> bool:
        for condition in conditions:
            if not isinstance(condition, dict):
                return False
            source = condition.get('source')
            if not isinstance(source, str):
                return False
            path = condition.get('path', '')
            if not isinstance(path, str):
                return False
            operator = condition.get('operator', 'equals')
            if not isinstance(operator, str):
                operator = 'equals'
            expected = condition.get('value')
            actual = self._resolve_condition_value(source, path, event, projected_states)
            if not self._compare_condition(actual, expected, operator):
                log('debug', f"Quest condition failed: source={source} path={path} operator={operator} expected={expected} actual={actual}")
                return False
        return True

    def _resolve_condition_value(self, source: str, path: str, event: Event, projected_states: ProjectedStates) -> Any:
        if source == 'projection':
            return self._resolve_projection_value(path, projected_states)
        if source == 'event':
            return self._resolve_event_value(path, event)
        return None

    def _resolve_projection_value(self, path: str, projected_states: ProjectedStates) -> Any:
        if not path:
            return None
        parts = path.split('.')
        root = parts[0]
        remainder = '.'.join(parts[1:])
        projection_data = get_state_dict(projected_states, root, default={})
        return self._get_nested_value(projection_data, remainder)

    def _resolve_event_value(self, path: str, event: Event) -> Any:
        if not path:
            return None
        event_data: dict[str, Any] | None = None
        if isinstance(event, GameEvent):
            event_data = dict(event.content)
        elif isinstance(event, StatusEvent):
            event_data = event.status
        if event_data is None:
            return None
        normalized = path
        if normalized.startswith('event.'):
            normalized = normalized[len('event.'):]
        return self._get_nested_value(event_data, normalized)

    def _get_nested_value(self, data: Any, path: str) -> Any:
        if path == '':
            return data
        current = data
        for part in path.split('.'):
            if isinstance(current, dict):
                if part not in current:
                    return None
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def _compare_condition(self, actual: Any, expected: Any, operator: str) -> bool:
        if operator in ('equals', '=='):
            return self._values_equal(actual, expected)
        log('debug', f"Quest condition operator not supported: {operator}")
        return False

    def _values_equal(self, actual: Any, expected: Any) -> bool:
        if actual is None:
            return False
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return float(actual) == float(expected)
        if isinstance(actual, str) and isinstance(expected, (int, float)):
            try:
                return float(actual) == float(expected)
            except ValueError:
                return False
        if isinstance(actual, (int, float)) and isinstance(expected, str):
            try:
                return float(actual) == float(expected)
            except ValueError:
                return False
        return actual == expected

    def _trigger_quest_stage_plan(self, quest_def: dict[str, Any], stage_def: dict[str, Any], state: QuestState, event: Event, projected_states: ProjectedStates) -> None:
        quest_id = quest_def.get('id', 'unknown')
        stage_id = stage_def.get('id', 'unknown')
        plan = stage_def.get('plan', [])
        log('debug', f"Quest '{quest_id}' stage '{stage_id}' conditions met. Plan: {plan}")
        for step in plan:
            if not isinstance(step, dict):
                continue
            step_conditions = step.get('conditions')
            if step_conditions is not None:
                if not isinstance(step_conditions, list):
                    continue
                if not self._conditions_met(step_conditions, event, projected_states):
                    continue
            action = step.get('action')
            if action == 'log':
                message = step.get('message', '')
                if message:
                    log('debug', message)
                continue
            if action == 'advance_stage':
                target_stage_id = step.get('target_stage_id') or step.get('stage_id')
                self._advance_quest_stage(quest_def, target_stage_id, state["quest_id"])
                continue
            if action == 'set_active':
                target_quest_id = step.get('quest_id')
                if not isinstance(target_quest_id, str) or not target_quest_id:
                    continue
                active_value = step.get('active')
                if active_value is None:
                    active_value = True
                if not isinstance(active_value, bool):
                    continue
                existing = self.quest_db.get(target_quest_id)
                if existing is None:
                    target_def = self.quest_catalog.get(target_quest_id)
                    stages = target_def.get('stages', []) if isinstance(target_def, dict) else []
                    first_stage_id = stages[0].get('id') if stages else None
                    if isinstance(first_stage_id, str):
                        self.quest_db.set(target_quest_id, first_stage_id, active_value, self.quest_version)
                        log('info', f"Quest '{target_quest_id}' set active={active_value} (initialized)")
                else:
                    self.quest_db.set_active(target_quest_id, active_value)
                    log('info', f"Quest '{target_quest_id}' set active={active_value}")
                target_def = self.quest_catalog.get(target_quest_id, {})
                quest_title = target_def.get('title') if isinstance(target_def, dict) else None
                self.event_manager.add_quest_event({
                    "event": "QuestEvent",
                    "action": "set_active",
                    "quest_id": target_quest_id,
                    "quest_title": quest_title,
                    "active": active_value,
                })
                continue

    def _advance_quest_stage(self, quest_def: dict[str, Any], target_stage_id: str | None, quest_id: str | None) -> None:
        if not quest_id or not target_stage_id:
            return
        stages = quest_def.get('stages', [])
        stage_ids = [stage.get('id') for stage in stages]
        if target_stage_id not in stage_ids:
            return
        stage_def = self._get_stage_def(quest_def, target_stage_id)
        stage_description = stage_def.get('description') if isinstance(stage_def, dict) else None
        stage_instructions = stage_def.get('instructions') if isinstance(stage_def, dict) else None
        stage_name = None
        if isinstance(stage_def, dict):
            stage_name = stage_def.get('title') or stage_def.get('name') or stage_def.get('id')
        version_state = self.quest_db.get(quest_id)
        stored_version = (version_state.get('version') if version_state else None) or self.quest_version
        self.quest_db.set(quest_id, target_stage_id, True, stored_version)
        log('info', f"Quest '{quest_id}' advanced to stage '{target_stage_id}'")
        self.event_manager.add_quest_event({
            "event": "QuestEvent",
            "action": "advance_stage",
            "quest_id": quest_id,
            "quest_title": quest_def.get('title'),
            "stage_id": target_stage_id,
            "stage_name": stage_name or target_stage_id,
            "stage_description": stage_description,
            "stage_instructions": stage_instructions,
        })

    def _is_newer_version(self, candidate: str, current: str | None) -> bool:
        if current is None:
            return True
        candidate_parts = self._parse_version(candidate)
        current_parts = self._parse_version(current)
        return candidate_parts > current_parts

    def _parse_version(self, value: str) -> tuple[int, ...]:
        parts: list[int] = []
        for item in value.split('.'):
            try:
                parts.append(int(item))
            except ValueError:
                parts.append(0)
        return tuple(parts)
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
