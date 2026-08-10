import base64
import json
from typing import Any, Iterable, override

import httpx
import numpy as np

from lib.Models import (
    LLMError,
    OpenAIEmbeddingModel,
    OpenAILLMModel,
    OpenAISTTModel,
    TTSModel,
)
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginSettingDefinitions import ModelProviderDefinition


MISTRAL_API_URL = "https://api.mistral.ai/v1"
MISTRAL_PLUGIN_GUID = "d17f20f6-2514-4a1f-9e54-2a3c089f5c2b"
MISTRAL_LLM_MODEL = "mistral-small-latest"
MISTRAL_VLM_MODEL = MISTRAL_LLM_MODEL
MISTRAL_EMBEDDING_MODEL = "mistral-embed"
MISTRAL_STT_MODEL = "voxtral-mini-latest"
MISTRAL_TTS_MODEL = "voxtral-mini-tts-2603"
MISTRAL_TTS_VOICE = "en_paul_neutral"


def _text_field(
    key: str,
    label: str,
    default_value: str,
    *,
    hidden: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": "text",
        "readonly": False,
        "placeholder": None,
        "default_value": default_value,
        "max_length": None,
        "min_length": None,
        "hidden": hidden,
    }


def _number_field(
    key: str,
    label: str,
    default_value: float,
    minimum: float,
    maximum: float,
    step: float,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": "number",
        "readonly": False,
        "placeholder": None,
        "default_value": default_value,
        "min_value": minimum,
        "max_value": maximum,
        "step": step,
    }


def _account_fields() -> list[dict[str, Any]]:
    return [
        _text_field("api_key", "Mistral API Key", "", hidden=True),
        _text_field("endpoint", "Endpoint", MISTRAL_API_URL),
    ]


