import json
from llama_cpp import Llama

from .localLLMUtils import create_chat_completion_handler


llm_model_names = [
    "lmstudio-community/Llama-3.2-3B-Instruct-GGUF",
    "lmstudio-community/Mistral-7B-Instruct-v0.3-GGUF",
    #"qwp4w3hyb/Mistral-Nemo-Instruct-2407-iMat-GGUF",
    "None",

    #"bartowski/Phi-3.5-mini-instruct-GGUF",
    #"phi0112358/DeepSeek-V2-Lite-Chat-Q4_0-GGUF",
    #"tiiuae/falcon-mamba-7b-instruct-Q4_K_M-GGUF",
]

model_presets = {
    "lmstudio-community/Mistral-7B-Instruct-v0.3-GGUF": {
        "filename": "Mistral-7B-Instruct-v0.3-IQ4_NL.gguf",
        "template": "{%- if messages[0][\"role\"] == \"system\" %}\n    {%- set system_message = messages[0][\"content\"] %}\n    {%- set loop_messages = messages[1:] %}\n{%- else %}\n    {%- set loop_messages = messages %}\n{%- endif %}\n{%- if not tools is defined %}\n    {%- set tools = none %}\n{%- endif %}\n{%- set user_messages = loop_messages | selectattr(\"role\", \"equalto\", \"user\") | list %}\n\n{#- This block checks for alternating user/assistant messages, skipping tool calling messages #}\n{%- set ns = namespace() %}\n{%- set ns.index = 0 %}\n{%- for message in loop_messages %}\n    {%- if not (message.role == \"tool\" or message.role == \"tool_results\" or (message.tool_calls is defined and message.tool_calls is not none)) %}\n        {%- if (message[\"role\"] == \"user\") != (ns.index % 2 == 0) %}\n            {{- raise_exception(\"After the optional system message, conversation roles must alternate user/assistant/user/assistant/...\") }}\n        {%- endif %}\n        {%- set ns.index = ns.index + 1 %}\n    {%- endif %}\n{%- endfor %}\n\n{{- bos_token }}\n{%- for message in loop_messages %}\n    {%- if message[\"role\"] == \"user\" %}\n        {%- if tools is not none and (message == user_messages[-1]) %}\n            {{- \"[AVAILABLE_TOOLS] [\" }}\n            {%- for tool in tools %}\n                {%- set tool = tool.function %}\n                {{- '{\"type\": \"function\", \"function\": {' }}\n                {%- for key, val in tool.items() if key != \"return\" %}\n                    {%- if val is string %}\n                        {{- '\"' + key + '\": \"' + val + '\"' }}\n                    {%- else %}\n                        {{- '\"' + key + '\": ' + val|tojson }}\n                    {%- endif %}\n                    {%- if not loop.last %}\n                        {{- \", \" }}\n                    {%- endif %}\n                {%- endfor %}\n                {{- \"}}\" }}\n                {%- if not loop.last %}\n                    {{- \", \" }}\n                {%- else %}\n                    {{- \"]\" }}\n                {%- endif %}\n            {%- endfor %}\n            {{- \"[/AVAILABLE_TOOLS]\" }}\n            {%- endif %}\n        {%- if loop.last and system_message is defined %}\n            {{- \"[INST] \" + system_message + \"\\n\\n\" + message[\"content\"] + \"[/INST]\" }}\n        {%- else %}\n            {{- \"[INST] \" + message[\"content\"] + \"[/INST]\" }}\n        {%- endif %}\n    {%- elif message.tool_calls is defined and message.tool_calls is not none %}\n        {{- \"[TOOL_CALLS] [\" }}\n        {%- for tool_call in message.tool_calls %}\n            {%- set out = tool_call.function|tojson %}\n            {{- out[:-1] }}\n            {%- if not tool_call.id is defined or tool_call.id|length != 9 %}\n                {{- raise_exception(\"Tool call IDs should be alphanumeric strings with length 9!\") }}\n            {%- endif %}\n            {{- ', \"id\": \"' + tool_call.id + '\"}' }}\n            {%- if not loop.last %}\n                {{- \", \" }}\n            {%- else %}\n                {{- \"]\" + eos_token }}\n            {%- endif %}\n        {%- endfor %}\n    {%- elif message[\"role\"] == \"assistant\" %}\n        {{- \" \" + message[\"content\"]|trim + eos_token}}\n    {%- elif message[\"role\"] == \"tool_results\" or message[\"role\"] == \"tool\" %}\n        {%- if message.content is defined and message.content.content is defined %}\n            {%- set content = message.content.content %}\n        {%- else %}\n            {%- set content = message.content %}\n        {%- endif %}\n        {{- '[TOOL_RESULTS] {\"content\": ' + content|string + \", \" }}\n        {%- if not message.tool_call_id is defined or message.tool_call_id|length != 9 %}\n            {{- raise_exception(\"Tool call IDs should be alphanumeric strings with length 9!\") }}\n        {%- endif %}\n        {{- '\"call_id\": \"' + message.tool_call_id + '\"}[/TOOL_RESULTS]' }}\n    {%- else %}\n        {{- raise_exception(\"Only user and assistant roles are supported, with the exception of an initial optional system message!\") }}\n    {%- endif %}\n{%- endfor %}\n",
        "tool_use_grammar": """
            root   ::= ("[TOOL_CALLS] " array "</s>") | nottoolcalls .* "</s>"
            nottoolcalls ::= [^\[] | ("\[" [^T]) | ("\[T" [^O]) | ("\[TO" [^O]) | ("\[TOO" [^L]) | ("\[TOOL" [^_] ) | ("\[TOOL_" [^C]) | ("\[TOOL_C" [^A]) | ("\[TOOL_CA" [^L]) | ("\[TOOL_CAL" [^L]) | ("\[TOOL_CALL" [^S]) | ("\[TOOL_CALLS" [^\]]) | ("\[TOOL_CALLS\]" [^ ])
        """,
        "tool_use_regex": '\\[TOOL_CALLS\\] (\\[.*\\])',
    },
    "qwp4w3hyb/Mistral-Nemo-Instruct-2407-iMat-GGUF": {
        "filename": "mistral-nemo-instruct-2407-imat-IQ4_XS.gguf",
        "template": "{%- if messages[0][\"role\"] == \"system\" %}\n    {%- set system_message = messages[0][\"content\"] %}\n    {%- set loop_messages = messages[1:] %}\n{%- else %}\n    {%- set loop_messages = messages %}\n{%- endif %}\n{%- if not tools is defined %}\n    {%- set tools = none %}\n{%- endif %}\n{%- set user_messages = loop_messages | selectattr(\"role\", \"equalto\", \"user\") | list %}\n\n{#- This block checks for alternating user/assistant messages, skipping tool calling messages #}\n{%- set ns = namespace() %}\n{%- set ns.index = 0 %}\n{%- for message in loop_messages %}\n    {%- if not (message.role == \"tool\" or message.role == \"tool_results\" or (message.tool_calls is defined and message.tool_calls is not none)) %}\n        {%- if (message[\"role\"] == \"user\") != (ns.index % 2 == 0) %}\n            {{- raise_exception(\"After the optional system message, conversation roles must alternate user/assistant/user/assistant/...\") }}\n        {%- endif %}\n        {%- set ns.index = ns.index + 1 %}\n    {%- endif %}\n{%- endfor %}\n\n{{- bos_token }}\n{%- for message in loop_messages %}\n    {%- if message[\"role\"] == \"user\" %}\n        {%- if tools is not none and (message == user_messages[-1]) %}\n            {{- \"[AVAILABLE_TOOLS] [\" }}\n            {%- for tool in tools %}\n                {%- set tool = tool.function %}\n                {{- '{\"type\": \"function\", \"function\": {' }}\n                {%- for key, val in tool.items() if key != \"return\" %}\n                    {%- if val is string %}\n                        {{- '\"' + key + '\": \"' + val + '\"' }}\n                    {%- else %}\n                        {{- '\"' + key + '\": ' + val|tojson }}\n                    {%- endif %}\n                    {%- if not loop.last %}\n                        {{- \", \" }}\n                    {%- endif %}\n                {%- endfor %}\n                {{- \"}}\" }}\n                {%- if not loop.last %}\n                    {{- \", \" }}\n                {%- else %}\n                    {{- \"]\" }}\n                {%- endif %}\n            {%- endfor %}\n            {{- \"[/AVAILABLE_TOOLS]\" }}\n            {%- endif %}\n        {%- if loop.last and system_message is defined %}\n            {{- \"[INST] \" + system_message + \"\\n\\n\" + message[\"content\"] + \"[/INST]\" }}\n        {%- else %}\n            {{- \"[INST] \" + message[\"content\"] + \"[/INST]\" }}\n        {%- endif %}\n    {%- elif message.tool_calls is defined and message.tool_calls is not none %}\n        {{- \"[TOOL_CALLS] [\" }}\n        {%- for tool_call in message.tool_calls %}\n            {%- set out = tool_call.function|tojson %}\n            {{- out[:-1] }}\n            {%- if not tool_call.id is defined or tool_call.id|length != 9 %}\n                {{- raise_exception(\"Tool call IDs should be alphanumeric strings with length 9!\") }}\n            {%- endif %}\n            {{- ', \"id\": \"' + tool_call.id + '\"}' }}\n            {%- if not loop.last %}\n                {{- \", \" }}\n            {%- else %}\n                {{- \"]\" + eos_token }}\n            {%- endif %}\n        {%- endfor %}\n    {%- elif message[\"role\"] == \"assistant\" %}\n        {{- \" \" + message[\"content\"]|trim + eos_token}}\n    {%- elif message[\"role\"] == \"tool_results\" or message[\"role\"] == \"tool\" %}\n        {%- if message.content is defined and message.content.content is defined %}\n            {%- set content = message.content.content %}\n        {%- else %}\n            {%- set content = message.content %}\n        {%- endif %}\n        {{- '[TOOL_RESULTS] {\"content\": ' + content|string + \", \" }}\n        {%- if not message.tool_call_id is defined or message.tool_call_id|length != 9 %}\n            {{- raise_exception(\"Tool call IDs should be alphanumeric strings with length 9!\") }}\n        {%- endif %}\n        {{- '\"call_id\": \"' + message.tool_call_id + '\"}[/TOOL_RESULTS]' }}\n    {%- else %}\n        {{- raise_exception(\"Only user and assistant roles are supported, with the exception of an initial optional system message!\") }}\n    {%- endif %}\n{%- endfor %}\n",
        "tool_use_grammar": """
            root   ::= ("[TOOL_CALLS] " array "</s>") | nottoolcalls .* "</s>"
            nottoolcalls ::= [^\[] | ("\[" [^T]) | ("\[T" [^O]) | ("\[TO" [^O]) | ("\[TOO" [^L]) | ("\[TOOL" [^_] ) | ("\[TOOL_" [^C]) | ("\[TOOL_C" [^A]) | ("\[TOOL_CA" [^L]) | ("\[TOOL_CAL" [^L]) | ("\[TOOL_CALL" [^S]) | ("\[TOOL_CALLS" [^\]]) | ("\[TOOL_CALLS\]" [^ ])
        """,
        "tool_use_regex": '\\[TOOL_CALLS\\] (\\[.*\\])',
    },
    "lmstudio-community/Llama-3.2-3B-Instruct-GGUF": {
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "template": "{% set loop_messages = messages %}{% for message in loop_messages %}{% set role = message['role'] %}{% if role == 'tool' %}{% set role = 'ipython' %}{% endif %}{% set text = message['content'] %}{% if loop.index0 == 0 and tools is defined %}{% set text = message['content'] + '\nHere is a list of functions in JSON format that you can invoke:\n' + tools|tojson + '\nShould you decide to return the function call, Put it in the format of [func_name({\"params_name1\":\"params_value1\", \"params_name2\"=\"params_value2\"})]' %}{% endif %}{% set content = '<|start_header_id|>' + role + '<|end_header_id|>\n\n'+ text | trim + '<|eot_id|>' %}{% if loop.index0 == 0 %}{% set content = bos_token + content %}{% endif %}{{ content }}{% endfor %}{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' }}",
        "tool_use_grammar": """
            root   ::= ("[" [a-zA-Z0-9_-]+ "(" object ")]<|eot_id|>")
        """,
        "tool_use_regex": '\\[([a-zA-Z0-9_-]+)\\((.*)\\)\\]<\\|eot_id\\|>',
        "tool_use_parser": lambda regex: [{"name": regex.groups()[0], "arguments": json.loads(regex.groups()[1])}],
    }
}


