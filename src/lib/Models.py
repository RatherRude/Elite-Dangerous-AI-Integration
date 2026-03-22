from abc import ABC, abstractmethod
from typing import Any, List, Optional, Generator, Iterable
import io
import base64
import json
import speech_recognition as sr
import soundfile as sf
import numpy as np
import threading
import traceback
from time import sleep, time
from uuid import uuid4
import edge_tts
import miniaudio
from openai.types.audio.speech_create_params import SpeechCreateParams
from openai import OpenAI, APIStatusError
from openai.types.chat import ChatCompletion, ChatCompletionMessageFunctionToolCall, ChatCompletionMessageToolCall
from openai.types import CreateEmbeddingResponse
from .Logger import log, ModelUsageStats

class LLMError(Exception):
    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error

class LLMModel(ABC):
    model_name: str
    provider_name: str | None

    def __init__(self, model_name: str, provider_name: str | None = None):
        self.model_name = model_name
        self.provider_name = provider_name

    @abstractmethod
    def generate(self, messages: List[dict], tools: Optional[List[dict]] = None, tool_choice: Optional[Any] = None) -> tuple[str | None, List[Any] | None, ModelUsageStats]:
        pass

class EmbeddingModel(ABC):
    model_name: str

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def create_embedding(self, input_text: str) -> tuple[str, List[float]]:
        pass

