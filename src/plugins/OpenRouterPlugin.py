from typing import Any, override

from lib.PluginBase import PluginBase, PluginManifest
from plugins.ProviderPluginHelpers import ToolToggleOpenAILLMModel, api_key, bool_setting, float_setting, number_field, paragraph, select_field, string_setting, text_field, toggle_field
from plugins.EdgeTTSPlugin import EDGE_TTS_PLUGIN_GUID


OPENROUTER_PLUGIN_GUID = "a9d9fb7a-18df-4602-bf7d-53f3486f7d18"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


class OpenRouterPlugin(PluginBase):
    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        providers: list[dict[str, Any]] = []
        for provider_id, prefix, slot, title in (
            ("llm", "llm", "llm", "OpenRouter LLM"),
            ("agent-llm", "agent_llm", "agent_llm", "OpenRouter Agent LLM"),
        ):
            providers.append({
                "kind": "llm", "id": provider_id, "label": "OpenRouter", "slots": [slot],
                "settings_config": [{"key": prefix, "label": title, "fields": [
                    text_field("api_key", "OpenRouter API Key", "", hidden=True),
                    text_field(f"{prefix}_api_key", "Override API Key", "", hidden=True),
                    text_field(f"{prefix}_endpoint", "Endpoint", OPENROUTER_API_URL),
                    text_field(f"{prefix}_model", "Model", OPENROUTER_MODEL),
                    number_field(f"{prefix}_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01),
                    select_field(f"{prefix}_reasoning_effort", "Reasoning Effort", "default", ["default", "none", "minimal", "low", "medium", "high"]),
                    toggle_field(f"{prefix}_tools_enabled", "Enable Tool Use", True),
                    paragraph("Disable tool use if the selected routed model rejects tool definitions."),
                ]}],
            })
        providers[0]["api_key_detection"] = {
            "patterns": [r"^sk-or-v1-[0-9a-fA-F]{64}$"],
            "priority": 100,
            "setting_key": "api_key",
            "provider_selections": {
                "llm_provider": "llm", "agent_llm_provider": "agent-llm",
                "vision_provider": "none", "stt_provider": "none",
                "tts_provider": f"plugin:{EDGE_TTS_PLUGIN_GUID}:tts",
                "embedding_provider": "none",
            },
        }
        self.model_providers = providers  # type: ignore[assignment]

    @override
    def create_model(self, provider_id: str, settings: dict[str, Any]):
        if provider_id not in {"llm", "agent-llm"}:
            raise ValueError(f"Unknown OpenRouter model provider: {provider_id}")
        prefix = "agent_llm" if provider_id == "agent-llm" else "llm"
        return ToolToggleOpenAILLMModel(
            string_setting(settings, f"{prefix}_endpoint", OPENROUTER_API_URL),
            api_key(settings, prefix),
            string_setting(settings, f"{prefix}_model", OPENROUTER_MODEL),
            float_setting(settings, f"{prefix}_temperature", 1.0),
            reasoning_effort=string_setting(settings, f"{prefix}_reasoning_effort", "default"),
            provider_name="openrouter",
            tools_enabled=bool_setting(settings, f"{prefix}_tools_enabled", True),
        )
