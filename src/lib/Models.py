from abc import ABC, abstractmethod
from typing import Any, List, Optional, Iterable
import io
import base64
import json
import speech_recognition as sr
import soundfile as sf
import numpy as np
from uuid import uuid4
from contextvars import ContextVar, copy_context
from dataclasses import replace
from time import perf_counter
from openai.types.audio.speech_create_params import SpeechCreateParams
from openai import OpenAI, APIStatusError
from openai.types.chat import ChatCompletion, ChatCompletionMessageFunctionToolCall, ChatCompletionMessageToolCall
from openai.types import CreateEmbeddingResponse
from .Logger import log, ModelUsageStats
from .ModelUsage import TranscriptionResult, SynthesisResult
from .Errors import ModelError, LLMError, error_kind


def _legacy_usage(model, **metadata) -> ModelUsageStats:
    """Only the legacy API bridge infers identity from model attributes."""
    def optional_string(name):
        try:
            value = getattr(model, name, None)
            return value if isinstance(value, str) else None
        except Exception:
            return None
    return ModelUsageStats.unknown(provider=optional_string("provider_name"),
                                   model_name=optional_string("model_name"), **metadata)

class LLMModel(ABC):
    model_name: str
    provider_name: str | None

    def __init__(self, model_name: str, provider_name: str | None = None):
        self.model_name = model_name
        self.provider_name = provider_name

    def generate_with_usage(self, *args, **kwargs):
        """Additive handler entrypoint: never replace a plugin's legacy generate()."""
        fallback = _legacy_usage(self)
        try:
            text, tools, usage = self.generate(*args, **kwargs)
            # Preserve provider-reported identity; fill only missing legacy fields.
            if usage.provider is None or usage.model_name is None:
                usage = replace(usage, provider=usage.provider or fallback.provider,
                                model_name=usage.model_name or fallback.model_name)
            return text, tools, usage
        except LLMError as exc:
            if exc.usage is None:
                exc.usage = fallback
            raise
        except Exception as exc:
            raise ModelError(str(exc), exc, usage=fallback) from exc

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


