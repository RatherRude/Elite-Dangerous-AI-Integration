from typing import Any, override

from lib.Models import (
    OpenAIEmbeddingModel,
    OpenAILLMModel,
    OpenAIMultiModalSTTModel,
    OpenAISTTModel,
    OpenAITTSModel,
)
from lib.PluginBase import PluginBase, PluginManifest
from plugins.ProviderPluginHelpers import ToolToggleOpenAILLMModel, bool_setting, float_setting, number_field, paragraph, select_field, string_setting, textarea_field, text_field, toggle_field


OPENAI_COMPATIBLE_PLUGIN_GUID = "64a79751-078d-48c6-9540-193afde6c469"
CUSTOM_API_URL = "https://api.openai.com/v1"
LOCAL_API_URL = "http://127.0.0.1:8080"


def _base_fields(prefix: str, endpoint: str, model: str, authenticated: bool) -> list[dict[str, Any]]:
    fields = [
        text_field(f"{prefix}_endpoint", "Endpoint", endpoint),
    ]
    if authenticated:
        fields.append(text_field(f"{prefix}_api_key", "API Key", "", hidden=True))
    fields.append(text_field(f"{prefix}_model", "Model", model))
    return fields


def _definition(
    kind: str,
    provider_id: str,
    slot: str,
    label: str,
    prefix: str,
    endpoint: str,
    model: str,
    *,
    llm: bool = False,
    tools: bool = False,
    stt: bool = False,
    multimodal_stt: bool = False,
    authenticated: bool = True,
) -> dict[str, Any]:
    fields = _base_fields(prefix, endpoint, model, authenticated)
    if llm:
        fields.extend([
            number_field(f"{prefix}_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
            select_field(f"{prefix}_reasoning_effort", "Reasoning Effort", "default", ["default", "none", "minimal", "low", "medium", "high"]),
            paragraph("Available features depend on the connected server and selected model."),
        ])
        if tools:
            fields.insert(-1, toggle_field(f"{prefix}_tools_enabled", "Enable Tool Use", True))
    if stt:
        fields.extend([
            text_field(f"{prefix}_language", "Language", ""),
            text_field(f"{prefix}_prompt", "Prompt", ""),
        ])
    elif multimodal_stt:
        fields.extend([
            text_field(f"{prefix}_prompt", "Prompt", ""),
            paragraph("Audio is sent to the selected multimodal model as conversation input."),
        ])
    definition: dict[str, Any] = {
        "kind": kind,
        "id": provider_id,
        "label": label,
        "slots": [slot],
        "settings_config": [{"key": prefix, "label": label, "fields": fields}],
    }
    if kind == "tts":
        definition["voice_settings_config"] = [{
            "key": "voice",
            "label": f"{label} Voice",
            "fields": [
                text_field("voice", "Voice Name or Reference Path", "nova"),
                textarea_field("instructions", "Voice Instructions", ""),
            ],
        }]
    return definition


class OpenAICompatiblePlugin(PluginBase):
    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        providers: list[dict[str, Any]] = []
        for profile, label, endpoint in (
            ("custom", "Custom OpenAI-compatible", CUSTOM_API_URL),
            ("local", "Local AI Server", LOCAL_API_URL),
        ):
            models = {
                "llm": "gpt-4.1-mini",
                "agent_llm": "gpt-4.1-mini",
                "vlm": "gpt-4o-mini",
                "stt": "whisper-1",
                "tts": "gpt-4o-mini-tts" if profile == "custom" else "tts-1",
                "embedding": "text-embedding-3-small",
            }
            providers.extend([
                _definition("llm", f"{profile}-llm", "llm", label, f"{profile}_llm", endpoint, models["llm"], llm=True, tools=profile == "custom", authenticated=profile == "custom"),
                _definition("llm", f"{profile}-agent-llm", "agent_llm", label, f"{profile}_agent_llm", endpoint, models["agent_llm"], llm=True, tools=profile == "custom", authenticated=profile == "custom"),
                _definition("vlm", f"{profile}-vlm", "vision", label, f"{profile}_vlm", endpoint, models["vlm"], llm=True, authenticated=profile == "custom"),
                _definition("stt", f"{profile}-stt", "stt", label, f"{profile}_stt", endpoint, models["stt"], stt=True, authenticated=profile == "custom"),
                _definition("tts", f"{profile}-tts", "tts", label, f"{profile}_tts", endpoint, models["tts"], authenticated=profile == "custom"),
                _definition("embedding", f"{profile}-embedding", "embedding", label, f"{profile}_embedding", endpoint, models["embedding"], authenticated=profile == "custom"),
            ])
        providers.append(_definition(
            "stt", "custom-multimodal-stt", "stt", "Custom Multi-Modal",
            "custom_multimodal_stt", CUSTOM_API_URL, "gpt-4o-mini-audio-preview", multimodal_stt=True,
        ))
        self.model_providers = providers  # type: ignore[assignment]

    @override
    def create_model(self, provider_id: str, settings: dict[str, Any]):
        branches = {
            "custom-llm": ("llm", "custom_llm", "gpt-4.1-mini"),
            "custom-agent-llm": ("llm", "custom_agent_llm", "gpt-4.1-mini"),
            "custom-vlm": ("llm", "custom_vlm", "gpt-4o-mini"),
            "custom-stt": ("stt", "custom_stt", "whisper-1"),
            "custom-multimodal-stt": ("multimodal-stt", "custom_multimodal_stt", "gpt-4o-mini-audio-preview"),
            "custom-tts": ("tts", "custom_tts", "gpt-4o-mini-tts"),
            "custom-embedding": ("embedding", "custom_embedding", "text-embedding-3-small"),
            "local-llm": ("llm", "local_llm", "gpt-4.1-mini"),
            "local-agent-llm": ("llm", "local_agent_llm", "gpt-4.1-mini"),
            "local-vlm": ("llm", "local_vlm", "gpt-4o-mini"),
            "local-stt": ("stt", "local_stt", "whisper-1"),
            "local-tts": ("tts", "local_tts", "tts-1"),
            "local-embedding": ("embedding", "local_embedding", "text-embedding-3-small"),
        }
        if provider_id not in branches:
            raise ValueError(f"Unknown OpenAI-compatible model provider: {provider_id}")
        kind, prefix, default_model = branches[provider_id]
        default_endpoint = LOCAL_API_URL if prefix.startswith("local_") else CUSTOM_API_URL
        endpoint = string_setting(settings, f"{prefix}_endpoint", default_endpoint)
        key = str(settings.get(f"{prefix}_api_key") or "-")
        model = string_setting(settings, f"{prefix}_model", default_model)
        provider_name = "local-ai-server" if prefix.startswith("local_") else "custom"

        if kind == "llm":
            model_type = ToolToggleOpenAILLMModel if prefix.startswith("custom_") else OpenAILLMModel
            model_kwargs: dict[str, Any] = {
                "reasoning_effort": string_setting(settings, f"{prefix}_reasoning_effort", "default"),
                "provider_name": provider_name,
            }
            if model_type is ToolToggleOpenAILLMModel:
                model_kwargs["tools_enabled"] = bool_setting(settings, f"{prefix}_tools_enabled", True)
            return model_type(
                endpoint, key, model,
                float_setting(settings, f"{prefix}_temperature", 1.0),
                **model_kwargs,
            )
        if kind == "stt":
            return OpenAISTTModel(
                endpoint, key, model,
                str(settings.get(f"{prefix}_language") or "") or None,
                str(settings.get(f"{prefix}_prompt") or "") or None,
                provider_name=provider_name,
            )
        if kind == "multimodal-stt":
            return OpenAIMultiModalSTTModel(
                endpoint, key, model,
                str(settings.get(f"{prefix}_prompt") or "") or None,
                provider_name=provider_name,
            )
        if kind == "tts":
            return OpenAITTSModel(endpoint, key, model, provider_name=provider_name)
        return OpenAIEmbeddingModel(endpoint, key, model)
