import base64
import json
from dataclasses import dataclass
from typing import Any, Iterable, override

import httpx
import speech_recognition as sr

from lib.Models import LLMError, OpenAIEmbeddingModel, OpenAILLMModel, OpenAIMultiModalSTTModel, STTModel, TTSModel
from lib.PluginBase import PluginBase, PluginManifest
from plugins.ProviderPluginHelpers import api_key as _shared_api_key, bool_setting, float_setting, number_field, paragraph as _paragraph, select_field, string_setting, textarea_field, text_field, toggle_field
from plugins.EdgeTTSPlugin import EDGE_TTS_PLUGIN_GUID


GOOGLE_AI_STUDIO_PLUGIN_GUID = "51f1df0c-479d-4f0f-a585-57c08d9e1901"
GOOGLE_AI_STUDIO_API_URL = "https://generativelanguage.googleapis.com/v1beta"
GOOGLE_LLM_MODEL = "gemini-3.5-flash-lite"
GOOGLE_AGENT_LLM_MODEL = "gemini-3.5-flash-lite"
GOOGLE_VLM_MODEL = "gemini-3.8-flash"
GOOGLE_STT_MODEL = "gemini-3.5-flash-lite"
GOOGLE_TRANSCRIBE_MODEL = "gemini-3.5-transcribe"
GOOGLE_TTS_MODEL = "gemini-3.8-flash-lite-tts"
GOOGLE_TTS_MODELS = [GOOGLE_TTS_MODEL, "gemini-3.8-flash-tts"]
GOOGLE_TTS_VOICE = "Kore"
GOOGLE_EMBEDDING_MODEL = "gemini-embedding-001"

@dataclass(frozen=True)
class GoogleModelCapabilities:
    efforts: tuple[str, ...]


# Gemini 2.5 access is restricted to existing users; previews are omitted.
# Source: https://ai.google.dev/gemini-api/docs/generate-content/thinking
GOOGLE_MODELS = {
    "gemini-3.5-flash-lite": GoogleModelCapabilities(("minimal", "low", "medium", "high")),
    "gemini-3.8-flash": GoogleModelCapabilities(("low", "medium", "high")),
}


def selected_model(settings: dict[str, Any], key: str, default: str) -> str:
    value = settings.get(key)
    return value if isinstance(value, str) and value in GOOGLE_MODELS else default


def api_key(settings: dict[str, Any], prefix: str) -> str:
    baseline = settings.get('legacy_shared_api_key')
    if isinstance(baseline, str):
        if settings.get('api_key') == baseline:
            return str(settings.get(f'{prefix}_api_key') or settings.get('api_key') or '-')
        return str(settings.get('api_key') or '-')
    return _shared_api_key(settings, prefix)


def selected_effort(value: Any, fallback: str, capabilities: GoogleModelCapabilities) -> str:
    if value == "default" or value in capabilities.efforts:
        return value
    return fallback if fallback in capabilities.efforts else capabilities.efforts[0]


def paragraph(content: str, key: str) -> dict[str, Any]:
    return {**_paragraph(content), "key": key}


def condition_field(key: str, setting_key: str, operator: str, value: Any,
                    fields: list[dict[str, Any]], *, default_show: bool = False) -> dict[str, Any]:
    return {"key": key, "type": "condition", "fields": fields,
            "condition": {"key": setting_key, "operator": operator, "value": value, "default_show": default_show}}


