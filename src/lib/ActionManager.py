from hashlib import md5
import json
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
import random
from typing import Any, Callable

from openai.types.chat import ChatCompletionMessageToolCall

from lib.Database import KeyValueStore

from .Logger import log
import traceback


class ActionManager:
    @staticmethod
    def clear_action_cache():
        """clear action cache"""
        action_cache: KeyValueStore = KeyValueStore("action_cache")
        action_cache.delete_all()
    
    actions = {}

    def __init__(self):
        self.action_cache = KeyValueStore("action_cache")

    def getToolsList(self, active_mode: str, uses_actions:bool, uses_web_actions: bool):
        """return list of functions as passed to gpt"""

        actions = self.actions.values()
        valid_actions = []
        for action in actions:
            if uses_actions:
                # enable correct actions for game mode
                if action.get("type") == active_mode:
                    valid_actions.append(action.get("tool"))
                # enable correct actions for extended game mode
                elif active_mode == 'mainship' or active_mode == 'fighter':
                    if action.get("type") == 'ship':
                        valid_actions.append(action.get("tool"))
                # enable vision capabilities
                if action.get("type") == 'global':
                    valid_actions.append(action.get("tool"))
            if uses_web_actions:
                # enable web tools
                if action.get("type") == 'web':
                    valid_actions.append(action.get("tool"))

        return valid_actions
    
    def getActionDesc(self, tool_call: ChatCompletionMessageToolCall, projected_states: dict[str, dict]):
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
    

    def runAction(self, tool_call: ChatCompletionMessageToolCall, projected_states: dict[str, dict]):
        """get function response and fetch matching python function, then call function using arguments provided"""
        function_result = None

        function_name = tool_call.function.name
        function_descriptor = self.actions.get(function_name)
        if function_descriptor:
            function_to_call = function_descriptor.get("method")
            function_args = json.loads(tool_call.function.arguments if tool_call.function.arguments else "null")

            try:
                function_result = function_to_call(function_args, projected_states)
            except Exception as e:
                log("debug", "An error occurred during function:", e, traceback.format_exc())
                function_result = "ERROR: " + repr(e)
        else:
            function_result = f"ERROR: Function {function_name} does not exist!"

        return {
            "tool_call_id": tool_call.id,
            "role": "tool",
            "name": function_name,
            "content": function_result,
        }

    # register function
    def registerAction(self, name, description, parameters, method: Callable[[dict, dict], str], action_type="ship", input_template: Callable[[dict, dict], str]|None=None):
        self.actions[name] = {
            "method": method,
            "type": action_type,
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
        
    
    def clean_user_input(self, user_input: list[str]) -> str:
        """
            clean user input, remove whitespaces, convert to lowercase, remove all symbols
        """
        user_input = [input.lower().strip() for input in user_input]
        user_input = [''.join(e for e in input if e.isalnum()) for input in user_input]
        return user_input

    def hash_action_input(self, user_input: list[str], tool_list: list) -> str:
        """
            hash user input
        """
        user_input = self.clean_user_input(user_input)
        return md5(json.dumps([user_input, tool_list]).encode()).hexdigest()

    def predict_action(self, user_input: list[str], tool_list) -> list[ChatCompletionMessageToolCall] | None:
        """
            predict action based on user input
            check if user input is in database
            if not, return None
            if yes and is draft, return None
            if yes and is confirmed, return actual
        """
        #log('info', 'Predicting action for:', user_input)
        input_hash = self.hash_action_input(user_input, tool_list)
        predicted_actions = self.action_cache.get(input_hash)
        if predicted_actions and predicted_actions.get("status") == "confirmed":
            actions = predicted_actions.get("actions")
            id = "call_"+random.randbytes(8).hex()
            log('debug', 'Predicted action:', user_input, actions)
            return [ChatCompletionMessageToolCall(id=id, function=action, type="function") for action in actions]
        return None
    
    def has_prediction_draft(self, user_input: list[str], tool_list: list) -> bool:
        """
            get draft prediction
        """
        input_hash = self.hash_action_input(user_input, tool_list)
        predicted_actions = self.action_cache.get(input_hash)
        return True if predicted_actions and predicted_actions.get("status") == "draft" else False
    
    def save_prediction_draft(self, user_input: list[str], contextual_actions: list[ChatCompletionMessageToolCall], tool_list):
        """
            save draft prediction
        """
        input_hash = self.hash_action_input(user_input, tool_list)
        contextual_actions: list[ChatCompletionMessageToolCall] = [action.function.model_dump() for action in contextual_actions]

        existing = self.action_cache.get(input_hash)
        if existing and existing.get("status") == "confirmed":
            log("debug", "Prediction already confirmed:", user_input, existing)
            return False
        if existing and existing.get("status") == "invalid":
            log("debug", "Prediction already invalid:", user_input, existing)
            return False
        
        log("debug", "Saving prediction draft:", user_input, contextual_actions)
        self.action_cache.init(input_hash, "0", {
            "status": "draft",
            "actions": contextual_actions,
            "user_input": user_input,
        })
        return True

    def save_prediction_verification(self, user_input: list[str], contextual_actions: list[ChatCompletionMessageToolCall], isolated_actions: list[ChatCompletionMessageToolCall], tool_list):
        """
            validate prediction
            if first seen, add as draft
            if already seen and same as actual, confirm
            otherwise remove
        """
        input_hash = self.hash_action_input(user_input, tool_list)
        contextual_actions: list[ChatCompletionMessageToolCall] = [action.function.model_dump() for action in contextual_actions] if contextual_actions else []
        isolated_actions = [action.function.model_dump() for action in isolated_actions] if isolated_actions else []
        
        if contextual_actions != isolated_actions:
            #log('debug', 'Invalidating prediction for:', user_input, contextual_actions, isolated_actions)
            self.action_cache.set(input_hash, {
                "status": "invalid",
                "actions": contextual_actions,
                "user_input": user_input,
            })
            return False
        
        #log('info', 'Validating prediction for:', user_input, actual_actions)
        cached = self.action_cache.get(input_hash)
        if not cached:
            #log('debug', 'Adding prediction as draft:', user_input, contextual_actions)
            self.action_cache.init(input_hash, "0", {
                "status": "draft",
                "actions": contextual_actions,
                "user_input": user_input,
            })
            return False
        
        if cached.get("actions") != contextual_actions:
            #log('debug', 'Invalidating prediction for:', user_input, cached.get("actions"), contextual_actions)
            self.action_cache.set(input_hash, {
                "status": "invalid",
                "actions": contextual_actions,
                "user_input": user_input,
            })
            return False
        
        #log('info', 'Prediction already seen:', user_input, cached.get("actions"))
        if cached.get("status") == "confirmed":
            #log('debug', 'Prediction already confirmed:', user_input, cached)
            return False
        
        if cached.get("status") == "draft":
            log('debug', 'Prediction confirmed:', user_input, cached)
            cached["status"] = "confirmed"
            self.action_cache.set(input_hash, cached)
            return True
        
        return False