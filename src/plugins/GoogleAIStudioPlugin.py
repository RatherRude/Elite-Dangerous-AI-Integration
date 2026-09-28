from typing import Any, override

from lib.Models import OpenAIEmbeddingModel, OpenAILLMModel, OpenAIMultiModalSTTModel
from lib.PluginBase import PluginBase, PluginManifest
from plugins.ProviderPluginHelpers import api_key, float_setting, number_field, paragraph, select_field, string_setting, text_field
from plugins.EdgeTTSPlugin import EDGE_TTS_PLUGIN_GUID


GOOGLE_AI_STUDIO_PLUGIN_GUID = "51f1df0c-479d-4f0f-a585-57c08d9e1901"
GOOGLE_AI_STUDIO_API_URL = "https://generativelanguage.googleapis.com/v1beta"
GOOGLE_LLM_MODEL = "gemini-3.1-flash-lite-preview"
GOOGLE_AGENT_LLM_MODEL = "gemini-3.1-flash-lite-preview"
GOOGLE_VLM_MODEL = "gemini-2.5-flash"
GOOGLE_STT_MODEL = "gemini-2.5-flash-lite"
GOOGLE_EMBEDDING_MODEL = "gemini-embedding-001"


class GoogleAIStudioLLMModel(OpenAILLMModel):
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


def _fields(prefix: str) -> list[dict[str, Any]]:
    return [
        text_field("api_key", "Google AI Studio API Key", "", hidden=True),
        text_field(f"{prefix}_api_key", "Override API Key", "", hidden=True),
        text_field(f"{prefix}_endpoint", "Endpoint", GOOGLE_AI_STUDIO_API_URL),
    ]


class GoogleAIStudioPlugin(PluginBase):
    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        providers: list[dict[str, Any]] = []
        for provider_id, prefix, slot, title, model, reasoning in (
            ("llm", "llm", "llm", "Google AI Studio LLM", GOOGLE_LLM_MODEL, "none"),
            ("agent-llm", "agent_llm", "agent_llm", "Google AI Studio Agent LLM", GOOGLE_AGENT_LLM_MODEL, "low"),
        ):
            providers.append({
                "kind": "llm", "id": provider_id, "label": "Google AI Studio", "slots": [slot],
                "settings_config": [{"key": prefix, "label": title, "fields": [
                    *_fields(prefix), text_field(f"{prefix}_model", "Model", model),
                    number_field(f"{prefix}_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
                    select_field(f"{prefix}_reasoning_effort", "Reasoning Effort", reasoning, ["default", "none", "minimal", "low", "medium", "high"]),
                ]}],
            })
        providers.extend([
            {
                "kind": "vlm", "id": "vlm", "label": "Google AI Studio", "slots": ["vision"],
                "settings_config": [{"key": "vlm", "label": "Google AI Studio Vision", "fields": [
                    *_fields("vlm"), text_field("vlm_model", "Model", GOOGLE_VLM_MODEL),
                    number_field("vlm_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
                    select_field("vlm_reasoning_effort", "Reasoning Effort", "none", ["default", "none", "minimal", "low", "medium", "high"]),
                ]}],
            },
            {
                "kind": "stt", "id": "stt", "label": "Google AI Studio", "slots": ["stt"],
                "settings_config": [{"key": "stt", "label": "Google AI Studio Speech-to-Text", "fields": [
                    *_fields("stt"), text_field("stt_model", "Model", GOOGLE_STT_MODEL),
                    text_field("stt_prompt", "Prompt", ""),
                    paragraph("Audio is sent to the selected Gemini model as multimodal conversation input."),
                ]}],
            },
            {
                "kind": "embedding", "id": "embedding", "label": "Google AI Studio", "slots": ["embedding"],
                "settings_config": [{"key": "embedding", "label": "Google AI Studio Embeddings", "fields": [
                    *_fields("embedding"), text_field("embedding_model", "Model", GOOGLE_EMBEDDING_MODEL),
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
                "llm": (GOOGLE_LLM_MODEL, "none"),
                "agent_llm": (GOOGLE_AGENT_LLM_MODEL, "low"),
                "vlm": (GOOGLE_VLM_MODEL, "none"),
            }
            model, reasoning = defaults[prefix]
            return GoogleAIStudioLLMModel(
                string_setting(settings, f"{prefix}_endpoint", GOOGLE_AI_STUDIO_API_URL), api_key(settings, prefix),
                string_setting(settings, f"{prefix}_model", model),
                float_setting(settings, f"{prefix}_temperature", 1.0),
                reasoning_effort=string_setting(settings, f"{prefix}_reasoning_effort", reasoning),
                provider_name="google-ai-studio",
            )
        if provider_id == "stt":
            return OpenAIMultiModalSTTModel(
                string_setting(settings, "stt_endpoint", GOOGLE_AI_STUDIO_API_URL), api_key(settings, "stt"),
                string_setting(settings, "stt_model", GOOGLE_STT_MODEL),
                str(settings.get("stt_prompt") or "") or None,
                provider_name="google-ai-studio",
            )
        if provider_id == "embedding":
            return OpenAIEmbeddingModel(
                string_setting(settings, "embedding_endpoint", GOOGLE_AI_STUDIO_API_URL), api_key(settings, "embedding"),
                string_setting(settings, "embedding_model", GOOGLE_EMBEDDING_MODEL),
            )
        raise ValueError(f"Unknown Google AI Studio model provider: {provider_id}")