def language_fields(prefix: str, model: str, effort: str) -> list[dict[str, Any]]:
    model_key, effort_key = f"{prefix}_model", f"{prefix}_reasoning_effort"
    fields = [select_field(model_key, "Model", model, list(GOOGLE_MODELS))]
    for name, capabilities in GOOGLE_MODELS.items():
        default_effort = selected_effort(None, effort, capabilities)
        reasoning_field = select_field(effort_key, "Thinking Level", default_effort, ["default", *capabilities.efforts])
        reasoning_field["select_options"][0]["label"] = "Model default"
        options = [reasoning_field,
            condition_field(f"{prefix}_{name}_slow", effort_key, "eq", "high",
                            [paragraph("High thinking effort can delay the first response and increase billed output tokens.",
                                       f"{prefix}_{name}_slow_hint")]),
        ]
        if "minimal" in capabilities.efforts:
            options.append(condition_field(f"{prefix}_{name}_minimal", effort_key, "eq", "minimal",
                           [paragraph("Minimal thinking favors lower latency but does not completely disable reasoning.",
                                      f"{prefix}_{name}_minimal_hint")], default_show=default_effort == "minimal"))
        fields.append(condition_field(f"{prefix}_{name}_options", model_key, "eq", name, options,
                                      default_show=name == model))
    fields.extend([
        toggle_field(f"{prefix}_custom_temperature", "Customize temperature", False),
        condition_field(f"{prefix}_sampling", f"{prefix}_custom_temperature", "eq", True, [
            number_field(f"{prefix}_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
            condition_field(f"{prefix}_temperature_warning", f"{prefix}_temperature", "lt", 1.0,
                            [paragraph("Google recommends temperature 1.0. Lower values can cause looping or degraded reasoning.",
                                       f"{prefix}_temperature_hint")]),
        ]),
    ])
    return fields


class GoogleAIStudioLLMModel(OpenAILLMModel):
    def __init__(self, *args: Any, custom_temperature: bool = False, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.custom_temperature = custom_temperature

    @override
    def _prepare_request_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params.pop("reasoning_effort", None)
        if not self.custom_temperature:
            params.pop("temperature", None)
        if self.reasoning_effort and self.reasoning_effort != "default":
            params["extra_body"] = {"google": {"thinking_config": {"thinking_level": self.reasoning_effort}}}
        return params

    def _prepare_messages(self, messages: list[dict]) -> list[dict]:
        request_messages = super()._prepare_messages(messages)
        for message in request_messages:
            calls = message.get("tool_calls") or []
            for index, call in enumerate(calls):
                if not isinstance(call, dict):
                    if hasattr(call, "model_dump"):
                        call = call.model_dump()
                    elif hasattr(call, "dict"):
                        call = call.dict()
                    calls[index] = call
                if isinstance(call, dict):
                    signature = call.get("extra_content", {}).get("google", {}).get("thought_signature")
                    if not signature:
                        call["extra_content"] = {
                            "google": {"thought_signature": "skip_thought_signature_validator"}
                        }
        return request_messages


class GoogleAIStudioTranscribeModel(STTModel):
    def __init__(self, api_key: str, model_name: str):
        super().__init__(model_name, provider_name="google-ai-studio")
        self.client = httpx.Client(
            base_url=f"{GOOGLE_AI_STUDIO_API_URL.rstrip('/')}/",
            headers={"x-goog-api-key": api_key},
            timeout=60.0,
        )

    @staticmethod
    def _extract_transcript(payload: dict[str, Any]) -> str:
        segments: list[str] = []
        for output in payload.get("outputs", []):
            if output.get("type") == "text" and isinstance(output.get("text"), str):
                segments.append(output["text"])
        for candidate in payload.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text:
                    segments.append(text)
                transcription = part.get("audioTranscription") or part.get("audio_transcription")
                if isinstance(transcription, dict):
                    text = transcription.get("text")
                    if isinstance(text, str) and text:
                        segments.append(text)
        return "".join(segments).strip()

    @override
    def transcribe(self, audio: sr.AudioData) -> str:
        audio_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
        try:
            response = self.client.post(
                "interactions",
                json={
                    "model": self.model_name,
                    "input": [{"type": "audio", "mime_type": "audio/wav",
                               "data": base64.b64encode(audio_data).decode("ascii")}],
                    "store": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            transcript = self._extract_transcript(payload)
            if transcript:
                return transcript

            candidates = payload.get("candidates", [])
            finish_reason = candidates[0].get("finishReason") if candidates else None
            usage = payload.get("usageMetadata", {})
            output_tokens = usage.get("candidatesTokenCount", 0)
            raise LLMError(
                "STT Google AI Studio returned no transcript "
                f"(finish reason: {finish_reason or 'unknown'}, output tokens: {output_tokens})"
            )
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise LLMError(f"STT Google AI Studio HTTP {e.response.status_code}: {detail}", e)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"STT Google AI Studio error: {e}", e)


class GoogleAIStudioTTSModel(TTSModel):
    def __init__(self, api_key: str, model_name: str):
        super().__init__(model_name, provider_name="google-ai-studio")
        self.client = httpx.Client(
            base_url=f"{GOOGLE_AI_STUDIO_API_URL.rstrip('/')}/",
            headers={"x-goog-api-key": api_key},
            timeout=60.0,
        )

    def _iter_audio(self, response: httpx.Response) -> Iterable[bytes]:
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            event = json.loads(data)
            if isinstance(event, dict) and "error" in event:
                raise LLMError(f"TTS Google AI Studio stream error: {event['error']}")
            for candidate in event.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline_data = part.get("inlineData") or part.get("inline_data")
                    encoded_audio = inline_data.get("data") if isinstance(inline_data, dict) else None
                    if isinstance(encoded_audio, str) and encoded_audio:
                        yield base64.b64decode(encoded_audio, validate=True)

    @override
    def synthesize(self, text: str, voice: str) -> Iterable[bytes]:
        yield from self.synthesize_with_settings(text, {"voice": voice})

    @override
    def synthesize_with_settings(self, text: str, settings: dict[str, Any]) -> Iterable[bytes]:
        voice = str(settings.get("voice") or GOOGLE_TTS_VOICE)
        style = str(settings.get("instructions") or "").strip()
        text_part: dict[str, Any] = {"text": text}
        if style:
            text_part["speechMetadata"] = {"style": style}

        try:
            with self.client.stream(
                "POST",
                f"models/{self.model_name}:streamGenerateContent",
                params={"alt": "sse"},
                json={
                    "contents": [{"role": "user", "parts": [text_part]}],
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {"voice": voice}
                        },
                    },
                },
            ) as response:
                response.raise_for_status()
                yield from self._iter_audio(response)
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise LLMError(f"TTS Google AI Studio HTTP {e.response.status_code}: {detail}", e)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"TTS Google AI Studio error: {e}", e)