def init_llm(model_path: str):
    if model_path == "None":
        return None
    
    model_preset = model_presets.get(model_path)
    llm = Llama.from_pretrained(
        repo_id=model_path,
        filename=model_preset.get("filename"),
        n_ctx=4096,

        chat_handler=create_chat_completion_handler(
            **model_preset,
        ),
    )

    completion = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": 'You are an expert in composing functions. You are given a question and a set of possible functions. \nBased on the question, you will need to make one or more function/tool calls to achieve the purpose. \nIf none of the functions can be used, point it out. If the given question lacks the parameters required by the function,also point it out. You should only return the function call in tools call sections.\nIf you decide to invoke any of the function(s), you MUST put it in the format of [func_name1(args={"params_name1":"params_value1", "params_name2"="params_value2"})]\nYou SHOULD NOT include any other text in the response.\nHere is a list of functions in JSON format that you can invoke.[\n    {\n        "name": "get_user_info",\n        "description": "Retrieve details for a specific user by their unique identifier. Note that the provided function is in Python 3 syntax.",\n        "parameters": {\n            "type": "dict",\n            "required": [\n                "user_id"\n            ],\n            "properties": {\n                "user_id": {\n                "type": "integer",\n                "description": "The unique identifier of the user. It is used to fetch the specific user details from the database."\n            },\n            "special": {\n                "type": "string",\n                "description": "Any special information or parameters that need to be considered while fetching user details.",\n                "default": "none"\n                }\n            }\n        }\n    }\n]'},
            {"role": "user", "content": "Get details of user 9399281 please"},
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": "get_weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g., San Francisco, CA",
                        },
                    },
                    "required": ["location"],
                },
            },
        }],
        tool_choice="auto",
    )
    print (completion)

    return llm

def llm(model: Llama, prompt):

    # deduplicate messages with consecutive roles
    messages = []
    for message in prompt.get("messages"):
        if messages and messages[-1].get("role") == message.get("role"):
            messages[-1]["content"] += " " + message.get("content")
        else:
            messages.append(message)

    completion = model.create_chat_completion(
        messages=messages,
        tools=prompt.get("tools", []),
        tool_choice=prompt.get("tool_choice", None),

    )

    return completion
