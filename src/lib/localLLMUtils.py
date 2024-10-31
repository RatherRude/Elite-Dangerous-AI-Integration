import json
import re
import sys
import time
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple, Union
import diskcache
from llama_cpp import BaseLlamaCache, Llama, LlamaDiskCache, LlamaRAMCache
import llama_cpp as llama
import llama_cpp
from llama_cpp.llama_chat_format import Jinja2ChatFormatter
import llama_cpp.llama_types as llama_types
import llama_cpp.llama_grammar as llama_grammar

from .localLLMGrammarUtils import functions_to_gbnf

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
        tool_use_parser = lambda regex: json.loads(regex.group(1))

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
        print('prompt_tokens:', len(prompt_tokens))
        if result.stop is not None:
            stop = [] if stop is None else [stop] if isinstance(stop, str) else stop
            rstop = result.stop if isinstance(result.stop, list) else [result.stop]
            stop = stop + rstop

        if response_format is not None and response_format["type"] == "json_object":
            grammar = llama_grammar.LlamaGrammar.from_string(
                llama_grammar.JSON_GBNF, verbose=False
            )
            if response_format["schema"] is not None:
                grammar = llama_grammar.LlamaGrammar.from_json_schema(
                    json.dumps(response_format["schema"]), 
                    verbose=False
                )

        if tools and tool_choice != "none":
            grammar_str = functions_to_gbnf([tool["function"] for tool in tools if tool["type"] == "function"])+"\n"
            grammar_str += tool_use_grammar(tools) 

            grammar = llama_grammar.LlamaGrammar.from_string(
                grammar_str, verbose=False
            )

        if llama.cache:
            llama._ctx.set_rng_seed(1) # deterministic cache
            try:
                cache_key, cache_length = llama.cache.find_prefix(prompt_tokens)
                eval_prefix_len = Llama.longest_token_prefix(
                    llama._input_ids.tolist(), prompt_tokens
                )
                cache_read_penalty = 1000  # cache needs to be at least 1000 tokens longer to be worth reading
                if cache_length > eval_prefix_len + cache_read_penalty:
                    cache_state = llama.cache.load_state(cache_key)
                    llama.load_state(cache_state)
                    if llama.verbose:
                        print("Llama._create_completion: cache hit", file=sys.stderr)
                elif llama.verbose:
                    print("Llama._create_completion: cache skip", file=sys.stderr)
                    
            except KeyError:
                if llama.verbose:
                    print("Llama._create_completion: cache miss", file=sys.stderr)

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

        generated_tokens = []
        stop_tokens = [llama.tokenize(token.encode('utf-8'), False, True)[0] for token in stop]
        stop_reason = None
        max_tokens = max_tokens if max_tokens is not None else llama.n_ctx()
        print ('max_tokens:', max_tokens)
        for token in token_gen:
            print(llama.detokenize([token], generated_tokens).decode('utf-8'), end="")
            sys.stdout.flush()
            if token in stop_tokens:
                stop_reason = "stop"
                break
            if len(generated_tokens) > max_tokens:
                stop_reason = "length"
                break
            generated_tokens.append(token)
        
        print()
        completion = llama._model.detokenize(generated_tokens, special=True).decode("utf-8")

        if llama.cache:
            cache_key, cache_length = llama.cache.find_prefix(prompt_tokens + generated_tokens)
            state_length = len(prompt_tokens + generated_tokens)
            cache_write_penalty = 2000  # new state needs to be at least 1000 tokens longer to be worth writing
            if cache_length < state_length - cache_write_penalty:
                if llama.verbose:
                    print("Llama._create_completion: cache save", file=sys.stderr)
                llama.cache[prompt_tokens + generated_tokens] = llama.save_state()
            elif llama.verbose:
                print("Llama._create_completion: cache save skip", file=sys.stderr)

        completion_id = "chat_" + str(int(time.time()))
        tool_calls = None
        content = None
        # check if the completion contains tool calls using regex
        if re.search(tool_use_regex, completion):
            match = re.search(tool_use_regex, completion)
            functions = tool_use_parser(match)
            print('extracted functions:', functions)
            tool_calls: llama_types.ChatCompletionMessageToolCalls = [{
                "id": "call_" + "_"+ str(i) +"_" + completion_id,
                "type": "function",
                "function": {
                    "name": function["name"],
                    "arguments": json.dumps(function["arguments"]),
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
                "completion_tokens": len(generated_tokens),
                "prompt_tokens": len(prompt_tokens),
                "total_tokens": len(generated_tokens) + len(prompt_tokens),
            },
        }
        return chat_completion
    return chat_completion_handler



class LlamaDiskCache(BaseLlamaCache):
    """Cache for a llama.cpp model using disk."""

    def __init__(
        self, cache_dir: str = ".cache/llama_cache", capacity_bytes: int = (2 << 30)
    ):
        super().__init__(capacity_bytes)
        self.cache = diskcache.Cache(cache_dir, size_limit=capacity_bytes, cull_limit=1)

    @property
    def cache_size(self):
        return int(self.cache.volume())  # type: ignore

    def _find_longest_prefix_key(
        self,
        key: Tuple[int, ...],
    ) -> Optional[Tuple[int, ...]]:
        min_len = 0
        min_key: Optional[Tuple[int, ...]] = None
        for k in self.cache.iterkeys():  # type: ignore
            prefix_len = llama_cpp.llama.Llama.longest_token_prefix(k, key)
            if prefix_len > min_len:
                min_len = prefix_len
                min_key = k  # type: ignore
        return min_key, min_len


    def find_prefix(self, key: Sequence[int]) -> "llama_cpp.llama.LlamaState":
        key = tuple(key)
        _key, _len = self._find_longest_prefix_key(key)
        return _key, _len
    
    def load_state(self, key: tuple) -> "llama_cpp.llama.LlamaState":
        value: "llama_cpp.llama.LlamaState" = self.cache.get(key)
        self.cache.touch(key)
        return value

    def __getitem__(self, key: Sequence[int]) -> "llama_cpp.llama.LlamaState":
        key = tuple(key)
        _key, _len = self._find_longest_prefix_key(key)
        if _key is None:
            raise KeyError("Key not found")
        value: "llama_cpp.llama.LlamaState" = self.cache.get(_key)  # type: ignore
        self.cache.touch(_key)  # type: ignore
        return value

    def __contains__(self, key: Sequence[int]) -> bool:
        _key, _len = self._find_longest_prefix_key(tuple(key)) is not None
        return _key

    def __setitem__(self, key: Sequence[int], value: "llama_cpp.llama.LlamaState"):
        print("LlamaDiskCache.__setitem__: called", file=sys.stderr)
        key = tuple(key)
        if key in self.cache:
            print("LlamaDiskCache.__setitem__: delete", file=sys.stderr)
            del self.cache[key]
        res = self.cache.set(key, value)
        print("LlamaDiskCache.__setitem__: set", res, file=sys.stderr)
        while self.cache_size > self.capacity_bytes and len(self.cache) > 0:
            print("LlamaDiskCache.__setitem__: trim",  self.cache_size, self.capacity_bytes, file=sys.stderr)
            key_to_remove = next(iter(self.cache))
            del self.cache[key_to_remove]