def _model_dump_compatible(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value

def _get_reasoning_tokens(usage: Any) -> int | None:
    for details_name in ("output_tokens_details", "completion_tokens_details"):
        details = getattr(usage, details_name, None)
        if details is None:
            continue

        reasoning_tokens = getattr(details, "reasoning_tokens", None)
        if reasoning_tokens is not None:
            return int(reasoning_tokens)

    return None

class OpenAILLMModel(LLMModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, temperature: float, reasoning_effort: Optional[str] = None, extra_body: Optional[dict] = None, extra_headers: Optional[dict] = None, provider_name: str | None = None):
        super().__init__(model_name, provider_name=provider_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.base_url = base_url
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.extra_body = extra_body or {}
        self.extra_headers = extra_headers or {}

    def generate(self, messages: List[dict], tools: Optional[List[dict]] = None, tool_choice: Optional[Any] = None) -> tuple[str | None, List[Any] | None, ModelUsageStats]:
        kwargs = {}
        # Special handling for specific models or providers if needed
        if self.model_name in ['gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5.1']:
            kwargs["verbosity"] = "low"
                    
        if 'google' in self.base_url or 'google' in self.model_name or 'gemini' in self.model_name:
            for m in messages:
                if 'tool_calls' in m and m.get('tool_calls', None):
                    calls = m.get('tool_calls', [])
                    if calls:
                        for i in range(len(calls)):
                            if not isinstance(calls[i], dict):
                                if hasattr(calls[i], 'model_dump'):
                                    calls[i] = calls[i].model_dump()
                                elif hasattr(calls[i], 'dict'):
                                    calls[i] = calls[i].dict()
                            
                            if isinstance(calls[i], dict):
                                thought_sig = calls[i].get('extra_content',{}).get('google', {}).get('thought_signature')
                                if not thought_sig:
                                    calls[i]['extra_content'] = {"google": {
                                        "thought_signature": "skip_thought_signature_validator"
                                    }}
        
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            **self.extra_body,
            **kwargs
        }
        if tools:
            params["tools"] = tools
            if tool_choice:
                params["tool_choice"] = tool_choice
        
        if self.reasoning_effort and self.reasoning_effort not in ["disabled", "default", None, ""]:
             params["reasoning_effort"] = self.reasoning_effort

        if self.extra_body:
            params["extra_body"] = self.extra_body
            
        if self.extra_headers:
            params["extra_headers"] = self.extra_headers

        try:
            completion = self.client.chat.completions.create(**params) # pyright: ignore[reportCallIssue]
        except APIStatusError as e:
            log("debug", "LLM error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "LLM error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'LLM {e.response.reason_phrase}: {message}', e)
        except Exception as e:
            raise LLMError(f'LLM Error: {str(e)}', e)

        if not isinstance(completion, ChatCompletion) or hasattr(completion, 'error'):
            log("debug", "LLM completion error:", completion)
            raise LLMError("LLM error: No valid completion received")
        
        if not completion.choices:
            log("debug", "LLM completion has no choices:", completion)
            return (None, None, ModelUsageStats(provider=self.provider_name, model_name=self.model_name)) # Treated as "..."

        if not hasattr(completion.choices[0], 'message') or not completion.choices[0].message:
            log("debug", "LLM completion choice has no message:", completion)
            return (None, None, ModelUsageStats(provider=self.provider_name, model_name=self.model_name)) # Treated as "..."
        
        usage_metadata = ModelUsageStats(provider=self.provider_name, model_name=self.model_name)
        if hasattr(completion, 'usage') and completion.usage:
            log("debug", f'LLM completion usage', completion.usage)
            usage_metadata.input_tokens = completion.usage.prompt_tokens
            usage_metadata.output_tokens = completion.usage.completion_tokens
            usage_metadata.total_tokens = completion.usage.total_tokens
            if hasattr(completion.usage, 'prompt_tokens_details') and completion.usage.prompt_tokens_details:
                usage_metadata.cached_tokens = getattr(completion.usage.prompt_tokens_details, 'cached_tokens', 0)
            usage_metadata.reasoning_tokens = _get_reasoning_tokens(completion.usage)
        
        response_text = None
        if hasattr(completion.choices[0].message, 'content'):
            response_text = completion.choices[0].message.content
            if completion.choices[0].message.content is None or completion.choices[0].message.content == "":
                log("debug", "LLM completion no content:", completion)
                response_text = None
        else:
            log("debug", f'LLM completion without text')
            response_text = None

        response_actions = None
        if hasattr(completion.choices[0].message, 'tool_calls'):
            response_actions = completion.choices[0].message.tool_calls

        if response_text is None and response_actions is None:
             return (None, None, usage_metadata)

        return (response_text, response_actions, usage_metadata)

    def list_models(self) -> List[str]:
        try:
            models = self.client.models.list()
            return [model.id for model in models]
        except Exception as e:
            raise e

class OpenAIResponsesLLMModel(LLMModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, temperature: float, reasoning_effort: Optional[str] = None, extra_body: Optional[dict] = None, extra_headers: Optional[dict] = None, provider_name: str | None = None):
        super().__init__(model_name, provider_name=provider_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.base_url = base_url
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.extra_body = extra_body or {}
        self.extra_headers = extra_headers or {}

    def _has_message_content(self, content: Any) -> bool:
        if content is None:
            return False
        if isinstance(content, str):
            return content != ""
        if isinstance(content, list):
            return len(content) > 0
        return True

    def _stringify_content(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        try:
            return json.dumps(content)
        except TypeError:
            return str(content)

    def _convert_content_part(self, part: Any) -> dict[str, Any]:
        part = _model_dump_compatible(part)
        if not isinstance(part, dict):
            return {"type": "input_text", "text": str(part)}

        part_type = part.get("type")
        if part_type in {"input_text", "input_image", "input_audio", "input_file"}:
            return part

        if part_type == "text":
            return {
                "type": "input_text",
                "text": str(part.get("text", "")),
            }

        if part_type == "image_url":
            image_value = part.get("image_url")
            image_url: str | None = None
            detail = "auto"
            if isinstance(image_value, dict):
                image_url = image_value.get("url")
                detail = image_value.get("detail", detail)
            elif isinstance(image_value, str):
                image_url = image_value

            if image_url:
                return {
                    "type": "input_image",
                    "image_url": image_url,
                    "detail": detail,
                }

        if part_type == "input_audio":
            return part

        return {
            "type": "input_text",
            "text": self._stringify_content(part),
        }

    def _convert_message_content(self, content: Any) -> str | list[dict[str, Any]]:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return [self._convert_content_part(part) for part in content]
        if isinstance(content, dict):
            return [self._convert_content_part(content)]
        return self._stringify_content(content)

    def _convert_assistant_tool_calls(self, tool_calls: Any) -> list[dict[str, Any]]:
        converted_calls: list[dict[str, Any]] = []
        for tool_call in tool_calls or []:
            tool_call = _model_dump_compatible(tool_call)
            if not isinstance(tool_call, dict):
                continue

            function_data = _model_dump_compatible(tool_call.get("function"))
            if not isinstance(function_data, dict):
                continue

            raw_call_id = tool_call.get("call_id") or tool_call.get("id") or f"call_{uuid4().hex}"
            raw_response_item_id = tool_call.get("id")
            converted_call = {
                "type": "function_call",
                "call_id": str(raw_call_id),
                "name": str(function_data.get("name", "")),
                "arguments": str(function_data.get("arguments") or "{}"),
            }

            # Chat-completions tool calls only provide a call ID like "call_xxx".
            # Responses API item IDs are separate and typically start with "fc_".
            if isinstance(raw_response_item_id, str) and raw_response_item_id.startswith("fc"):
                converted_call["id"] = raw_response_item_id

            converted_calls.append(converted_call)
        return converted_calls

    def _convert_tool_output_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        call_id = message.get("tool_call_id") or message.get("call_id")
        if not call_id:
            return None

        return {
            "type": "function_call_output",
            "call_id": str(call_id),
            "output": self._stringify_content(message.get("content", "")),
        }

    def _convert_messages(self, messages: List[dict]) -> list[dict[str, Any]]:
        converted_messages: list[dict[str, Any]] = []

        for raw_message in messages:
            message = _model_dump_compatible(raw_message)
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            content = message.get("content")
            tool_calls = message.get("tool_calls")

            if role == "tool":
                tool_output = self._convert_tool_output_message(message)
                if tool_output:
                    converted_messages.append(tool_output)
                continue

            if role in {"system", "developer", "user", "assistant"} and self._has_message_content(content):
                converted_messages.append({
                    "type": "message",
                    "role": role,
                    "content": self._convert_message_content(content),
                })

            if role == "assistant" and tool_calls:
                converted_messages.extend(self._convert_assistant_tool_calls(tool_calls))

        return converted_messages

    def _convert_tools(self, tools: List[dict]) -> list[dict[str, Any]]:
        converted_tools: list[dict[str, Any]] = []

        for raw_tool in tools:
            tool = _model_dump_compatible(raw_tool)
            if not isinstance(tool, dict):
                continue

            if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
                function_data = _model_dump_compatible(tool["function"])
                converted_tool = {
                    "type": "function",
                    "name": function_data.get("name"),
                    "description": function_data.get("description"),
                    "parameters": function_data.get("parameters"),
                }
                strict = function_data.get("strict")
                if strict is not None:
                    converted_tool["strict"] = strict
                converted_tools.append({k: v for k, v in converted_tool.items() if v is not None})
                continue

            converted_tools.append(tool)

        return converted_tools

    def _convert_tool_choice(self, tool_choice: Any) -> Any:
        tool_choice = _model_dump_compatible(tool_choice)
        if isinstance(tool_choice, str):
            return tool_choice

        if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
            function_data = _model_dump_compatible(tool_choice.get("function"))
            if isinstance(function_data, dict):
                return {
                    "type": "function",
                    "name": function_data.get("name"),
                }

        return tool_choice

    def _extract_tool_calls(self, response: Any) -> list[ChatCompletionMessageFunctionToolCall] | None:
        tool_calls: list[ChatCompletionMessageFunctionToolCall] = []

        for output_item in getattr(response, "output", []) or []:
            item = _model_dump_compatible(output_item)
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue

            call_id = str(item.get("call_id") or item.get("id") or f"call_{uuid4().hex}")
            tool_calls.append(ChatCompletionMessageFunctionToolCall.model_validate({
                "type": "function",
                "id": call_id,
                "function": {
                    "name": str(item.get("name", "")),
                    "arguments": str(item.get("arguments") or "{}"),
                },
            }))

        return tool_calls or None

    def generate(self, messages: List[dict], tools: Optional[List[dict]] = None, tool_choice: Optional[Any] = None) -> tuple[str | None, List[Any] | None, ModelUsageStats]:
        params: dict[str, Any] = {
            "model": self.model_name,
            "input": self._convert_messages(messages),
            "temperature": self.temperature,
        }

        if self.model_name in ['gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5.4-mini', 'gpt-5.4-nano', 'gpt-5.4', 'gpt-5.1']:
            params["text"] = {"verbosity": "low"}

        if tools:
            params["tools"] = self._convert_tools(tools)
            if tool_choice:
                params["tool_choice"] = self._convert_tool_choice(tool_choice)

        if self.reasoning_effort and self.reasoning_effort not in ["disabled", "default", "none", None, ""]:
            params["reasoning"] = {"effort": self.reasoning_effort}

        if self.extra_body:
            params["extra_body"] = self.extra_body

        if self.extra_headers:
            params["extra_headers"] = self.extra_headers

        try:
            response = self.client.responses.create(**params)
        except APIStatusError as e:
            log("debug", "LLM error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "LLM error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))

            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message

            raise LLMError(f'LLM {e.response.reason_phrase}: {message}', e)
        except Exception as e:
            raise LLMError(f'LLM Error: {str(e)}', e)

        if getattr(response, "error", None):
            log("debug", "LLM response error:", response)
            raise LLMError("LLM error: No valid response received")

        usage_metadata = ModelUsageStats(provider=self.provider_name, model_name=self.model_name)
        if hasattr(response, 'usage') and response.usage:
            log("debug", "LLM response usage", response.usage)
            usage_metadata.input_tokens = getattr(response.usage, "input_tokens", 0)
            usage_metadata.output_tokens = getattr(response.usage, "output_tokens", 0)
            usage_metadata.total_tokens = getattr(response.usage, "total_tokens", 0)
            if hasattr(response.usage, "input_tokens_details") and response.usage.input_tokens_details:
                usage_metadata.cached_tokens = getattr(response.usage.input_tokens_details, "cached_tokens", 0)
            usage_metadata.reasoning_tokens = _get_reasoning_tokens(response.usage)

        response_text = getattr(response, "output_text", None) or None
        response_actions = self._extract_tool_calls(response)

        if response_text is None and response_actions is None:
            return (None, None, usage_metadata)

        return (response_text, response_actions, usage_metadata)

    def list_models(self) -> List[str]:
        try:
            models = self.client.models.list()
            return [model.id for model in models]
        except Exception as e:
            raise e

class OpenAIEmbeddingModel(EmbeddingModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, extra_headers: Optional[dict] = None, extra_body: Optional[dict] = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.extra_headers = extra_headers or {}
        self.extra_body = extra_body or {}

    def create_embedding(self, input_text: str) -> tuple[str, List[float]]:
        params: dict[str, Any] = {
            "model": self.model_name,
            "input": input_text,
            **self.extra_body
        }
        if self.extra_headers:
            params["extra_headers"] = self.extra_headers
            
        response = self.client.embeddings.create(**params)
        return (response.model, response.data[0].embedding)

class STTModel(ABC):
    model_name: str

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def transcribe(self, audio: sr.AudioData) -> str:
        pass

class OpenAISTTModel(STTModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, language: Optional[str] = None, prompt: Optional[str] = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.language = language
        self.prompt = prompt

    def transcribe(self, audio: sr.AudioData) -> str:
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        # Convert raw PCM data to numpy array
        audio_np = np.frombuffer(audio_raw, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Create a BytesIO buffer for the Ogg file
        audio_ogg = io.BytesIO()
        
        # Write as Ogg Vorbis
        sf.write(audio_ogg, audio_np, 16000, format='OGG', subtype='VORBIS')
        audio_ogg.seek(0)
        audio_ogg.name = "audio.ogg"  # OpenAI needs a filename
        
        try:
            kwargs: dict[str, Any] = {
                "model": self.model_name,
                "file": audio_ogg,
                "language": self.language if self.language else None,  # pyright: ignore[reportArgumentType]
            }
            if self.prompt:
                kwargs["prompt"] = self.prompt

            transcription = self.client.audio.transcriptions.create(**kwargs)
        except APIStatusError as e:
            log("debug", "STT error request:", e.request.method, e.request.url, e.request.headers)
            log("debug", "STT error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'STT {e.response.reason_phrase}: {message}', e)
        
        text = transcription.text
        return text

class OpenAIMultiModalSTTModel(STTModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, prompt: Optional[str] = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.prompt = prompt

    def transcribe(self, audio: sr.AudioData) -> str:
        audio_raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        # Convert raw PCM data to numpy array
        audio_np = np.frombuffer(audio_raw, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Create a BytesIO buffer for the Ogg file
        audio_wav = io.BytesIO()
        
        # Write as Ogg Vorbis
        sf.write(audio_wav, audio_np, 16000, format='WAV', subtype='PCM_16')
        audio_wav.seek(0)
        audio_wav.name = "audio.wav"  # OpenAI needs a filename
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role":"system", "content":
                        "You are a high quality transcription model. You are given audio input from the user, and return the transcribed text from the input. Do NOT add any additional text in your response, only respond with the text given by the user.\n" +
                        "The audio may be related to space sci-fi terminology like systems, equipment, and station names, specifically the game Elite Dangerous.\n" + 
                        #"Here is an example of the type of text you should return: <example>" + self.prompt + "</example>\n" +
                        "Always provide an exact transcription of the audio. If the user is not speaking or inaudible, return only the word 'silence'."
                    },
                    {"role": "user", "content": [{
                        "type": "text",
                        "text": "<input>"
                    },{
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(audio_wav.getvalue()).decode('utf-8'),
                            "format": "wav"
                        }
                    },{
                        "type": "text",
                        "text": "</input>"
                    },]}
                ]
            )
        except APIStatusError as e:
            log("debug", "STT mm error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "STT mm error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'STT {e.response.reason_phrase}: {message}', e)
        
        if not response.choices or not hasattr(response.choices[0], 'message') or not hasattr(response.choices[0].message, 'content'):
            log('debug', "STT mm response is incomplete or malformed:", response)
            raise LLMError('STT completion error: Response incomplete or malformed')
        
        text = response.choices[0].message.content
        if not text:
            return ''
        if text.strip() == 'silence' or text.strip() == '':
            return ''
        return text.strip()

class Mp3Stream(miniaudio.StreamableSource):
    def __init__(self, gen: Generator, prebuffer_size=4, initial_timeout: float = 10.0, chunk_timeout: float = 5.0) -> None:
        super().__init__()
        self.gen = gen
        self.prebuffer_size = prebuffer_size
        self.initial_timeout = initial_timeout
        self.chunk_timeout = chunk_timeout
        self.buffer = bytearray()
        self._done = False
        self._closed = False
        self._first_chunk = False
        self._last_chunk_time = time()
        threading.Thread(target=self._produce, daemon=True).start()

    def _produce(self):
        try:
            for ev in self.gen:
                if self._closed:
                    break
                if isinstance(ev, dict) and ev.get('type') == 'audio':
                    self.buffer.extend(ev['data'])
                    self._first_chunk = True
                    self._last_chunk_time = time()
        except Exception as e:
            log('error', 'Mp3Stream producer exception', e, traceback.format_exc())
            raise e
        finally:
            self._done = True

    def close(self):  # type: ignore[override]
        self._closed = True
        return super().close()

    def read(self, num_bytes: int) -> bytes:
        if self._closed:
            return b''
        out = bytearray()
        need = max(self.prebuffer_size * 720, num_bytes)
        while len(out) < need:
            # timeout checks
            timeout = self.initial_timeout if not self._first_chunk else self.chunk_timeout
            if (not self._done) and (time() - self._last_chunk_time > timeout):
                log('warn', 'TTS Stream timeout (initial)' if not self._first_chunk else 'TTS Stream timeout (gap)')
                self.close()
                raise IOError('TTS Stream timeout')
            if self.buffer:
                take = min(len(self.buffer), need - len(out))
                out.extend(self.buffer[:take])
                del self.buffer[:take]
            else:
                if self._done:
                    break
                sleep(0.01)
        return bytes(out)

class TTSModel(ABC):
    model_name: str

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        pass

class OpenAITTSModel(TTSModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, speed: float = 1.0, voice_instructions: str | None = None):
        super().__init__(model_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.speed = speed
        self.voice_instructions = voice_instructions

    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        try:
            kwargs: SpeechCreateParams = {
                "model": self.model_name,
                "voice": voice, # pyright: ignore[reportArgumentType]
                "input": text,
                "response_format": "pcm",
                "speed": self.speed
            }
            if self.voice_instructions:
                kwargs["instructions"] = self.voice_instructions
            
            with self.client.audio.speech.with_streaming_response.create(**kwargs) as response:
                for chunk in response.iter_bytes(1024):
                    yield chunk
        except APIStatusError as e:
            log("debug", "TTS error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "TTS error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'TTS {e.response.reason_phrase}: {message}', e)

class EdgeTTSModel(TTSModel):
    def __init__(self, model_name: str, speed: float = 1.0):
        super().__init__(model_name)
        self.speed = speed
        self.prebuffer_size = 4

    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        rate = f"+{int((float(self.speed) - 1) * 100)}%" if float(self.speed) > 1 else f"-{int((1 - float(self.speed)) * 100)}%"
        response = edge_tts.Communicate(text, voice=voice, rate=rate)
        
        pcm_stream = miniaudio.stream_any(
            source=Mp3Stream(response.stream_sync(), self.prebuffer_size),
            source_format=miniaudio.FileFormat.MP3,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=24000,
            frames_to_read=1024 // 2
        )

        for i in pcm_stream:
            yield i.tobytes()

def create_llm_model(provider: str, config: dict, prefix: str = "llm") -> LLMModel:
    base_url = str(config.get(f"{prefix}_endpoint", ""))
    api_key = str(config.get("api_key") if config.get(f"{prefix}_api_key", "") == "" else config.get(f"{prefix}_api_key"))
    model_name = str(config.get(f"{prefix}_model_name", ""))
    temperature = float(config.get(f"{prefix}_temperature", 1.0))
    reasoning_effort = config.get(f"{prefix}_reasoning_effort", None)
    if reasoning_effort:
        reasoning_effort = str(reasoning_effort)
    
    if provider == "openai":
        if not base_url:
            base_url = "https://api.openai.com/v1"
    elif provider == "google-ai-studio":
        if not base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta"
    elif provider == "openrouter":
        if not base_url:
            base_url = "https://openrouter.ai/api/v1"
            
    extra_body = {}
    extra_headers = {}

    if provider == "openai":
        return OpenAIResponsesLLMModel(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body,
            extra_headers=extra_headers,
            provider_name=provider,
        )

    return OpenAILLMModel(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
        extra_body=extra_body,
        extra_headers=extra_headers,
        provider_name=provider,
    )

def create_embedding_model(provider: str, config: dict, prefix: str = "embedding") -> EmbeddingModel:
    base_url = str(config.get(f"{prefix}_endpoint", ""))
    api_key = str(config.get("api_key") if config.get(f"{prefix}_api_key", "") == "" else config.get(f"{prefix}_api_key"))
    model_name = str(config.get(f"{prefix}_model_name", ""))
    
    if provider == "openai":
        if not base_url:
            base_url = "https://api.openai.com/v1"
    elif provider == "google-ai-studio":
        if not base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta"
    elif provider == "openrouter":
        if not base_url:
            base_url = "https://openrouter.ai/api/v1"
          

    return OpenAIEmbeddingModel(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
    )

def create_stt_model(provider: str, config: dict, prefix: str = "stt") -> STTModel | None:
    if provider == 'none':
        return None

    base_url = str(config.get(f"{prefix}_endpoint", ""))
    api_key = str(config.get("api_key") if config.get(f"{prefix}_api_key", "") == "" else config.get(f"{prefix}_api_key"))
    model_name = str(config.get(f"{prefix}_model_name", "whisper-1"))
    language = config.get(f"{prefix}_language", None)
    prompt = config.get(f"{prefix}_prompt", "COVAS, give me a status update... and throw in something inspiring, would you?")

    if provider == "openai" or provider == "custom" or provider == "local-ai-server":
        if provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"
        return OpenAISTTModel(base_url, api_key, model_name, language, prompt)
    
    elif provider == "google-ai-studio" or provider == "custom-multi-modal":
        if provider == "google-ai-studio" and not base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta"
        return OpenAIMultiModalSTTModel(base_url, api_key, model_name, prompt)
    
    return None

def create_tts_model(provider: str, config: dict, prefix: str = "tts") -> TTSModel | None:
    if provider == 'none':
        return None

    base_url = str(config.get(f"{prefix}_endpoint", ""))
    api_key = str(config.get("api_key") if config.get(f"{prefix}_api_key", "") == "" else config.get(f"{prefix}_api_key"))
    model_name = str(config.get(f"{prefix}_model_name", "tts-1"))
    speed = float(config.get(f"{prefix}_speed", 1.0))
    voice_instructions = config.get(f"{prefix}_voice_instructions", "") or None

    if provider == "openai" or provider == "custom" or provider == "local-ai-server":
        if provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"
        return OpenAITTSModel(base_url, api_key, model_name, speed, voice_instructions)
    
    elif provider == "edge-tts":
        return EdgeTTSModel(model_name, speed)
    
    return None