def _infer_schema_type(schema: dict[str, Any]) -> str | None:
    schema_type = schema.get("type")
    if isinstance(schema_type, str) and schema_type:
        return schema_type

    if isinstance(schema_type, list):
        for item in schema_type:
            if isinstance(item, str) and item and item != "null":
                return item

    for union_key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(union_key)
        if not isinstance(options, list):
            continue

        for option in options:
            option_schema = _model_dump_compatible(option)
            if not isinstance(option_schema, dict):
                continue

            inferred = _infer_schema_type(option_schema)
            if inferred and inferred != "null":
                return inferred

    properties = schema.get("properties")
    if isinstance(properties, dict):
        return "object"

    if "items" in schema:
        return "array"

    enum_values = schema.get("enum")
    if isinstance(enum_values, list):
        for value in enum_values:
            if value is None:
                continue
            if isinstance(value, bool):
                return "boolean"
            if isinstance(value, int) and not isinstance(value, bool):
                return "integer"
            if isinstance(value, float):
                return "number"
            if isinstance(value, str):
                return "string"

    default_value = schema.get("default")
    if default_value is not None:
        if isinstance(default_value, bool):
            return "boolean"
        if isinstance(default_value, int) and not isinstance(default_value, bool):
            return "integer"
        if isinstance(default_value, float):
            return "number"
        if isinstance(default_value, str):
            return "string"
        if isinstance(default_value, list):
            return "array"
        if isinstance(default_value, dict):
            return "object"

    if any(key in schema for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")):
        return "number"

    return None


def _normalize_tool_schema(schema: Any) -> Any:
    schema = _model_dump_compatible(schema)

    if isinstance(schema, list):
        return [_normalize_tool_schema(item) for item in schema]

    if not isinstance(schema, dict):
        return schema

    normalized = {key: _normalize_tool_schema(value) for key, value in schema.items()}

    inferred_type = _infer_schema_type(normalized)
    if inferred_type:
        normalized["type"] = inferred_type

    properties = normalized.get("properties")
    if isinstance(properties, dict):
        for value in properties.values():
            if isinstance(value, dict):
                value.setdefault("description", "")
                child_type = _infer_schema_type(value)
                if child_type:
                    value["type"] = child_type

    items = normalized.get("items")
    if isinstance(items, dict):
        items.setdefault("description", "")
        item_type = _infer_schema_type(items)
        if item_type:
            items["type"] = item_type

    return normalized


def _normalize_tools_for_chat_template(tools: list[dict]) -> list[dict[str, Any]]:
    normalized_tools: list[dict[str, Any]] = []
    for tool in tools:
        normalized_tool = _model_dump_compatible(tool)
        if not isinstance(normalized_tool, dict):
            continue
        normalized_tools.append(_normalize_tool_schema(normalized_tool))
    return normalized_tools

def _get_reasoning_usage(usage: Any) -> tuple[int | None, bool | None]:
    def count(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    input_tokens = count(getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", None)))
    output_tokens = count(getattr(usage, "output_tokens", getattr(usage, "completion_tokens", None)))
    total_tokens = count(getattr(usage, "total_tokens", None))
    for details_name in ("output_tokens_details", "completion_tokens_details"):
        details = getattr(usage, details_name, None)
        if details is None:
            continue

        reasoning_tokens = count(getattr(details, "reasoning_tokens", None))
        if reasoning_tokens is not None:
            included = None
            if input_tokens is not None and output_tokens is not None and total_tokens is not None:
                if total_tokens == input_tokens + output_tokens:
                    included = True
                elif total_tokens == input_tokens + output_tokens + reasoning_tokens:
                    included = False
            return reasoning_tokens, included
    if input_tokens is not None and output_tokens is not None and total_tokens is not None:
        difference = total_tokens - input_tokens - output_tokens
        if difference > 0:
            return difference, False
    # Equal totals do not prove zero hidden reasoning when the breakdown is absent.
    return None, None


def _get_reasoning_tokens(usage: Any) -> int | None:
    return _get_reasoning_usage(usage)[0]

class OpenAILLMModel(LLMModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, temperature: float, reasoning_effort: Optional[str] = None, extra_body: Optional[dict] = None, extra_headers: Optional[dict] = None, provider_name: str | None = None):
        super().__init__(model_name, provider_name=provider_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key, max_retries=4)
        self.base_url = base_url
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.extra_body = extra_body or {}
        self.extra_headers = extra_headers or {}

    def _prepare_messages(self, messages: List[dict]) -> List[dict]:
        return messages

    def _extract_response_text(self, content: Any) -> str | None:
        return content if isinstance(content, str) and content else None

    def _prepare_request_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Allow providers to enforce their model's parameter compatibility."""
        return params

    def generate(self, messages: List[dict], tools: Optional[List[dict]] = None, tool_choice: Optional[Any] = None) -> tuple[str | None, List[Any] | None, ModelUsageStats]:
        started_at = perf_counter()
        kwargs = {}
        request_messages = self._prepare_messages(messages)
        # Special handling for specific models or providers if needed
        if self.model_name in ['gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5.1']:
            kwargs["verbosity"] = "low"
                    
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": request_messages,
            "temperature": self.temperature,
            **self.extra_body,
            **kwargs
        }
        if tools:
            # LM Studio's embedded FunctionGemma template expects every schema node
            # to have a direct scalar `type`. Normalize tool schemas defensively so
            # optional or partially-specified fields do not crash prompt rendering.
            params["tools"] = _normalize_tools_for_chat_template(tools)
            if tool_choice:
                params["tool_choice"] = tool_choice
        
        if self.reasoning_effort and self.reasoning_effort not in ["disabled", "default", None, ""]:
             params["reasoning_effort"] = self.reasoning_effort

        if self.extra_body:
            params["extra_body"] = self.extra_body
            
        if self.extra_headers:
            params["extra_headers"] = self.extra_headers

        try:
            raw_response = self.client.chat.completions.with_raw_response.create(**self._prepare_request_params(params))  # pyright: ignore[reportCallIssue]
            completion = raw_response.parse()
            retry_attempts = raw_response.retries_taken
        except APIStatusError as e:
            log("debug", "LLM error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "LLM error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            log("error", f"LLM request failed for {self.provider_name or 'unknown'}/{self.model_name}: HTTP {e.status_code}: {e.body}")
            
            try:
                error: dict = e.body[0] if hasattr(e, 'body') and e.body and isinstance(e.body, list) else e.body # pyright: ignore[reportAssignmentType]
                message = error.get('error', {}).get('message', e.body if e.body else 'Unknown error')
            except:
                message = e.message
            
            raise LLMError(f'LLM {e.response.reason_phrase}: {message}', e)
        except Exception as e:
            raise LLMError(f'LLM Error: {str(e)}', e)

        if not isinstance(completion, ChatCompletion) or getattr(completion, 'error', None):
            log("debug", "LLM completion error:", completion)
            raise LLMError("LLM error: No valid completion received", kind="invalid_response")
        
        if not completion.choices:
            log("debug", "LLM completion has no choices:", completion)
            raise ModelError("LLM completion has no choices", kind="invalid_response")

        if not hasattr(completion.choices[0], 'message') or not completion.choices[0].message:
            log("debug", "LLM completion choice has no message:", completion)
            raise ModelError("LLM completion choice has no message", kind="invalid_response")

        usage_metadata = ModelUsageStats.unknown(
            provider=self.provider_name,
            model_name=getattr(completion, "model", None) or self.model_name,
            response_ms=(perf_counter() - started_at) * 1000,
            retry_attempts=retry_attempts,
        )
        if hasattr(completion, 'usage') and completion.usage:
            log("debug", f'LLM completion usage', completion.usage)
            usage_metadata.input_tokens = completion.usage.prompt_tokens
            usage_metadata.output_tokens = completion.usage.completion_tokens
            usage_metadata.total_tokens = completion.usage.total_tokens
            if hasattr(completion.usage, 'prompt_tokens_details') and completion.usage.prompt_tokens_details:
                usage_metadata.cached_tokens = getattr(completion.usage.prompt_tokens_details, 'cached_tokens', 0)
            usage_metadata.reasoning_tokens, usage_metadata.reasoning_tokens_in_output = _get_reasoning_usage(completion.usage)
        
        response_text = None
        if hasattr(completion.choices[0].message, 'content'):
            response_text = self._extract_response_text(completion.choices[0].message.content)
            if response_text is None:
                log("debug", "LLM completion no content:", completion)
        else:
            log("debug", f'LLM completion without text')
            response_text = None

        response_actions = None
        if hasattr(completion.choices[0].message, 'tool_calls'):
            response_actions = completion.choices[0].message.tool_calls

        if response_text is None and response_actions is None:
             return (None, None, usage_metadata)

        if response_text is not None:
            usage_metadata.output_chars = len(response_text)

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
        self.client = OpenAI(base_url=base_url, api_key=api_key, max_retries=4)
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

        for raw_tool in _normalize_tools_for_chat_template(tools):
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

    def _prepare_request_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Allow providers to enforce their model's parameter compatibility."""
        return params

    def generate(self, messages: List[dict], tools: Optional[List[dict]] = None, tool_choice: Optional[Any] = None) -> tuple[str | None, List[Any] | None, ModelUsageStats]:
        started_at = perf_counter()
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
            raw_response = self.client.responses.with_raw_response.create(**self._prepare_request_params(params))
            response = raw_response.parse()
            retry_attempts = raw_response.retries_taken
        except APIStatusError as e:
            log("debug", "LLM error request:", e.request.method, e.request.url, e.request.headers, e.request.read().decode('utf-8', errors='replace'))
            log("debug", "LLM error response:", e.response.status_code, e.response.headers, e.response.read().decode('utf-8', errors='replace'))
            log("error", f"LLM request failed for {self.provider_name or 'unknown'}/{self.model_name}: HTTP {e.status_code}: {e.body}")

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
            raise LLMError("LLM error: No valid response received", kind="invalid_response")

        usage_metadata = ModelUsageStats.unknown(
            provider=self.provider_name,
            model_name=getattr(response, "model", None) or self.model_name,
            response_ms=(perf_counter() - started_at) * 1000,
            retry_attempts=retry_attempts,
        )
        if hasattr(response, 'usage') and response.usage:
            log("debug", "LLM response usage", response.usage)
            usage_metadata.input_tokens = getattr(response.usage, "input_tokens", 0)
            usage_metadata.output_tokens = getattr(response.usage, "output_tokens", 0)
            usage_metadata.total_tokens = getattr(response.usage, "total_tokens", 0)
            if hasattr(response.usage, "input_tokens_details") and response.usage.input_tokens_details:
                usage_metadata.cached_tokens = getattr(response.usage.input_tokens_details, "cached_tokens", 0)
            usage_metadata.reasoning_tokens, usage_metadata.reasoning_tokens_in_output = _get_reasoning_usage(response.usage)

        response_text = getattr(response, "output_text", None) or None
        response_actions = self._extract_tool_calls(response)

        if response_text is None and response_actions is None:
            return (None, None, usage_metadata)

        if response_text is not None:
            usage_metadata.output_chars = len(response_text)

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
    provider_name: str | None

    def __init__(self, model_name: str, provider_name: str | None = None):
        self.model_name = model_name
        self.provider_name = provider_name

    @abstractmethod
    def transcribe(self, audio: sr.AudioData) -> str:
        pass

    def transcribe_with_usage(self, audio: sr.AudioData) -> TranscriptionResult:
        """Legacy bridge; plugins can override to report resolved identity/usage."""
        usage = _legacy_usage(self)
        started = perf_counter()
        try:
            text = self.transcribe(audio)
            if not isinstance(text, str):
                raise ModelError("Provider returned an invalid transcription", kind="invalid_response", usage=usage)
            usage.response_ms = (perf_counter() - started) * 1000
            return TranscriptionResult(text, usage)
        except LLMError as exc:
            if exc.usage is None:
                exc.usage = usage
            raise
        except Exception as exc:
            raise ModelError(str(exc), exc, usage=usage) from exc

class OpenAISTTModel(STTModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, language: Optional[str] = None, prompt: Optional[str] = None, provider_name: str | None = None):
        super().__init__(model_name, provider_name=provider_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.language = language
        self.prompt = prompt

    def transcribe_with_usage(self, audio: sr.AudioData) -> TranscriptionResult:
        try:
            result = super().transcribe_with_usage(audio)
            if hasattr(self, "language"):
                result.usage.input_language = self.language or "auto"
            return result
        except LLMError as exc:
            if exc.usage and hasattr(self, "language"):
                exc.usage.input_language = self.language or "auto"
            raise

    def _prepare_request_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return params

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
                "language": self.language if self.language else None,
            }
            if self.prompt:
                kwargs["prompt"] = self.prompt

            transcription = self.client.audio.transcriptions.create(**self._prepare_request_params(kwargs))
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
    def __init__(self, base_url: str, api_key: str, model_name: str, prompt: Optional[str] = None, provider_name: str | None = None):
        super().__init__(model_name, provider_name=provider_name)
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
                        (f"Additional transcription context: {self.prompt}\n" if self.prompt else "") +
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

class TTSModel(ABC):
    model_name: str
    provider_name: str | None

    def __init__(self, model_name: str, provider_name: str | None = None):
        self.model_name = model_name
        self.provider_name = provider_name

    @abstractmethod
    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        pass

    def synthesize_with_settings(self, text: str, settings: dict[str, Any]) -> Iterable[bytes]:
        """Synthesize with character-scoped provider settings while preserving legacy models."""
        return self.synthesize(text, str(settings.get("voice") or ""))

    def synthesis_usage(self, settings: dict[str, Any]) -> ModelUsageStats:
        """Override when the provider resolves defaults or synthesis languages."""
        return _legacy_usage(self, voice_name=str(settings.get("voice") or "") or None)

    def synthesize_voice_with_usage(self, text: str, voice: str) -> SynthesisResult:
        """Preserve the old voice-only dispatch when character settings are absent."""
        if type(self).synthesize_with_usage is not TTSModel.synthesize_with_usage:
            return self.synthesize_with_usage(text, {"voice": voice})
        usage = self.synthesis_usage({"voice": voice})
        return self._synthesis_result(usage, lambda: self.synthesize(text, voice))

    def synthesize_with_usage(self, text: str, settings: dict[str, Any]) -> SynthesisResult:
        usage = self.synthesis_usage(settings)
        return self._synthesis_result(usage, lambda: self.synthesize_with_settings(text, settings))

    def _synthesis_result(self, usage: ModelUsageStats, create_stream) -> SynthesisResult:
        def audio():
            started = perf_counter()
            stream = None
            received_audio = False
            try:
                stream = iter(create_stream())
                for chunk in stream:
                    received_audio = received_audio or bool(chunk)
                    if usage.time_to_first_byte_ms is None:
                        usage.time_to_first_byte_ms = (perf_counter() - started) * 1000
                    yield chunk
                if not received_audio and usage.is_provider_operation:
                    raise ModelError("Provider returned no audio", kind="invalid_response", usage=usage)
                usage.response_ms = (perf_counter() - started) * 1000
            except LLMError as exc:
                if exc.usage is None:
                    exc.usage = usage
                raise
            except Exception as exc:
                raise ModelError(str(exc), exc, usage=usage) from exc
            finally:
                close = getattr(stream, "close", None)
                if close:
                    close()
        return SynthesisResult(audio(), usage)


def generate_with_usage(model: LLMModel, context: str, prompt_usage: Any, **kwargs):
    """One caller-owned terminal event, including failures, for a logical LLM call."""
    from .Logger import log_llm_usage
    started = perf_counter()
    try:
        text, tools, usage = model.generate_with_usage(**kwargs) if isinstance(model, LLMModel) else model.generate(**kwargs)
    except Exception as exc:
        usage = exc.usage if isinstance(exc, LLMError) and exc.usage else ModelUsageStats.unknown()
        log_llm_usage(context, usage, prompt_usage, status="error", error_kind=error_kind(exc),
                      operation_ms=(perf_counter() - started) * 1000)
        raise
    log_llm_usage(context, usage, prompt_usage, response_text=text,
                  operation_ms=(perf_counter() - started) * 1000)
    return text, tools, usage

_INSTRUCTIONS_UNSET = object()


class OpenAITTSModel(TTSModel):
    def __init__(self, base_url: str, api_key: str, model_name: str, speed: float = 1.0, voice_instructions: str | None = None, provider_name: str | None = None):
        super().__init__(model_name, provider_name=provider_name)
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.speed = speed
        self._voice_instruction_context = ContextVar("tts_voice_instructions", default=_INSTRUCTIONS_UNSET)
        self.voice_instructions = voice_instructions

    @property
    def voice_instructions(self) -> str | None:
        variable = getattr(self, "_voice_instruction_context", None)
        value = variable.get() if variable is not None else _INSTRUCTIONS_UNSET
        return self.__dict__.get("voice_instructions") if value is _INSTRUCTIONS_UNSET else value

    @voice_instructions.setter
    def voice_instructions(self, value: str | None) -> None:
        variable = getattr(self, "_voice_instruction_context", None)
        if variable is not None and variable.get() is not _INSTRUCTIONS_UNSET:
            variable.set(value)
        else:
            self.__dict__["voice_instructions"] = value

    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        yield from self._synthesize(text, voice, self.voice_instructions)

    def _synthesize(self, text: str, voice: str, instructions: str | None) -> Iterable[bytes]:
        try:
            kwargs: SpeechCreateParams = {
                "model": self.model_name,
                "voice": voice, # pyright: ignore[reportArgumentType]
                "input": text,
                "response_format": "pcm",
                "speed": self.speed
            }
            if instructions and self.model_name == "gpt-4o-mini-tts":
                kwargs["instructions"] = instructions
            
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

    def synthesize_with_settings(self, text: str, settings: dict[str, Any]) -> Iterable[bytes]:
        instructions = settings.get("instructions")
        # Drive every next()/close() in its own context so legacy synthesize()
        # overrides still dispatch dynamically, without mutating shared defaults
        # or leaking one request's instructions into another interleaved stream.
        variable = getattr(self, "_voice_instruction_context", None)
        if variable is None:
            variable = self._voice_instruction_context = ContextVar("tts_voice_instructions", default=_INSTRUCTIONS_UNSET)
        context = copy_context()
        context.run(variable.set, str(instructions) if instructions else None)
        stream = context.run(lambda: iter(self.synthesize(text, str(settings.get("voice") or ""))))
        try:
            while True:
                try:
                    chunk = context.run(next, stream)
                except StopIteration:
                    return
                yield chunk
        finally:
            close = getattr(stream, "close", None)
            if close:
                context.run(close)