def _model_dump_compatible(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _extract_visible_text(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content or None

    content = _model_dump_compatible(content)
    if isinstance(content, (list, tuple)):
        parts = [_extract_visible_text(part) for part in content]
        text = "".join(part for part in parts if part)
        return text or None
    if not isinstance(content, dict):
        return None
    if str(content.get("type", "")).lower() in {"thinking", "reasoning"}:
        return None

    text = content.get("text")
    if isinstance(text, str):
        return text or None
    return _extract_visible_text(content.get("content"))


def _json_compatible(value: Any) -> Any:
    value = _model_dump_compatible(value)
    if isinstance(value, dict):
        return {key: _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return value


def _contains_hidden_reasoning(content: Any) -> bool:
    content = _model_dump_compatible(content)
    if isinstance(content, (list, tuple)):
        return any(_contains_hidden_reasoning(part) for part in content)
    if not isinstance(content, dict):
        return False
    return str(content.get("type", "")).lower() in {"thinking", "reasoning"}


def _normalize_tool_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if _contains_hidden_reasoning(content):
        return _extract_visible_text(content) or ""

    content = _json_compatible(content)
    try:
        return json.dumps(content)
    except TypeError:
        return str(content)


class MistralLLMModel(OpenAILLMModel):
    @override
    def _prepare_messages(self, messages: list[dict]) -> list[dict]:
        return [
            {
                **message,
                "content": _normalize_tool_content(message.get("content")),
            }
            if message.get("role") == "tool"
            else {**message}
            for message in messages
        ]

    @override
    def _extract_response_text(self, content: Any) -> str | None:
        return _extract_visible_text(content)


class MistralTTSModel(TTSModel):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        default_voice: str,
    ):
        super().__init__(model_name, provider_name="mistral")
        self.default_voice = default_voice
        self.client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    def _iter_audio_deltas(self, response: httpx.Response) -> Iterable[bytes]:
        data_lines: list[str] = []
        for line in response.iter_lines():
            if line == "":
                if not data_lines:
                    continue
                data = "\n".join(data_lines)
                data_lines.clear()
                if data == "[DONE]":
                    return
                event = json.loads(data)
                event_type = event.get("type") if isinstance(event, dict) else None
                if event_type == "speech.audio.done":
                    return
                if event_type == "speech.audio.delta":
                    encoded_audio = event.get("audio_data")
                    if not isinstance(encoded_audio, str) or not encoded_audio:
                        raise LLMError("TTS Mistral audio event did not contain audio data")
                    yield base64.b64decode(encoded_audio, validate=True)
                elif isinstance(event_type, str) and "error" in event_type:
                    raise LLMError(f"TTS Mistral stream error: {event}")
                continue

            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

        if data_lines:
            event = json.loads("\n".join(data_lines))
            if isinstance(event, dict) and event.get("type") == "speech.audio.delta":
                encoded_audio = event.get("audio_data")
                if not isinstance(encoded_audio, str) or not encoded_audio:
                    raise LLMError("TTS Mistral audio event did not contain audio data")
                yield base64.b64decode(encoded_audio, validate=True)

    def _to_pcm16(self, audio_deltas: Iterable[bytes]) -> Iterable[bytes]:
        float32_buffer = bytearray()
        pcm16_buffer = bytearray()

        for delta in audio_deltas:
            float32_buffer.extend(delta)
            complete_bytes = len(float32_buffer) - (len(float32_buffer) % 4)
            if complete_bytes == 0:
                continue

            samples = np.frombuffer(bytes(float32_buffer[:complete_bytes]), dtype="<f4")
            del float32_buffer[:complete_bytes]
            samples = np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0)
            pcm16_buffer.extend(
                (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
            )
            while len(pcm16_buffer) >= 1024:
                yield bytes(pcm16_buffer[:1024])
                del pcm16_buffer[:1024]

        if float32_buffer:
            raise LLMError("TTS Mistral returned invalid float32 PCM data")
        if pcm16_buffer:
            yield bytes(pcm16_buffer)

    @override
    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        try:
            with self.client.stream(
                "POST",
                "audio/speech",
                headers={"Accept": "text/event-stream"},
                json={
                    "model": self.model_name,
                    "voice": self.default_voice,
                    "input": text,
                    "response_format": "pcm",
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                yield from self._to_pcm16(self._iter_audio_deltas(response))
        except LLMError:
            raise
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise LLMError(f"TTS Mistral HTTP {e.response.status_code}: {detail}", e)
        except Exception as e:
            raise LLMError(f"TTS Mistral error: {e}", e)


class MistralPlugin(PluginBase):
    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)

        self.model_providers: list[ModelProviderDefinition] = [
            {
                "kind": "llm",
                "id": "llm",
                "label": "Mistral",
                "settings_config": [{
                    "key": "llm",
                    "label": "Mistral LLM",
                    "fields": [
                        *_account_fields(),
                        _text_field("llm_model", "Model", MISTRAL_LLM_MODEL),
                        _number_field("llm_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
                    ],  # type: ignore[typeddict-item]
                }],
            },
            {
                "kind": "stt",
                "id": "stt",
                "label": "Mistral",
                "settings_config": [{
                    "key": "stt",
                    "label": "Mistral Speech-to-Text",
                    "fields": [
                        *_account_fields(),
                        _text_field("stt_model", "Model", MISTRAL_STT_MODEL),
                        _text_field("stt_language", "Language", ""),
                        _text_field("stt_prompt", "Prompt", ""),
                    ],  # type: ignore[typeddict-item]
                }],
            },
            {
                "kind": "vlm",
                "id": "vlm",
                "label": "Mistral",
                "settings_config": [{
                    "key": "vlm",
                    "label": "Mistral Vision",
                    "fields": [
                        *_account_fields(),
                        _text_field("vlm_model", "Model", MISTRAL_VLM_MODEL),
                        _number_field("vlm_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
                    ],  # type: ignore[typeddict-item]
                }],
            },
            {
                "kind": "embedding",
                "id": "embedding",
                "label": "Mistral",
                "settings_config": [{
                    "key": "embedding",
                    "label": "Mistral Embeddings",
                    "fields": [
                        *_account_fields(),
                        _text_field(
                            "embedding_model",
                            "Model",
                            MISTRAL_EMBEDDING_MODEL,
                        ),
                    ],  # type: ignore[typeddict-item]
                }],
            },
            {
                "kind": "tts",
                "id": "tts",
                "label": "Mistral",
                "settings_config": [{
                    "key": "tts",
                    "label": "Mistral Text-to-Speech",
                    "fields": [
                        *_account_fields(),
                        _text_field("tts_model", "Model", MISTRAL_TTS_MODEL),
                        _text_field("tts_voice", "Voice", MISTRAL_TTS_VOICE),
                    ],  # type: ignore[typeddict-item]
                }],
            },
        ]

    @override
    def create_model(self, provider_id: str, settings: dict[str, Any]):
        endpoint = str(settings.get("endpoint") or MISTRAL_API_URL)
        api_key = str(settings.get("api_key") or "-")

        if provider_id == "llm":
            return MistralLLMModel(
                base_url=endpoint,
                api_key=api_key,
                model_name=str(settings.get("llm_model") or MISTRAL_LLM_MODEL),
                temperature=float(settings.get("llm_temperature", 1.0)),
                reasoning_effort="none",
                provider_name="mistral",
            )
        if provider_id == "stt":
            return OpenAISTTModel(
                base_url=endpoint,
                api_key=api_key,
                model_name=str(settings.get("stt_model") or MISTRAL_STT_MODEL),
                language=str(settings.get("stt_language") or "") or None,
                prompt=str(settings.get("stt_prompt") or "") or None,
                provider_name="mistral",
            )
        if provider_id == "vlm":
            return MistralLLMModel(
                base_url=endpoint,
                api_key=api_key,
                model_name=str(settings.get("vlm_model") or MISTRAL_VLM_MODEL),
                temperature=float(settings.get("vlm_temperature", 1.0)),
                reasoning_effort="none",
                provider_name="mistral",
            )
        if provider_id == "embedding":
            return OpenAIEmbeddingModel(
                base_url=endpoint,
                api_key=api_key,
                model_name=str(
                    settings.get("embedding_model") or MISTRAL_EMBEDDING_MODEL
                ),
            )
        if provider_id == "tts":
            return MistralTTSModel(
                base_url=endpoint,
                api_key=api_key,
                model_name=str(settings.get("tts_model") or MISTRAL_TTS_MODEL),
                default_voice=str(settings.get("tts_voice") or MISTRAL_TTS_VOICE),
            )
        raise ValueError(f"Unknown Mistral model provider: {provider_id}")
