import json


class AIActions:
    actions = {}

    def __init__(self):
         pass

    def getToolsList(self):
        """return list of functions as passed to gpt"""
        return [action.get("tool") for action in self.actions.values()]

    def runAction(self, tool_call):
        """get function response and fetch matching python function, then call function using arguments provided"""
        function_name = tool_call.function.name
        function_to_call = self.actions.get(function_name).get("method")
        function_args = json.loads(tool_call.function.arguments)

        function_result = None
        try:
            function_result = function_to_call(function_args)
        except Exception as e:
            function_result = "ERROR: "+repr(e)

        return {
            "tool_call_id": tool_call.id,
            "role": "tool",
            "name": function_name,
            "content": function_result,
        }

    # register function
    def registerAction(self, name, description, parameters, method, image=False):
        self.actions[name] = {
            "method": method,
            "tool": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        }

