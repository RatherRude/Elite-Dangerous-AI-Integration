from typing import Any, override

from lib.Models import (
    OpenAIEmbeddingModel,
    OpenAIResponsesLLMModel,
    OpenAISTTModel,
    OpenAITTSModel,
)
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginSettingDefinitions import ModelProviderDefinition
from plugins.ProviderPluginHelpers import (
    api_key,
    float_setting,
    number_field,
    select_field,
    string_setting,
    text_field,
)
from plugins.EdgeTTSPlugin import EDGE_TTS_PLUGIN_GUID


OPENAI_PLUGIN_GUID = "7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"
OPENAI_API_URL = "https://api.openai.com/v1"
OPENAI_LLM_MODEL = "gpt-5.4-nano"
OPENAI_AGENT_LLM_MODEL = "gpt-5.4-mini"
OPENAI_VLM_MODEL = "gpt-5.4-nano"
OPENAI_STT_MODEL = "gpt-4o-mini-transcribe"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


def _account_fields(prefix: str) -> list[dict[str, Any]]:
    return [
        text_field("api_key", "OpenAI API Key", "", hidden=True),
        text_field(f"{prefix}_api_key", "Override API Key", "", hidden=True),
    ]


def _llm_definition(
    provider_id: str,
    prefix: str,
    slot: str,
    label: str,
    model: str,
    reasoning: str,
) -> dict[str, Any]:
    return {
        "kind": "llm",
        "id": provider_id,
        "label": "OpenAI",
        "slots": [slot],
        "settings_config": [{
            "key": prefix,
            "label": label,
            "fields": [
                *_account_fields(prefix),
                text_field(f"{prefix}_model", "Model", model),
                number_field(f"{prefix}_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
                select_field(f"{prefix}_reasoning_effort", "Reasoning Effort", reasoning, ["default", "none", "minimal", "low", "medium", "high"]),
            ],
        }],
    }


class OpenAIPlugin(PluginBase):
    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        providers: list[dict[str, Any]] = [
            _llm_definition("llm", "llm", "llm", "OpenAI LLM", OPENAI_LLM_MODEL, "none"),
            _llm_definition("agent-llm", "agent_llm", "agent_llm", "OpenAI Agent LLM", OPENAI_AGENT_LLM_MODEL, "low"),
            {
                "kind": "vlm", "id": "vlm", "label": "OpenAI", "slots": ["vision"],
                "settings_config": [{"key": "vlm", "label": "OpenAI Vision", "fields": [
                    *_account_fields("vlm"),
                    text_field("vlm_model", "Model", OPENAI_VLM_MODEL),
                    number_field("vlm_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
                    select_field("vlm_reasoning_effort", "Reasoning Effort", "none", ["default", "none", "minimal", "low", "medium", "high"]),
                ]}],
            },
            {
                "kind": "stt", "id": "stt", "label": "OpenAI", "slots": ["stt"],
                "settings_config": [{"key": "stt", "label": "OpenAI Speech-to-Text", "fields": [
                    *_account_fields("stt"),
                    text_field("stt_model", "Model", OPENAI_STT_MODEL),
                    text_field("stt_language", "Language", ""),
                    text_field("stt_prompt", "Prompt", ""),
                ]}],
            },
            {
                "kind": "tts", "id": "tts", "label": "OpenAI", "slots": ["tts"],
                "settings_config": [{"key": "tts", "label": "OpenAI Text-to-Speech", "fields": [
                    *_account_fields("tts"),
                    text_field("tts_model", "Model", OPENAI_TTS_MODEL),
                ]}],
            },
            {
                "kind": "embedding", "id": "embedding", "label": "OpenAI", "slots": ["embedding"],
                "settings_config": [{"key": "embedding", "label": "OpenAI Embeddings", "fields": [
                    *_account_fields("embedding"),
                    text_field("embedding_model", "Model", OPENAI_EMBEDDING_MODEL),
                ]}],
            },
        ]
        providers[0]["api_key_detection"] = {
            "patterns": [r"^sk-(?!or-v1-)[A-Za-z0-9_-]{20,}$"],
            "priority": 10,
            "setting_key": "api_key",
            "provider_selections": {
                "llm_provider": "llm",
                "agent_llm_provider": "agent-llm",
                "vision_provider": "vlm",
                "stt_provider": "stt",
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
                "llm": (OPENAI_LLM_MODEL, "none"),
                "agent_llm": (OPENAI_AGENT_LLM_MODEL, "low"),
                "vlm": (OPENAI_VLM_MODEL, "none"),
            }
            model, reasoning = defaults[prefix]
            return OpenAIResponsesLLMModel(
                base_url=OPENAI_API_URL,
                api_key=api_key(settings, prefix),
                model_name=string_setting(settings, f"{prefix}_model", model),
                temperature=float_setting(settings, f"{prefix}_temperature", 1.0),
                reasoning_effort=string_setting(settings, f"{prefix}_reasoning_effort", reasoning),
                provider_name="openai",
            )
        if provider_id == "stt":
            return OpenAISTTModel(
                OPENAI_API_URL, api_key(settings, "stt"),
                string_setting(settings, "stt_model", OPENAI_STT_MODEL),
                str(settings.get("stt_language") or "") or None,
                str(settings.get("stt_prompt") or "") or None,
                provider_name="openai",
            )
        if provider_id == "tts":
            return OpenAITTSModel(
                OPENAI_API_URL, api_key(settings, "tts"),
                string_setting(settings, "tts_model", OPENAI_TTS_MODEL),
                provider_name="openai",
            )
        if provider_id == "embedding":
            return OpenAIEmbeddingModel(
                OPENAI_API_URL, api_key(settings, "embedding"),
                string_setting(settings, "embedding_model", OPENAI_EMBEDDING_MODEL),
            )
        raise ValueError(f"Unknown OpenAI model provider: {provider_id}")
