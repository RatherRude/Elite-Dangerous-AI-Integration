from typing import Any, override

from lib.Models import OpenAISTTModel
from lib.PluginBase import PluginBase, PluginManifest
from plugins.ProviderPluginHelpers import api_key, paragraph, select_field, string_setting, text_field


GROQ_PLUGIN_GUID = "43a2a263-b899-40f6-b06d-560dfdfd8cc6"
GROQ_API_URL = "https://api.groq.com/openai/v1"
GROQ_STT_MODEL = "whisper-large-v3-turbo"
GROQ_STT_MODELS = [GROQ_STT_MODEL, "whisper-large-v3"]


class GroqPlugin(PluginBase):
    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        self.model_providers = [{  # type: ignore[assignment]
            "kind": "stt", "id": "stt", "label": "Groq", "slots": ["stt"],
            "settings_config": [{"key": "stt", "label": "Groq Speech-to-Text", "fields": [
                text_field("api_key", "Groq API Key", "", hidden=True),
                select_field("stt_model", "Model", GROQ_STT_MODEL, GROQ_STT_MODELS),
                paragraph("whisper-large-v3-turbo is faster and cheaper; whisper-large-v3 is more accurate."),
                text_field("stt_language", "Language (ISO-639-1 code, e.g. fr)", ""),
                text_field("stt_prompt", "Prompt", ""),
            ]}],
        }]

    @override
    def create_model(self, provider_id: str, settings: dict[str, Any]):
        if provider_id != "stt":
            raise ValueError(f"Unknown Groq model provider: {provider_id}")
        return OpenAISTTModel(
            GROQ_API_URL,
            api_key(settings, "stt"),
            string_setting(settings, "stt_model", GROQ_STT_MODEL),
            str(settings.get("stt_language") or "").strip() or None,
            str(settings.get("stt_prompt") or "") or None,
            provider_name="groq",
        )