def _fields() -> list[dict[str, Any]]:
    return [
        text_field("api_key", "Google AI Studio API Key", "", hidden=True),
    ]


class GoogleAIStudioPlugin(PluginBase):
    settings_schema_version = 2

    @override
    def migrate_settings(self, settings: dict[str, Any], from_version: int) -> None:
        if from_version not in (0, 1):
            return
        if not settings.get('api_key'):
            for prefix in ('llm', 'agent_llm', 'vlm', 'stt', 'tts', 'embedding'):
                key = settings.get(f'{prefix}_api_key')
                if isinstance(key, str) and key:
                    settings['api_key'] = key
                    break
        if any(settings.get(f'{prefix}_api_key') and settings[f'{prefix}_api_key'] != settings.get('api_key')
               for prefix in ('llm', 'agent_llm', 'vlm', 'stt', 'tts', 'embedding')):
            settings.setdefault('legacy_shared_api_key', settings.get('api_key', ''))
        # Version 1 already has curated model settings. Version 2 only repairs
        # credentials imported by the original legacy-provider migration.
        if from_version == 1:
            return
        for prefix, default, effort in (
            ("llm", GOOGLE_LLM_MODEL, "minimal"), ("agent_llm", GOOGLE_AGENT_LLM_MODEL, "low"),
            ("vlm", GOOGLE_VLM_MODEL, "low"),
        ):
            key = f"{prefix}_model"
            if key in settings:
                settings[key] = selected_model(settings, key, default)
            reasoning_key = f"{prefix}_reasoning_effort"
            if reasoning_key in settings:
                model = selected_model(settings, key, default)
                settings[reasoning_key] = selected_effort(settings[reasoning_key], effort, GOOGLE_MODELS[model])
            if settings.get(f"{prefix}_temperature") not in (None, 1.0, "", "1", "1.0"):
                settings.setdefault(f"{prefix}_custom_temperature", True)
        if "stt_model" in settings and settings["stt_model"] not in (GOOGLE_STT_MODEL, GOOGLE_TRANSCRIBE_MODEL):
            settings["stt_model"] = GOOGLE_STT_MODEL
        if "tts_model" in settings and settings["tts_model"] not in GOOGLE_TTS_MODELS:
            settings["tts_model"] = GOOGLE_TTS_MODEL
        if "embedding_model" in settings:
            settings["embedding_model"] = GOOGLE_EMBEDDING_MODEL

    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        providers: list[dict[str, Any]] = []
        for provider_id, prefix, slot, title, model, reasoning in (
            ("llm", "llm", "llm", "Google AI Studio LLM", GOOGLE_LLM_MODEL, "minimal"),
            ("agent-llm", "agent_llm", "agent_llm", "Google AI Studio Agent LLM", GOOGLE_AGENT_LLM_MODEL, "low"),
            ("vlm", "vlm", "vision", "Google AI Studio Vision", GOOGLE_VLM_MODEL, "low"),
        ):
            providers.append({
                "kind": "vlm" if slot == "vision" else "llm", "id": provider_id, "label": "Google AI Studio", "slots": [slot],
                "settings_config": [{"key": prefix, "label": title, "fields": [
                    *_fields(), *language_fields(prefix, model, reasoning),
                ]}],
            })
        providers.extend([
            {
                "kind": "stt", "id": "stt", "label": "Google AI Studio", "slots": ["stt"],
                "settings_config": [{"key": "stt", "label": "Google AI Studio Speech-to-Text", "fields": [
                    *_fields(), select_field("stt_model", "Model", GOOGLE_STT_MODEL, [
                        GOOGLE_STT_MODEL, GOOGLE_TRANSCRIBE_MODEL,
                    ]),
                    condition_field("stt_multimodal", "stt_model", "eq", GOOGLE_STT_MODEL, [
                        text_field("stt_prompt", "Transcription Context", ""),
                        paragraph("Audio is sent to a multimodal model with transcription instructions.", "stt_multimodal_hint"),
                    ], default_show=True),
                    condition_field("stt_dedicated", "stt_model", "eq", GOOGLE_TRANSCRIBE_MODEL, [
                        paragraph("Uses Google's dedicated transcription model through the Interactions API.", "stt_dedicated_hint"),
                    ]),
                ]}],
            },
            {
                "kind": "tts", "id": "tts", "label": "Google AI Studio", "slots": ["tts"],
                "settings_config": [{"key": "tts", "label": "Google AI Studio Text-to-Speech", "fields": [
                    *_fields(), select_field("tts_model", "Model", GOOGLE_TTS_MODEL, GOOGLE_TTS_MODELS),
                ]}],
                "voice_settings_config": [{"key": "voice", "label": "Google AI Studio Voice", "fields": [
                    text_field("voice", "Voice", GOOGLE_TTS_VOICE),
                    textarea_field("instructions", "Voice Instructions", ""),
                    condition_field("voice_style_help", "instructions", "neq", "", [
                        paragraph("Describe delivery, emotion, accent, or pace. Spoken text is treated as a verbatim transcript.", "voice_style_hint"),
                    ]),
                ]}],
            },
            {
                "kind": "embedding", "id": "embedding", "label": "Google AI Studio", "slots": ["embedding"],
                "settings_config": [{"key": "embedding", "label": "Google AI Studio Embeddings", "fields": [
                    *_fields(), select_field("embedding_model", "Model", GOOGLE_EMBEDDING_MODEL, [GOOGLE_EMBEDDING_MODEL]),
                ]}],
            },
        ])
        providers[0]["api_key_detection"] = {
            "patterns": [r"^AIza[A-Za-z0-9_-]{35}$", r"^AQ[A-Za-z0-9_-]{30,}$"],
            "priority": 20,
            "setting_key": "api_key",
            "provider_selections": {
                "llm_provider": "llm", "agent_llm_provider": "agent-llm",
                "vision_provider": "vlm", "stt_provider": "stt",
                "tts_provider": f"plugin:{EDGE_TTS_PLUGIN_GUID}:tts",
                "embedding_provider": "embedding",
            },
        }
        self.model_providers = providers  # type: ignore[assignment]

    @override
    def create_model(self, provider_id: str, settings: dict[str, Any]):
        if provider_id in {"llm", "agent-llm", "vlm"}:
            prefix = "agent_llm" if provider_id == "agent-llm" else provider_id
            defaults = {
                "llm": (GOOGLE_LLM_MODEL, "minimal"),
                "agent_llm": (GOOGLE_AGENT_LLM_MODEL, "low"),
                "vlm": (GOOGLE_VLM_MODEL, "low"),
            }
            model, reasoning = defaults[prefix]
            model = selected_model(settings, f"{prefix}_model", model)
            return GoogleAIStudioLLMModel(
                GOOGLE_AI_STUDIO_API_URL, api_key(settings, prefix),
                model,
                float_setting(settings, f"{prefix}_temperature", 1.0),
                reasoning_effort=selected_effort(settings.get(f"{prefix}_reasoning_effort"), reasoning, GOOGLE_MODELS[model]),
                custom_temperature=bool_setting(settings, f"{prefix}_custom_temperature", False),
                provider_name="google-ai-studio",
            )
        if provider_id == "stt":
            model = string_setting(settings, "stt_model", GOOGLE_STT_MODEL)
            if model == GOOGLE_TRANSCRIBE_MODEL:
                return GoogleAIStudioTranscribeModel(api_key(settings, "stt"), model)
            model = GOOGLE_STT_MODEL
            return OpenAIMultiModalSTTModel(
                GOOGLE_AI_STUDIO_API_URL, api_key(settings, "stt"),
                model,
                str(settings.get("stt_prompt") or "") or None,
                provider_name="google-ai-studio",
            )
        if provider_id == "tts":
            model = settings.get("tts_model")
            return GoogleAIStudioTTSModel(
                api_key(settings, "tts"),
                model if model in GOOGLE_TTS_MODELS else GOOGLE_TTS_MODEL,
            )
        if provider_id == "embedding":
            return OpenAIEmbeddingModel(
                GOOGLE_AI_STUDIO_API_URL, api_key(settings, "embedding"),
                GOOGLE_EMBEDDING_MODEL,
            )
        raise ValueError(f"Unknown Google AI Studio model provider: {provider_id}")
