import json
from typing import Any, Callable

from openai.types.chat import ChatCompletionMessageToolCall

from .Logger import log
import traceback


class ActionManager:
    actions = {}

    def __init__(self):
        pass

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
