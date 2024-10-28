import json
from typing import Optional
from llama_cpp import Llama

from .localLLMGrammarUtils import gbnf_literal, gbnf_not, gbnf_or, gbnf_sanitize
from .localLLMUtils import create_chat_completion_handler, LlamaDiskCache 

llm_model_names = [
    "lucaelin/llama-3.2-3b-instruct-fc-gguf",
    "lmstudio-community/Llama-3.2-3B-Instruct-GGUF",
    "lmstudio-community/Mistral-7B-Instruct-v0.3-GGUF",
    "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
    "lmstudio-community/Mistral-Nemo-Instruct-2407-GGUF",
    "allenai/OLMoE-1B-7B-0924-Instruct-GGUF",
    "Salesforce/xLAM-1b-fc-r-gguf",
    "bartowski/functionary-small-v3.1-GGUF",
    "None",

    #"NousResearch/Llama-3.2-1B",
    #"bartowski/Phi-3.5-mini-instruct-GGUF",
    #"phi0112358/DeepSeek-V2-Lite-Chat-Q4_0-GGUF",
    #"tiiuae/falcon-mamba-7b-instruct-Q4_K_M-GGUF",
]


model_presets = {
    "lucaelin/llama-3.2-3b-instruct-fc-gguf": {
        "filename": "unsloth.Q8_0.gguf",
        "template": "{% set loop_messages = messages %}{% for message in loop_messages %}{% set role = message['role'] %}{% if 'tool_calls' in message %}{% set text = '<tool_call>' + message['tool_calls'][0]['function']|tojson + '</tool_call>' %}{% endif %}{% if 'content' in message %}{% set text = message['content'] %}{% endif %}{% if loop.index0 == 0 and tools is defined %}{% set text = message['content'] + '\n\nYou are able to call the following tools, when needed, call them using the <tool_call> xml-tag, followed by name and arguments as json.\n<tools>\n' + tools|tojson + '\n</tools>' %}{% endif %}{% set content = '<|start_header_id|>' + role + '<|end_header_id|>\n\n'+ text | trim + '<|eot_id|>' %}{% if loop.index0 == 0 %}{% set content = bos_token + content %}{% endif %}{{ content }}{% endfor %}{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' }}",
        "tool_use_grammar": lambda tools: f"""
            root   ::= ("<tool_call>" {gbnf_or([gbnf_sanitize(tool["function"]["name"]) for tool in tools])} "</tool_call>") | (.*)
            nottoolcalls ::= {gbnf_not("<tool_call>")}
        """,
        "tool_use_regex": '^<tool_call>(.*)</tool_call>',
        "tool_use_parser": lambda regex: [json.loads(regex.group(1))]
    },
    "lmstudio-community/Llama-3.2-3B-Instruct-GGUF": {
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "template": "{% set loop_messages = messages %}{% for message in loop_messages %}{% set role = message['role'] %}{% if role == 'tool' %}{% set role = 'ipython' %}{% endif %}{% set text = message['content'] %}{% if loop.index0 == 0 and tools is defined %}{% set text = message['content'] + '\nHere is a list of functions in JSON format that you can invoke:\n' + tools|tojson + '\nShould you decide to return the function call, must put it at the beginning of your response, without any additional text and in the following format: [func_name({\"params_name1\":\"params_value1\", \"params_name2\"=\"params_value2\"})]. You may also choose not to call any function, if no function matches the users request.' %}{% endif %}{% set content = '<|start_header_id|>' + role + '<|end_header_id|>\n\n'+ text | trim + '<|eot_id|>' %}{% if loop.index0 == 0 %}{% set content = bos_token + content %}{% endif %}{{ content }}{% endfor %}{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' }}",
        "tool_use_grammar": lambda tools: f"""
            root   ::= ("[" {gbnf_or([gbnf_literal(tool["function"]["name"])+'"("'+gbnf_sanitize(tool["function"]["name"])+'-arguments'+'")"' for tool in tools])} "]" )| ( [^\\[] .* )
        """,
        "tool_use_regex": '^\\[([a-zA-Z0-9_-]+)\\((.*)\\)\\]$',
        "tool_use_parser": lambda regex: [{"name": regex.groups()[0], "arguments": json.loads(regex.groups()[1])}],
    },
    "lmstudio-community/Mistral-7B-Instruct-v0.3-GGUF": {
        "filename": "Mistral-7B-Instruct-v0.3-IQ4_NL.gguf",
        "template": "{%- if messages[0][\"role\"] == \"system\" %}\n    {%- set system_message = messages[0][\"content\"] %}\n    {%- set loop_messages = messages[1:] %}\n{%- else %}\n    {%- set loop_messages = messages %}\n{%- endif %}\n{%- if not tools is defined %}\n    {%- set tools = none %}\n{%- endif %}\n{%- set user_messages = loop_messages | selectattr(\"role\", \"equalto\", \"user\") | list %}\n\n{#- This block checks for alternating user/assistant messages, skipping tool calling messages #}\n{%- set ns = namespace() %}\n{%- set ns.index = 0 %}\n{%- for message in loop_messages %}\n    {%- if not (message.role == \"tool\" or message.role == \"tool_results\" or (message.tool_calls is defined and message.tool_calls is not none)) %}\n        {%- if (message[\"role\"] == \"user\") != (ns.index % 2 == 0) %}\n            {{- raise_exception(\"After the optional system message, conversation roles must alternate user/assistant/user/assistant/...\") }}\n        {%- endif %}\n        {%- set ns.index = ns.index + 1 %}\n    {%- endif %}\n{%- endfor %}\n\n{{- bos_token }}\n{%- for message in loop_messages %}\n    {%- if message[\"role\"] == \"user\" %}\n        {%- if tools is not none and (message == user_messages[-1]) %}\n            {{- \"[AVAILABLE_TOOLS] [\" }}\n            {%- for tool in tools %}\n                {%- set tool = tool.function %}\n                {{- '{\"type\": \"function\", \"function\": {' }}\n                {%- for key, val in tool.items() if key != \"return\" %}\n                    {%- if val is string %}\n                        {{- '\"' + key + '\": \"' + val + '\"' }}\n                    {%- else %}\n                        {{- '\"' + key + '\": ' + val|tojson }}\n                    {%- endif %}\n                    {%- if not loop.last %}\n                        {{- \", \" }}\n                    {%- endif %}\n                {%- endfor %}\n                {{- \"}}\" }}\n                {%- if not loop.last %}\n                    {{- \", \" }}\n                {%- else %}\n                    {{- \"]\" }}\n                {%- endif %}\n            {%- endfor %}\n            {{- \"[/AVAILABLE_TOOLS]\" }}\n            {%- endif %}\n        {%- if loop.last and system_message is defined %}\n            {{- \"[INST] \" + system_message + \"\\n\\n\" + message[\"content\"] + \"[/INST]\" }}\n        {%- else %}\n            {{- \"[INST] \" + message[\"content\"] + \"[/INST]\" }}\n        {%- endif %}\n    {%- elif message.tool_calls is defined and message.tool_calls is not none %}\n        {{- \"[TOOL_CALLS] [\" }}\n        {%- for tool_call in message.tool_calls %}\n            {%- set out = tool_call.function|tojson %}\n            {{- out[:-1] }}\n            {%- if not tool_call.id is defined or tool_call.id|length != 9 %}\n                {{- raise_exception(\"Tool call IDs should be alphanumeric strings with length 9!\") }}\n            {%- endif %}\n            {{- ', \"id\": \"' + tool_call.id + '\"}' }}\n            {%- if not loop.last %}\n                {{- \", \" }}\n            {%- else %}\n                {{- \"]\" + eos_token }}\n            {%- endif %}\n        {%- endfor %}\n    {%- elif message[\"role\"] == \"assistant\" %}\n        {{- \" \" + message[\"content\"]|trim + eos_token}}\n    {%- elif message[\"role\"] == \"tool_results\" or message[\"role\"] == \"tool\" %}\n        {%- if message.content is defined and message.content.content is defined %}\n            {%- set content = message.content.content %}\n        {%- else %}\n            {%- set content = message.content %}\n        {%- endif %}\n        {{- '[TOOL_RESULTS] {\"content\": ' + content|string + \", \" }}\n        {%- if not message.tool_call_id is defined or message.tool_call_id|length != 9 %}\n            {{- raise_exception(\"Tool call IDs should be alphanumeric strings with length 9!\") }}\n        {%- endif %}\n        {{- '\"call_id\": \"' + message.tool_call_id + '\"}[/TOOL_RESULTS]' }}\n    {%- else %}\n        {{- raise_exception(\"Only user and assistant roles are supported, with the exception of an initial optional system message!\") }}\n    {%- endif %}\n{%- endfor %}\n",
        "tool_use_grammar": lambda tools: f"""
            root   ::= ("[TOOL_CALLS] " "[" {gbnf_or([gbnf_sanitize(tool["function"]["name"]) for tool in tools])} "]") | (nottoolcalls .*)
            nottoolcalls ::= {gbnf_not("[TOOL_CALLS] ")}
        """,
        "tool_use_regex": '^\\[TOOL_CALLS\\] (\\[.*\\])$',
    },
    "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF": {
        "filename": "Meta-Llama-3.1-8B-Instruct-IQ4_XS.gguf",
        "template": "{% set loop_messages = messages %}{% for message in loop_messages %}{% set role = message['role'] %}{% if role == 'tool' %}{% set role = 'ipython' %}{% endif %}{% set text = message['content'] %}{% if loop.index0 == 0 and tools is defined %}{% set text = message['content'] + '\nHere is a list of functions in JSON format that you can invoke:\n' + tools|tojson + '\nShould you decide to return the function call, must put it at the beginning of your response, without any additional text and in the following format: [func_name({\"params_name1\":\"params_value1\", \"params_name2\"=\"params_value2\"})]. You may also choose not to call any function, if no function matches the users request.' %}{% endif %}{% set content = '<|start_header_id|>' + role + '<|end_header_id|>\n\n'+ text | trim + '<|eot_id|>' %}{% if loop.index0 == 0 %}{% set content = bos_token + content %}{% endif %}{{ content }}{% endfor %}{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' }}",
        "tool_use_grammar": lambda tools: f"""
            root   ::= ("[" {gbnf_or([gbnf_literal(tool["function"]["name"])+'"("'+gbnf_sanitize(tool["function"]["name"])+'-arguments'+'")"' for tool in tools])} "]" )| ( [^\\[] .* )
        """,
        "tool_use_regex": '^\\[([a-zA-Z0-9_-]+)\\((.*)\\)\\]$',
        "tool_use_parser": lambda regex: [{"name": regex.groups()[0], "arguments": json.loads(regex.groups()[1])}],
    },
    "lmstudio-community/Mistral-Nemo-Instruct-2407-GGUF": {
        "filename": "Mistral-Nemo-Instruct-2407-IQ4_XS.gguf",
        "template": "{%- if messages[0][\"role\"] == \"system\" %}\n    {%- set system_message = messages[0][\"content\"] %}\n    {%- set loop_messages = messages[1:] %}\n{%- else %}\n    {%- set loop_messages = messages %}\n{%- endif %}\n{%- if not tools is defined %}\n    {%- set tools = none %}\n{%- endif %}\n{%- set user_messages = loop_messages | selectattr(\"role\", \"equalto\", \"user\") | list %}\n\n{#- This block checks for alternating user/assistant messages, skipping tool calling messages #}\n{%- set ns = namespace() %}\n{%- set ns.index = 0 %}\n{%- for message in loop_messages %}\n    {%- if not (message.role == \"tool\" or message.role == \"tool_results\" or (message.tool_calls is defined and message.tool_calls is not none)) %}\n        {%- if (message[\"role\"] == \"user\") != (ns.index % 2 == 0) %}\n            {{- raise_exception(\"After the optional system message, conversation roles must alternate user/assistant/user/assistant/...\") }}\n        {%- endif %}\n        {%- set ns.index = ns.index + 1 %}\n    {%- endif %}\n{%- endfor %}\n\n{{- bos_token }}\n{%- for message in loop_messages %}\n    {%- if message[\"role\"] == \"user\" %}\n        {%- if tools is not none and (message == user_messages[-1]) %}\n            {{- \"[AVAILABLE_TOOLS] [\" }}\n            {%- for tool in tools %}\n                {%- set tool = tool.function %}\n                {{- '{\"type\": \"function\", \"function\": {' }}\n                {%- for key, val in tool.items() if key != \"return\" %}\n                    {%- if val is string %}\n                        {{- '\"' + key + '\": \"' + val + '\"' }}\n                    {%- else %}\n                        {{- '\"' + key + '\": ' + val|tojson }}\n                    {%- endif %}\n                    {%- if not loop.last %}\n                        {{- \", \" }}\n                    {%- endif %}\n                {%- endfor %}\n                {{- \"}}\" }}\n                {%- if not loop.last %}\n                    {{- \", \" }}\n                {%- else %}\n                    {{- \"]\" }}\n                {%- endif %}\n            {%- endfor %}\n            {{- \"[/AVAILABLE_TOOLS]\" }}\n            {%- endif %}\n        {%- if loop.last and system_message is defined %}\n            {{- \"[INST] \" + system_message + \"\\n\\n\" + message[\"content\"] + \"[/INST]\" }}\n        {%- else %}\n            {{- \"[INST] \" + message[\"content\"] + \"[/INST]\" }}\n        {%- endif %}\n    {%- elif message.tool_calls is defined and message.tool_calls is not none %}\n        {{- \"[TOOL_CALLS] [\" }}\n        {%- for tool_call in message.tool_calls %}\n            {%- set out = tool_call.function|tojson %}\n            {{- out[:-1] }}\n            {%- if not tool_call.id is defined or tool_call.id|length != 9 %}\n                {{- raise_exception(\"Tool call IDs should be alphanumeric strings with length 9!\") }}\n            {%- endif %}\n            {{- ', \"id\": \"' + tool_call.id + '\"}' }}\n            {%- if not loop.last %}\n                {{- \", \" }}\n            {%- else %}\n                {{- \"]\" + eos_token }}\n            {%- endif %}\n        {%- endfor %}\n    {%- elif message[\"role\"] == \"assistant\" %}\n        {{- \" \" + message[\"content\"]|trim + eos_token}}\n    {%- elif message[\"role\"] == \"tool_results\" or message[\"role\"] == \"tool\" %}\n        {%- if message.content is defined and message.content.content is defined %}\n            {%- set content = message.content.content %}\n        {%- else %}\n            {%- set content = message.content %}\n        {%- endif %}\n        {{- '[TOOL_RESULTS] {\"content\": ' + content|string + \", \" }}\n        {%- if not message.tool_call_id is defined or message.tool_call_id|length != 9 %}\n            {{- raise_exception(\"Tool call IDs should be alphanumeric strings with length 9!\") }}\n        {%- endif %}\n        {{- '\"call_id\": \"' + message.tool_call_id + '\"}[/TOOL_RESULTS]' }}\n    {%- else %}\n        {{- raise_exception(\"Only user and assistant roles are supported, with the exception of an initial optional system message!\") }}\n    {%- endif %}\n{%- endfor %}\n",
        "tool_use_grammar": lambda tools: f"""
            root   ::= ("[TOOL_CALLS] " "[" {gbnf_or([gbnf_sanitize(tool["function"]["name"]) for tool in tools])} "]") | (nottoolcalls .*)
            nottoolcalls ::= {gbnf_not("[TOOL_CALLS] ")}
        """,
        "tool_use_regex": '^\\[TOOL_CALLS\\] (\\[(.*\\])$',
    },
    "allenai/OLMoE-1B-7B-0924-Instruct-GGUF": {
        "filename": "olmoe-1b-7b-0924-instruct-q4_k_m.gguf",
        "template": "{{ bos_token }}{% for message in messages %}\n{% if message['role'] == 'system' %}\n{{ '<|system|>\n' + message['content'] }}\n{% elif message['role'] == 'user' %}\n{{ '<|user|>\n' + message['content'] }}\n{% elif message['role'] == 'assistant' %}\n{{ '<|assistant|>\n'  + message['content'] + eos_token }}\n{% endif %}\n{% if loop.last and add_generation_prompt %}\n{{ '<|assistant|>' }}\n{% endif %}\n{% endfor %}",
        "tool_use_grammar": lambda tools: f'''
            root   ::= .*
        ''',
        "tool_use_regex": '^\\[TOOL_CALLS\\] (\\[.*\\])$',
    },
    "Salesforce/xLAM-1b-fc-r-gguf": {
        "filename": "xLAM-1b-fc-r.Q4_K_M.gguf",
        "template": "{% set system_message = 'You are an AI assistant for function calling.\\n' %}{% if messages[0]['role'] == 'system' %}{% set system_message = messages[0]['content'] %}{% endif %}{% if system_message is defined %}{{ system_message }}{% endif %}{% for message in messages %}{% set content = message['content'] %}{% if message['role'] == 'user' %}{{ '### Instruction:\\n' + content + '\\n### Response:' }}{% elif message['role'] == 'assistant' %}{{ '\\n' + content + '\\n<|EOT|>\\n' }}{% endif %}{% endfor %}",
        "tool_use_grammar": lambda tools: f"""
            root   ::= {gbnf_literal('{"tool_calls": [')} {gbnf_or([gbnf_sanitize(tool["function"]["name"]) for tool in tools])}  {gbnf_literal("]}")}
        """,
        "tool_use_regex": '^\\{"tool_calls": (\\[.*\\])\\}$',
    },
    "bartowski/functionary-small-v3.1-GGUF": {
        "filename": "functionary-small-v3.1-IQ4_XS.gguf",
        "template": "{# version=v3-llama3.1 #}{%- if not tools is defined -%}\n    {%- set tools = none -%}\n{%- endif -%}\n\n{%- set has_code_interpreter = tools | selectattr(\"type\", \"equalto\", \"code_interpreter\") | list | length > 0 -%}\n{%- if has_code_interpreter -%}\n    {%- set tools = tools | rejectattr(\"type\", \"equalto\", \"code_interpreter\") | list -%}\n{%- endif -%}\n\n{#- System message + builtin tools #}\n{{- bos_token + \"<|start_header_id|>system<|end_header_id|>\\n\\n\" }}\n{%- if has_code_interpreter %}\n    {{- \"Environment: ipython\\n\\n\" }}\n{%- else -%}\n    {{ \"\\n\"}}\n{%- endif %}\n{{- \"Cutting Knowledge Date: December 2023\\n\\n\" }}\n{%- if tools %}\n    {{- \"\\nYou have access to the following functions:\\n\\n\" }}\n    {%- for t in tools %}\n        {%- if \"type\" in t -%}\n            {{ \"Use the function '\"|safe + t[\"function\"][\"name\"] + \"' to '\"|safe + t[\"function\"][\"description\"] + \"'\\n\"|safe + t[\"function\"] | tojson() }}\n        {%- else -%}\n            {{ \"Use the function '\"|safe + t[\"name\"] + \"' to '\"|safe + t[\"description\"] + \"'\\n\"|safe + t | tojson() }}\n        {%- endif -%}\n        {{- \"\\n\\n\" }}\n    {%- endfor %}\n    {{- '\\nThink very carefully before calling functions.\\nIf a you choose to call a function ONLY reply in the following format:\\n<{start_tag}={function_name}>{parameters}{end_tag}\\nwhere\\n\\nstart_tag => `<function`\\nparameters => a JSON dict with the function argument name as key and function argument value as value.\\nend_tag => `</function>`\\n\\nHere is an example,\\n<function=example_function_name>{\"example_name\": \"example_value\"}</function>\\n\\nReminder:\\n- If looking for real time information use relevant functions before falling back to brave_search\\n- Function calls MUST follow the specified format, start with <function= and end with </function>\\n- Required parameters MUST be specified\\n- Only call one function at a time\\n- Put the entire function call reply on one line\\n\\n' -}}\n{%- endif %}\n{{- \"<|eot_id|>\" -}}\n\n{%- for message in messages -%}\n    {%- if message['role'] == 'user' or message['role'] == 'system' -%}\n        {{ '<|start_header_id|>' + message['role'] + '<|end_header_id|>\\n\\n' + message['content'] + '<|eot_id|>' }}\n    {%- elif message['role'] == 'tool' -%}\n        {{ '<|start_header_id|>ipython<|end_header_id|>\\n\\n' + message['content'] + '<|eot_id|>' }}\n    {%- else -%}\n        {{ '<|start_header_id|>' + message['role'] + '<|end_header_id|>\\n\\n'}}\n        {%- if message['content'] -%}\n            {{ message['content'] }}\n        {%- endif -%}\n        {%- if 'tool_calls' in message and message['tool_calls'] -%}\n            {%- for tool_call in message['tool_calls'] -%}\n                {%- if tool_call[\"function\"][\"name\"] == \"python\" -%}\n                    {{ '<|python_tag|>' + tool_call['function']['arguments'] }}\n                {%- else -%}\n                    {{ '<function=' + tool_call['function']['name'] + '>' + tool_call['function']['arguments'] + '</function>' }}\n                {%- endif -%}\n            {%- endfor -%}\n            {{ '<|eom_id|>' }}\n        {%- else -%}\n            {{ '<|eot_id|>' }}\n        {%- endif -%}\n    {%- endif -%}\n{%- endfor -%}\n{%- if add_generation_prompt -%}\n    {{ '<|start_header_id|>assistant<|end_header_id|>\\n\\n' }}\n{%- endif -%}",
        "tool_use_grammar": lambda tools: f"""
            root   ::= ("<function=" {gbnf_or([gbnf_literal(tool["function"]["name"])+'">"'+gbnf_sanitize(tool["function"]["name"])+'-arguments' for tool in tools])} "</function>")  | ( {gbnf_not("<function")} .* )
        """,
        "tool_use_regex": '^<function=([a-zA-Z0-9_-]+)>(.*)</function>',
        "tool_use_parser": lambda regex: [{"name": regex.groups()[0], "arguments": json.loads(regex.groups()[1])}],
    },
}


