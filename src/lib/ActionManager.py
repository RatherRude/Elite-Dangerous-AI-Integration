from hashlib import md5
from collections.abc import Iterator
import json
import random
from typing import Any, Callable, Literal

from openai.types.chat import ChatCompletionMessageFunctionToolCall
from pydantic import BaseModel


from .Database import KeyValueStore
from .Logger import log
import traceback

# Type alias for projected states dictionary
ProjectedStates = dict[str, BaseModel]


class ActionManager:
    LANGUAGE_ALIAS_CACHE_KEY = "language_alias_cache_keys"

    @staticmethod
    def clear_action_cache():
        """clear action cache"""
        action_cache: KeyValueStore = KeyValueStore("action_cache")
        action_cache.delete_all()
    
    def __init__(self):
        self.actions: dict[str, dict[str, Any]] = {}
        self.action_cache = KeyValueStore("action_cache")
        self.allowed_actions: dict[str, bool] = {}
        self.base_action_aliases: dict[str, set[tuple[str, str]]] = {}

    def set_allowed_actions(self, allowed_actions: dict[str, bool] | None):
        """Set enabled states by permission key. Missing keys are disabled."""
        self.allowed_actions = allowed_actions if isinstance(allowed_actions, dict) else {}

    def getToolsList(self, active_mode: str, uses_actions: bool, uses_web_actions: bool, uses_ui_actions: bool, allowed_actions: dict[str, bool] | None = None, in_station: bool = False):
        """return list of functions as passed to gpt"""

        actions = self.actions.values()
        valid_actions = []
        action_permissions = allowed_actions if isinstance(allowed_actions, dict) else {}
        for action in actions:
            is_enabled = action.get("is_enabled")
            if is_enabled is not None and not is_enabled():
                continue
            permission_key = action.get("permission")
            if permission_key and action_permissions.get(permission_key) is not True:
                continue
            if uses_actions:
                # enable correct actions for game mode
                action_type = action.get("type")
                if action_type == active_mode or (
                    isinstance(action_type, list) and active_mode in action_type
                ):
                    valid_actions.append(action.get("tool"))
                # enable correct actions for extended game mode
                elif active_mode in ('mainship', 'fighter', 'nomad'):
                    if action.get("type") == 'ship':
                        valid_actions.append(action.get("tool"))
                # enable actions that require the commander to be docked
                if active_mode == 'mainship' and in_station and action.get("type") == 'in_station':
                    valid_actions.append(action.get("tool"))
                # enable vision capabilities
                if action.get("type") == 'global':
                    valid_actions.append(action.get("tool"))
            if uses_web_actions:
                # enable web tools
                if action.get("type") == 'web':
                    valid_actions.append(action.get("tool"))

            if uses_ui_actions:
                if action.get("type") == 'ui':
                    valid_actions.append(action.get("tool"))

        return valid_actions
    
    def getActionDesc(self, tool_call: ChatCompletionMessageFunctionToolCall, projected_states: ProjectedStates):
        """ summarize functions input as text """
        if tool_call.function.name in self.actions:
            action_descriptor = self.actions.get(tool_call.function.name)
            function_args = json.loads(tool_call.function.arguments if tool_call.function.arguments else "null")
            input_template = action_descriptor.get("input_template")
            if input_template:
                input_desc = input_template(function_args, projected_states)
                # filter all duplicate whitespaces
                input_desc = ' '.join(input_desc.split())
                return input_desc
        return None
    

    def runAction(
        self,
        tool_call: ChatCompletionMessageFunctionToolCall,
        projected_states: ProjectedStates,
        processing_callback: Callable[[str, str, object], None] | None = None,
    ):
        """get function response and fetch matching python function, then call function using arguments provided"""
        function_result = None

        function_name = tool_call.function.name
        function_descriptor = self.actions.get(function_name)
        if function_descriptor and (
            function_descriptor.get("is_enabled") is None or function_descriptor["is_enabled"]()
        ):
            function_to_call = function_descriptor.get("method")
            function_args = json.loads(tool_call.function.arguments if tool_call.function.arguments else "null")

            try:
                function_result = function_to_call(function_args, projected_states)
                if isinstance(function_result, Iterator):
                    final_result: Any = None
                    while True:
                        try:
                            processing_result = next(function_result)
                        except StopIteration as stop:
                            final_result = stop.value
                            break
                        if processing_callback:
                            processing_callback(tool_call.id, function_name, processing_result)
                    function_result = final_result
            except Exception as e:
                log("debug", "An error occurred during function:", e, traceback.format_exc())
                function_result = "ERROR: " + repr(e)
        else:
            function_result = f"ERROR: Function {function_name} does not exist or is disabled!"

        return {
            "tool_call_id": tool_call.id,
            "role": "tool",
            "name": function_name,
            "content": function_result,
        }

    # register function
    def registerAction(
        self, name, description, parameters, 
        method: Callable[[dict, dict], object], 
        action_type="ship", 
        permission: str | None = None,
        input_template: Callable[[dict, dict], str] | None = None, 
        cache_prefill: dict[str, dict] | None = None,
        is_enabled: Callable[[], bool] | None = None,
    ):
        """
            register action with name, description, parameters and method
            input_template is a function that takes the function arguments and projected states and returns a string
            cache_prefill is a dictionary of user input and arguments to prefill the cache with
            is_enabled optionally checks live availability before listing or executing an action
        """
        if permission and self.allowed_actions.get(permission) is not True:
            log("debug", f"Action '{name}' skipped registration due to missing permission '{permission}'")
            return

        self.actions[name] = {
            "method": method,
            "type": action_type,
            "permission": permission,
            "is_enabled": is_enabled,
            "input_template": input_template,
            "tool": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        }
        if cache_prefill is not None:
            for user_input, arguments in cache_prefill.items():
                clean_input = self.clean_user_input(user_input)
                target = (name, json.dumps(arguments, sort_keys=True))
                self.base_action_aliases.setdefault(clean_input, set()).add(target)
                #log('debug', 'Cache: prefilling', name, user_input, arguments)
                self.prefill_action_in_cache(user_input, ChatCompletionMessageFunctionToolCall(
                    type="function",
                    id=str(random.randint(100000, 999999)),
                    function={  # pyright: ignore[reportArgumentType]
                        "name": name,
                        "description": description,
                        "arguments": json.dumps(arguments)
                    }
                ), self.actions[name].get("tool"))

    def clean_user_input(self, user_input: str) -> str:
        """
            clean user input, remove whitespaces, convert to lowercase, remove all symbols
        """
        user_input = user_input.lower().strip()
        user_input = ''.join(e for e in user_input if e.isalnum())
        return user_input

    def hash_action_input(self, user_input: str, tool: dict) -> str:
        """
            hash user input
        """
        user_input = self.clean_user_input(user_input)
        return md5(json.dumps([user_input, tool]).encode()).hexdigest()

    def predict_action(self, user_input: str, tool_list) -> list[ChatCompletionMessageFunctionToolCall] | None:
        """
            predict action based on user input and available tools
        """
        # get the hash for user input with each tool
        input_hashes = [self.hash_action_input(user_input, tool) for tool in tool_list]
        # check if any of the input hashes match the predicted actions
        for input_hash in input_hashes:
            prediction = self.action_cache.get(input_hash)
            if prediction is not None and prediction.get("status") == "confirmed":
                # if prediction is confirmed, return the tool call
                new_id = str(random.randint(100000, 999999))
                tool_call = ChatCompletionMessageFunctionToolCall(
                    type="function",
                    id=new_id,
                    function=prediction.get("function")
                )
                log("debug", f"Cache: Action prediction found in cache with hash {input_hash}, returning tool call {new_id}")
                return [tool_call]
                
        return None

    def suggest_action_for_cache(self, user_input: str, action: ChatCompletionMessageFunctionToolCall, tool_list):
        """
            suggest action for cache
        """
        tool = None
        for t in tool_list:
            if t.get("function").get("name") == action.function.name:
                tool = t
                break
        
        if tool is None:
            log("debug", "Cache: No tool found for action suggestion")
            return
        
        # check if action is already in cache
        input_hash = self.hash_action_input(user_input, tool)
        if self.action_cache.get(input_hash) is not None:
            #log("debug", "Cache: Action already in cache")
            return
        
        # add action to cache
        self.action_cache.set(input_hash, {
            "status": "pending",
            "input": user_input,
            "function": {
                "name": action.function.name,
                "arguments": action.function.arguments
            }
        })
        log("info", f"Cache: Action {action.function.name} suggested for cache with hash {input_hash}")
    
    def confirm_action_in_cache(self, user_input: str, action: ChatCompletionMessageFunctionToolCall, tool_list):
        """
            confirm action in cache
        """
        tool = None
        for t in tool_list:
            if t.get("function").get("name") == action.function.name:
                tool = t
                break
        
        if tool is None:
            log("debug", "Cache: No tool found for action confirmation")
            return
        
        # check if action is already in cache
        input_hash = self.hash_action_input(user_input, tool)
        suggested_action = self.action_cache.get(input_hash)
        if suggested_action is None:
            log("debug", "Cache: Action not in cache, cannot confirm")
            return

        if suggested_action.get("function") != action.function.model_dump():
            log("debug", "Cache: Suggested action function does not match")
            self.action_cache.delete(input_hash)
            log("debug", "Cache: Deleted action from cache due to mismatch")
            return

        # update action in cache
        self.action_cache.set(input_hash, {
            "status": "confirmed",
            "input": user_input,
            "function": {
                "name": action.function.name,
                "arguments": action.function.arguments
            }
        })
        log("info", f"Cache: Action {action.function.name} confirmed in cache with hash {input_hash}")

    def prefill_action_in_cache(self, user_input: str, action: ChatCompletionMessageFunctionToolCall, tool):
        """
            prefill action cache with user input and action
        """
        input_hash = self.hash_action_input(user_input, tool)
        if self.action_cache.get(input_hash) is not None:
            #log("debug", "Cache: Action already in cache, skipping prefill")
            return
        
        # add action to cache
        self.action_cache.set(input_hash, {
            "status": "confirmed",
            "input": user_input,
            "function": {
                "name": action.function.name,
                "arguments": action.function.arguments
            }
        })
        log("info", f"Cache: Action {action.function.name} prefilled in cache with hash {input_hash}")

    def apply_language_aliases(
        self,
        language_packs: dict[str, dict[str, Any]],
        selected_languages: list[str],
    ) -> None:
        aliases: list[tuple[str, str, dict[str, Any], dict]] = []
        seen_phrases: dict[str, tuple[str, str]] = {}

        for language in selected_languages:
            pack = language_packs.get(language)
            if pack is None:
                raise ValueError(f"Unknown action language pack: {language}")
            pack_aliases = pack.get("aliases")
            if not isinstance(pack_aliases, list):
                raise ValueError(f"Invalid aliases in action language pack: {language}")

            for alias in pack_aliases:
                phrase = alias["phrase"]
                action_name = alias["action"]
                arguments = alias["arguments"]
                clean_phrase = self.clean_user_input(phrase)
                if not clean_phrase:
                    raise ValueError(f"Invalid empty action language alias: {phrase}")
                target = (action_name, json.dumps(arguments, sort_keys=True))
                base_targets = self.base_action_aliases.get(clean_phrase, set())
                if base_targets and target not in base_targets:
                    raise ValueError(f"Language alias conflicts with an English command: {phrase}")
                existing_target = seen_phrases.get(clean_phrase)
                if existing_target is not None and existing_target != target:
                    raise ValueError(f"Conflicting action language aliases for: {phrase}")
                seen_phrases[clean_phrase] = target

                if target in base_targets:
                    continue

                registered_action = self.actions.get(action_name)
                if registered_action is None:
                    log("debug", f"Skipping alias '{phrase}' for unavailable action '{action_name}'")
                    continue
                aliases.append((phrase, action_name, arguments, registered_action["tool"]))

        previous_keys = self.action_cache.get(self.LANGUAGE_ALIAS_CACHE_KEY, [])
        if isinstance(previous_keys, list):
            for key in previous_keys:
                if isinstance(key, str):
                    self.action_cache.delete(key)

        cache_keys: list[str] = []
        for phrase, action_name, arguments, tool in aliases:
            input_hash = self.hash_action_input(phrase, tool)
            action_tool = self.actions[action_name]["tool"]["function"]
            self.action_cache.set(input_hash, {
                "status": "confirmed",
                "input": phrase,
                "function": {
                    "name": action_name,
                    "description": action_tool.get("description"),
                    "arguments": json.dumps(arguments),
                },
            })
            cache_keys.append(input_hash)

        self.action_cache.set(self.LANGUAGE_ALIAS_CACHE_KEY, cache_keys)
        log("info", f"Loaded aliases for action languages: {', '.join(selected_languages) or 'English only'}")

    def has_action_in_cache(self, user_input: str, action: ChatCompletionMessageFunctionToolCall, tool_list) -> Literal["suggested", "confirmed", False]:
        """
            check if there is a suggested action in cache
        """
        tool = None
        for t in tool_list:
            if t.get("function").get("name") == action.function.name:
                tool = t
                break

        if tool is None:
            log("debug", "Cache: No tool found for action suggestion")
            return False

        input_hash = self.hash_action_input(user_input, tool)
        if self.action_cache.get(input_hash) is not None:
            return self.action_cache.get(input_hash).get("status")
        log("debug", "Cache: No suggested action found in cache")
        return False
