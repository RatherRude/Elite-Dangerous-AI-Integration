import json
import re
import sys
import time
from typing import Callable, Dict, Iterator, List, Optional, Union
from llama_cpp import Llama
import llama_cpp as llama
from llama_cpp.llama_chat_format import Jinja2ChatFormatter
import llama_cpp.llama_types as llama_types
import llama_cpp.llama_grammar as llama_grammar


def create_chat_completion_handler(
    template: str,
    tool_use_grammar: str,
    tool_use_regex: str,
    tool_use_parser: Callable[[re.Match], List[llama_types.ChatCompletionFunction]] = None,
    bos_token: str = None,
    eos_token: str = None,
    **kwargs,  # type: ignore
):
    if tool_use_parser is None:
        tool_use_parser = lambda regex: json.loads(regex.group(0))

    def chat_completion_handler(
        *,
        llama: llama.Llama,
        messages: List[llama_types.ChatCompletionRequestMessage],
        functions: Optional[List[llama_types.ChatCompletionFunction]] = None,
        function_call: Optional[llama_types.ChatCompletionRequestFunctionCall] = None,
        tools: Optional[List[llama_types.ChatCompletionTool]] = None,
        tool_choice: Optional[llama_types.ChatCompletionToolChoiceOption] = None,
        temperature: float = 0.2,
        top_p: float = 0.95,
        top_k: int = 40,
        min_p: float = 0.05,
        typical_p: float = 1.0,
        stream: bool = False,
        stop: Optional[Union[str, List[str]]] = [],
        seed: Optional[int] = None,
        response_format: Optional[
            llama_types.ChatCompletionRequestResponseFormat
        ] = None,
        max_tokens: Optional[int] = None,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        repeat_penalty: float = 1.1,
        tfs_z: float = 1.0,
        mirostat_mode: int = 0,
        mirostat_tau: float = 5.0,
        mirostat_eta: float = 0.1,
        model: Optional[str] = None,
        logits_processor: Optional[llama.LogitsProcessorList] = None,
        grammar: Optional[llama.LlamaGrammar] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        **kwargs,  # type: ignore
    ) -> Union[
        llama_types.CreateChatCompletionResponse,
        Iterator[llama_types.CreateChatCompletionStreamResponse],
    ]:
        chat_formatter = Jinja2ChatFormatter(
            template=template,
            eos_token=eos_token if eos_token else llama._model.detokenize([llama.token_eos()], special=True).decode("utf-8"),
            bos_token=bos_token if bos_token else llama._model.detokenize([llama.token_bos()], special=True).decode("utf-8"),
        )

        result = chat_formatter(
            messages=messages,
            functions=functions,
            function_call=function_call,
            tools=tools,
            tool_choice=tool_choice,
        )

        prompt_tokens = llama.tokenize(
            result.prompt.encode("utf-8"),
            add_bos=not result.added_special,
            special=True,
        )
        if result.stop is not None:
            stop = [] if stop is None else [stop] if isinstance(stop, str) else stop
            rstop = result.stop if isinstance(result.stop, list) else [result.stop]
            stop = stop + rstop

        if response_format is not None and response_format["type"] == "json_object":
            grammar = llama_grammar.LlamaGrammar.from_string(
                llama_grammar.JSON_GBNF, verbose=llama.verbose
            )
            if response_format["schema"] is not None:
                grammar = llama_grammar.LlamaGrammar.from_json_schema(
                    json.dumps(response_format["schema"]), 
                    verbose=llama.verbose
                )

        if tools and tool_choice != "none":
            grammar_str = "\n".join(llama_grammar.JSON_GBNF.split("\n")[2:])
            grammar_str += tool_use_grammar  # TODO fix spaces around special token
            print(grammar_str)

            grammar = llama_grammar.LlamaGrammar.from_string(
                grammar_str, verbose=llama.verbose
            )
        
        token_gen = llama.generate(
            tokens=prompt_tokens,
            temp=temperature,
            top_p=top_p,
            top_k=top_k,
            min_p=min_p,
            typical_p=typical_p,
            #logprobs=top_logprobs if logprobs else None,
            #stream=False,
            #stop=stop,
            #seed=seed,
            #max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            repeat_penalty=repeat_penalty,
            tfs_z=tfs_z,
            mirostat_mode=mirostat_mode,
            mirostat_tau=mirostat_tau,
            mirostat_eta=mirostat_eta,
            #model=model,
            logits_processor=logits_processor,
            grammar=grammar,
            #logit_bias=logit_bias,
        )

        tokens = []
        stop_tokens = [llama.tokenize(token.encode('utf-8'), False, True)[0] for token in stop]
        stop_reason = None
        max_tokens = max_tokens if max_tokens is not None else llama.n_ctx()
        print ('max_tokens:', max_tokens)
        for token in token_gen:
            print(llama._model.detokenize(tokens, special=True).decode("utf-8"))
            if token in stop_tokens:
                stop_reason = "stop"
                break
            if len(tokens) > max_tokens:
                stop_reason = "length"
                break
            tokens.append(token)
        
        completion = llama._model.detokenize(tokens, special=True).decode("utf-8")
        print(completion)

        completion_id = "chat_" + str(int(time.time()))
        tool_calls = None
        content = None
        # check if the completion contains tool calls using regex
        if re.search(tool_use_regex, completion):
            match = re.search(tool_use_regex, completion)
            functions = tool_use_parser(match)
            tool_calls: llama_types.ChatCompletionMessageToolCalls = [{
                "id": "call_" + "_"+ str(i) +"_" + completion_id,
                "type": "function",
                "function": {
                    "name": function["name"],
                    "arguments": function["arguments"],
                },
            } for i, function in enumerate(functions)]
        else:
            content = completion
            
        chat_completion: llama_types.CreateChatCompletionResponse = {
            "id": completion_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model if model else llama.model_path,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    },
                    "logprobs": None,
                    "finish_reason": stop_reason,
                }
            ],
            "usage": {
                "completion_tokens": len(tokens),
                "prompt_tokens": len(prompt_tokens),
                "total_tokens": len(tokens) + len(prompt_tokens),
            },
        }
        return chat_completion
    return chat_completion_handler