def init_llm(model_path: str):
    if model_path == "None":
        return None
    
    model_preset = model_presets.get(model_path)
    llm = Llama.from_pretrained(
        repo_id=model_path,
        filename=model_preset.get("filename"),
        n_ctx=8192,
        n_gpu_layers=1000,

        chat_handler=create_chat_completion_handler(
            **model_preset,
        ),
    )

    
    #cache = LlamaRAMCache()
    cache = LlamaDiskCache(capacity_bytes=(8 << 30))
    llm.set_cache(cache)

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
        temperature=1.5,
        min_p=0.1,
    )

    return completion

if __name__ == '__main__':
    llm_model = init_llm('bartowski/functionary-small-v3.1-GGUF')

    tools = [
        {
            "type": "function",
            "function": {
                "name": "fire",
                "description": "start firing primary weapons",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "holdFire",
                "description": "stop firing primary weapons",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fireSecondary",
                "description": "start secondary primary weapons",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "holdFireSecondary",
                "description": "stop secondary primary weapons",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "hyperSuperCombination",
                "description": "initiate FSD Jump, required to jump to the next system or to enter supercruise",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "setSpeedZero",
                "description": "Set speed to 0%",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "setSpeed50",
                "description": "Set speed to 50%",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "setSpeed100",
                "description": "Set speed to 100%",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "deployHeatSink",
                "description": "Deploy heat sink",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "deployHardpointToggle",
                "description": "Deploy or retract hardpoints",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "increaseEnginesPower",
                "description": "Increase engine power, can be done multiple times",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pips": {
                            "type": "integer",
                            "description": "Amount of pips to increase engine power, default: 1, maximum: 4"
                        }
                    },
                    "required": [
                        "pips"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "increaseWeaponsPower",
                "description": "Increase weapon power, can be done multiple times",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pips": {
                            "type": "integer",
                            "description": "Amount of pips to increase weapon power, default: 1, maximum: 4"
                        }
                    },
                    "required": [
                        "pips"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "increaseSystemsPower",
                "description": "Increase systems power, can be done multiple times",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pips": {
                            "type": "integer",
                            "description": "Amount of pips to increase systems power, default: 1, maximum: 4"
                        }
                    },
                    "required": [
                        "pips"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "galaxyMapOpen",
                "description": "Open galaxy map. Zoom in on system in map or plot a route.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "system_name": {
                            "type": "string",
                            "description": "System to display in the galaxy map, for route plotting."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "galaxyMapClose",
                "description": "Close galaxy map.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "systemMapOpen",
                "description": "Open or close system map",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "cycleNextTarget",
                "description": "Cycle to next target",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "cycleFireGroupNext",
                "description": "Cycle to next fire group",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "shipSpotLightToggle",
                "description": "Toggle ship spotlight",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ejectAllCargo",
                "description": "Eject all cargo",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "landingGearToggle",
                "description": "Toggle landing gear",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "useShieldCell",
                "description": "Use shield cell",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fireChaffLauncher",
                "description": "Fire chaff launcher",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "nightVisionToggle",
                "description": "Toggle night vision",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "recallDismissShip",
                "description": "Recall or dismiss ship, available on foot and inside SRV",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "selectHighestThreat",
                "description": "Target lock highest threat",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "toggleCargoScoop",
                "description": "Toggles cargo scoop",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "chargeECM",
                "description": "Charge ECM",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "getFactions",
                "description": "Retrieve information about factions for a system",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Answer inquiry if given, otherise give general overview. Example: 'What factions are at war?'"
                        },
                        "systemName": {
                            "type": "string",
                            "description": "Name of relevant system. Example: 'Sol'"
                        }
                    },
                    "required": [
                        "query",
                        "systemName"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "getStations",
                "description": "Retrieve information about stations for a system",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Answer inquiry if given, otherise give general overview. Example: 'What stations require immediate repair?'"
                        },
                        "systemName": {
                            "type": "string",
                            "description": "Name of relevant system. Example: 'Sol'"
                        }
                    },
                    "required": [
                        "query",
                        "systemName"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "getGalnetNews",
                "description": "Retrieve current interstellar news from Galnet",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Inquiry you are trying to answer. Example: 'What happened to the thargoids recently?'"
                        }
                    },
                    "required": [
                        "query"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "trade_plotter",
                "description": "Retrieve a trade route from the trade plotter. Ask for unknown values and make sure they are known.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "system": {
                            "type": "string",
                            "description": "Name of the current system. Example: 'Sol'"
                        },
                        "station": {
                            "type": "string",
                            "description": "Name of the current station. Example: 'Wakata Station'"
                        },
                        "max_hops": {
                            "type": "integer",
                            "description": "Maximum number of hops (jumps) allowed for the route."
                        },
                        "max_hop_distance": {
                            "type": "number",
                            "description": "Maximum distance in light-years for a single hop."
                        },
                        "starting_capital": {
                            "type": "number",
                            "description": "Available starting capital in credits."
                        },
                        "max_cargo": {
                            "type": "integer",
                            "description": "Maximum cargo capacity in tons."
                        },
                        "requires_large_pad": {
                            "type": "boolean",
                            "description": "Whether the station must have a large landing pad."
                        }
                    },
                    "required": [
                        "system",
                        "station",
                        "max_hops",
                        "max_hop_distance",
                        "starting_capital",
                        "max_cargo",
                        "requires_large_pad"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "system_finder",
                "description": "Find a star system based on allegiance, government, state, power, primary economy, and more. Ask for unknown values and ensure they are filled out.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reference_system": {
                            "type": "string",
                            "description": "Name of the current system. Example: 'Sol'"
                        },
                        "distance": {
                            "type": "number",
                            "description": "Maximum distance to search for systems, default: 50000"
                        },
                        "allegiance": {
                            "type": "array",
                            "description": "System allegiance to filter by",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "Alliance",
                                    "Empire",
                                    "Federation",
                                    "Guardian",
                                    "Independent",
                                    "Pilots Federation",
                                    "Player Pilots",
                                    "Thargoid"
                                ]
                            }
                        },
                        "state": {
                            "type": "array",
                            "description": "System state to filter by",
                            "items": {
                                "type": "string"
                            }
                        },
                        "government": {
                            "type": "array",
                            "description": "System government type to filter by",
                            "items": {
                                "type": "string"
                            }
                        },
                        "power": {
                            "type": "array",
                            "description": "Powers controlling or exploiting the system",
                            "items": {
                                "type": "string"
                            }
                        },
                        "primary_economy": {
                            "type": "array",
                            "description": "Primary economy type of the system",
                            "items": {
                                "type": "string"
                            }
                        },
                        "security": {
                            "type": "array",
                            "description": "Security level of the system",
                            "items": {
                                "type": "string"
                            }
                        },
                        "thargoid_war_state": {
                            "type": "array",
                            "description": "System's state in the Thargoid War",
                            "items": {
                                "type": "string"
                            }
                        },
                        "population": {
                            "type": "object",
                            "description": "Population comparison and value",
                            "properties": {
                                "comparison": {
                                    "type": "string",
                                    "description": "Comparison type",
                                    "enum": [
                                        "<",
                                        ">"
                                    ]
                                },
                                "value": {
                                    "type": "number",
                                    "description": "Size to compare with"
                                }
                            }
                        }
                    },
                    "required": [
                        "reference_system"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "station_finder",
                "description": "Find a station to buy or sell a commodity, to buy an outfitting module, with a Material Trader or Technology Broker. Ask for unknown values and make sure they are known.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reference_system": {
                            "type": "string",
                            "description": "Name of the current system. Example: 'Sol'"
                        },
                        "has_large_pad": {
                            "type": "boolean",
                            "description": "If the ship requires a large landing pad",
                            "example": False
                        },
                        "distance": {
                            "type": "number",
                            "description": "The maximum distance to search for stations",
                            "example": 50000
                        },
                        "material_trader": {
                            "type": "array",
                            "description": "Material traders to find",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "Encoded",
                                    "Manufactured",
                                    "Raw"
                                ]
                            },
                            "minItems": 1
                        },
                        "technology_broker": {
                            "type": "array",
                            "description": "Technology brokers to find",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "Guardian",
                                    "Human"
                                ]
                            },
                            "minItems": 1
                        },
                        "modules": {
                            "type": "array",
                            "description": "Outfitting modules to buy",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the module.",
                                        "example": "Frame Shift Drive"
                                    },
                                    "class": {
                                        "type": "array",
                                        "description": "Classes of the modules.",
                                        "items": {
                                            "type": "string",
                                            "enum": [
                                                "0",
                                                "1",
                                                "2",
                                                "3",
                                                "4",
                                                "5",
                                                "6",
                                                "7",
                                                "8"
                                            ]
                                        }
                                    },
                                    "rating": {
                                        "type": "array",
                                        "description": "Ratings of the modules.",
                                        "items": {
                                            "type": "string",
                                            "enum": [
                                                "A",
                                                "B",
                                                "C",
                                                "D",
                                                "E",
                                                "F",
                                                "G",
                                                "H",
                                                "I"
                                            ]
                                        },
                                        "example": [
                                            "A",
                                            "B",
                                            "C",
                                            "D"
                                        ]
                                    }
                                },
                                "required": [
                                    "name",
                                    "class",
                                    "rating"
                                ]
                            },
                            "minItems": 1
                        },
                        "market": {
                            "type": "array",
                            "description": "Market commodities to buy and sell",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the commodity.",
                                        "example": "Tritium"
                                    },
                                    "amount": {
                                        "type": "integer",
                                        "description": "Tons of cargo to sell or buy. Use maximum cargo capacity."
                                    },
                                    "transaction": {
                                        "type": "string",
                                        "description": "Type of transaction.",
                                        "enum": [
                                            "Buy",
                                            "Sell"
                                        ]
                                    }
                                },
                                "required": [
                                    "name",
                                    "amount",
                                    "transaction"
                                ]
                            },
                            "minItems": 1
                        },
                        "ships": {
                            "type": "array",
                            "description": "Ships to buy",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name of ship"
                                    }
                                },
                                "required": [
                                    "name"
                                ]
                            },
                            "minItems": 1
                        },
                        "services": {
                            "type": "array",
                            "description": "Services to use",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name services",
                                        "enum": [
                                            "Black Market",
                                            "Interstellar Factors Contact"
                                        ]
                                    }
                                },
                                "required": [
                                    "name"
                                ]
                            },
                            "minItems": 1
                        }
                    },
                    "required": [
                        "reference_system",
                        "has_large_pad"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "getVisuals",
                "description": "Describes what's currently visible to the Commander.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Describe what you are curious about in the description. Example: 'Count the number of pirates'"
                        }
                    },
                    "required": [
                        "query"
                    ]
                }
            }
        }
    ]

    print (llm(llm_model, {
        "messages": [
            {
                "role": "system",
                "content": "Let's roleplay in the universe of Elite: Dangerous. I will provide game events in parentheses; do not create new ones. Do not hallucinate any information that is not given to you. Do not use markdown in your responses. I am Commander Rude, an independent pilot and secret member of the Dark Wheel. \n\nYou are COVAS:NEXT, the onboard AI of my starship. You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, including galactic navigation, ship status, the current system, and more. \n\nDo not inform about my ship status and my location unless it's relevant or requested by me. Answer within 3 sentences. Acknowledge given orders. \n\nGuide and support me with witty, intelligent and sarcastic commentary. Provide clear mission briefings and humorous observations."
            },
            {
                "role": "user",
                "content": "(Ship status: {\"star_class\": null, \"body\": null, \"ship_type\": null, \"location\": null, \"target\": null, \"jumps_remains\": 0, \"dist_jumped\": 0, \"cargo_capacity\": 0, \"status\": {\"Shields Up\": true, \"In MainShip\": true}, \"time\": \"3310-10-19T14:20:18.667106\", \"legalState\": \"Clean\", \"balance\": 58541564, \"pips\": {\"system\": 1.0, \"engine\": 2.5, \"weapons\": 2.5}, \"cargo\": 0.0})"
            },
            {
                "role": "user",
                "content": "Hey, can you find a station that sells gold?"
            }
        ],
        "tools": tools,
    }))
