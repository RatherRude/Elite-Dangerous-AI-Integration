from dataclasses import dataclass
from typing import Any, override

from lib.Models import (
    OpenAIEmbeddingModel,
    OpenAIResponsesLLMModel,
    OpenAISTTModel,
    OpenAITTSModel,
)
from lib.PluginBase import PluginBase, PluginManifest
from plugins.ProviderPluginHelpers import (
    api_key as _shared_api_key,
    float_setting,
    number_field,
    paragraph as _paragraph,
    select_field,
    string_setting,
    textarea_field,
    text_field,
)
from plugins.EdgeTTSPlugin import EDGE_TTS_PLUGIN_GUID


OPENAI_PLUGIN_GUID = "7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"
OPENAI_API_URL = "https://api.openai.com/v1"
OPENAI_LLM_MODEL = "gpt-6-luna"
OPENAI_AGENT_LLM_MODEL = "gpt-5.4-mini"
OPENAI_VLM_MODEL = "gpt-6-luna"
OPENAI_STT_MODEL = "gpt-transcribe"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_MODELS = [OPENAI_EMBEDDING_MODEL, "text-embedding-3-large"]

@dataclass(frozen=True)
class OpenAIModelCapabilities:
    efforts: tuple[str, ...]
    default_effort: str
    temperature: bool = True
    fast: bool = True


# Curated, non-deprecated language/vision models. Prices are not cached here.
# Source: https://developers.openai.com/api/docs/models
_REASONING = ("none", "low", "medium", "high", "xhigh")
_EXTENDED = (*_REASONING, "max")
OPENAI_MODELS = {
    "gpt-6-luna": OpenAIModelCapabilities(_EXTENDED, "medium"),
    "gpt-6-sol": OpenAIModelCapabilities(_EXTENDED, "medium"),
    "gpt-6.1-sol": OpenAIModelCapabilities(_EXTENDED[1:], "medium", temperature=False),
    "gpt-6-astra": OpenAIModelCapabilities(_EXTENDED[1:], "medium", temperature=False),
    "gpt-5.4-mini": OpenAIModelCapabilities(_REASONING, "none", temperature=False),
    "gpt-5.4": OpenAIModelCapabilities(_REASONING, "none"),
}


def selected_model(settings: dict[str, Any], key: str, default: str) -> str:
    value = settings.get(key)
    return value if isinstance(value, str) and value in OPENAI_MODELS else default


def api_key(settings: dict[str, Any], prefix: str) -> str:
    baseline = settings.get('legacy_shared_api_key')
    if isinstance(baseline, str):
        if settings.get('api_key') == baseline:
            return str(settings.get(f'{prefix}_api_key') or settings.get('api_key') or '-')
        # Editing the shared key explicitly replaces imported role overrides.
        return str(settings.get('api_key') or '-')
    return _shared_api_key(settings, prefix)


def selected_effort(value: Any, fallback: str, capabilities: OpenAIModelCapabilities) -> str:
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
    fields = [select_field(model_key, "Model", model, list(OPENAI_MODELS))]
    for name, capabilities in OPENAI_MODELS.items():
        default_effort = selected_effort(None, effort, capabilities)
        reasoning_field = select_field(effort_key, "Reasoning Effort", default_effort, ["default", *capabilities.efforts])
        reasoning_field["select_options"][0]["label"] = "Model default"
        options = [reasoning_field]
        options.append(condition_field(
            f"{prefix}_{name}_slow", effort_key, "in", ["high", "xhigh", "max"],
            [paragraph("Higher reasoning effort can delay the first response and increase billed output tokens.",
                       f"{prefix}_{name}_slow_hint")], default_show=default_effort in {"high", "xhigh", "max"},
        ))
        if capabilities.temperature:
            allowed = ["none"] + (["default"] if capabilities.default_effort == "none" else [])
            show_temperature = default_effort == "none"
            options.extend([
                condition_field(f"{prefix}_{name}_sampling", effort_key, "in", allowed,
                                [number_field(f"{prefix}_temperature", "Temperature", 1.0, 0.0, 2.0, 0.01)],
                                default_show=show_temperature),
                condition_field(f"{prefix}_{name}_no_sampling", effort_key, "not_in", allowed,
                                [paragraph("Temperature is unavailable while reasoning is enabled.",
                                           f"{prefix}_{name}_sampling_hint")], default_show=not show_temperature),
            ])
        fields.append(condition_field(f"{prefix}_{name}_options", model_key, "eq", name, options,
                                      default_show=name == model))
    tier = select_field(f"{prefix}_service_tier", "Processing Tier", "default", ["default", "fast", "auto"])
    for option in tier["select_options"]:
        option["label"] = {"default": "Standard", "fast": "Fast (higher cost)", "auto": "Project default"}[option["value"]]
    fields.extend([
        select_field(f"{prefix}_verbosity", "Verbosity", "low", ["default", "low", "medium", "high"]),
        condition_field(f"{prefix}_verbose", f"{prefix}_verbosity", "eq", "high",
                        [paragraph("Longer answers take longer to generate and speak, and use more output tokens.",
                                   f"{prefix}_verbosity_hint")]),
        tier,
        condition_field(f"{prefix}_fast", f"{prefix}_service_tier", "eq", "fast", [
            paragraph('Fast processing reduces latency at a higher token price. Availability and rates depend on the model. '
                      'See <a href="https://openai.com/api-priority-processing/" target="_blank" rel="noopener noreferrer">'
                      'OpenAI pricing</a> for current rates.', f"{prefix}_fast_hint"),
        ]),
    ])
    return fields


class OpenAIProviderLLMModel(OpenAIResponsesLLMModel):
    def __init__(self, *args: Any, verbosity: str = "low", service_tier: str = "default", **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.verbosity = verbosity
        self.service_tier = service_tier

    @override
    def _prepare_request_params(self, params: dict[str, Any]) -> dict[str, Any]:
        capabilities = OPENAI_MODELS[self.model_name]
        effort = self.reasoning_effort
        effective = capabilities.default_effort if effort == "default" else effort
        if not capabilities.temperature or effective != "none":
            params.pop("temperature", None)
        params.pop("reasoning", None)
        if effort != "default":
            params["reasoning"] = {"effort": effort}
        params.pop("text", None)
        if self.verbosity in {"low", "medium", "high"}:
            params["text"] = {"verbosity": self.verbosity}
        if self.service_tier in {"default", "auto"} or (self.service_tier == "fast" and capabilities.fast):
            params["service_tier"] = self.service_tier
        return params


class OpenAITranscribeModel(OpenAISTTModel):
    @override
    def _prepare_request_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params.pop("language", None)
        if self.language:
            params["languages"] = [code.strip() for code in self.language.split(",") if code.strip()]
        return params


def _account_fields() -> list[dict[str, Any]]:
    return [
        text_field("api_key", "OpenAI API Key", "", hidden=True),
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
        "kind": "vlm" if slot == "vision" else "llm",
        "id": provider_id,
        "label": "OpenAI",
        "slots": [slot],
        "settings_config": [{
            "key": prefix,
            "label": label,
            "fields": [
                *_account_fields(),
                *language_fields(prefix, model, reasoning),
            ],
        }],
    }


class OpenAIPlugin(PluginBase):
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
            ("llm", OPENAI_LLM_MODEL, "none"), ("agent_llm", OPENAI_AGENT_LLM_MODEL, "low"),
            ("vlm", OPENAI_VLM_MODEL, "none"),
        ):
            key = f"{prefix}_model"
            if key in settings:
                settings[key] = selected_model(settings, key, default)
            reasoning_key = f"{prefix}_reasoning_effort"
            if reasoning_key in settings:
                model = selected_model(settings, key, default)
                settings[reasoning_key] = selected_effort(settings[reasoning_key], effort, OPENAI_MODELS[model])
        if "stt_model" in settings:
            settings["stt_model"] = OPENAI_STT_MODEL
        if "tts_model" in settings:
            settings["tts_model"] = OPENAI_TTS_MODEL
        if "embedding_model" in settings and settings["embedding_model"] not in OPENAI_EMBEDDING_MODELS:
            settings["embedding_model"] = OPENAI_EMBEDDING_MODEL

    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        providers: list[dict[str, Any]] = [
            _llm_definition("llm", "llm", "llm", "OpenAI LLM", OPENAI_LLM_MODEL, "none"),
            _llm_definition("agent-llm", "agent_llm", "agent_llm", "OpenAI Agent LLM", OPENAI_AGENT_LLM_MODEL, "low"),
            _llm_definition("vlm", "vlm", "vision", "OpenAI Vision", OPENAI_VLM_MODEL, "none"),
            {
                "kind": "stt", "id": "stt", "label": "OpenAI", "slots": ["stt"],
                "settings_config": [{"key": "stt", "label": "OpenAI Speech-to-Text", "fields": [
                    *_account_fields(),
                    select_field("stt_model", "Model", OPENAI_STT_MODEL, [OPENAI_STT_MODEL]),
                    text_field("stt_language", "Languages (comma-separated codes)", ""),
                    text_field("stt_prompt", "Prompt", ""),
                ]}],
            },
            {
                "kind": "tts", "id": "tts", "label": "OpenAI", "slots": ["tts"],
                "settings_config": [{"key": "tts", "label": "OpenAI Text-to-Speech", "fields": [
                    *_account_fields(),
                    select_field("tts_model", "Model", OPENAI_TTS_MODEL, [OPENAI_TTS_MODEL]),
                ]}],
                "voice_settings_config": [{"key": "voice", "label": "OpenAI Voice", "fields": [
                    select_field("voice", "Voice", "nova", [
                        "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse", "marin", "cedar",
                    ]),
                    condition_field("tts_instructions", "tts_model", "eq", OPENAI_TTS_MODEL,
                                    [textarea_field("instructions", "Voice Instructions", "")], default_show=True),
                ]}],
            },
            {
                "kind": "embedding", "id": "embedding", "label": "OpenAI", "slots": ["embedding"],
                "settings_config": [{"key": "embedding", "label": "OpenAI Embeddings", "fields": [
                    *_account_fields(),
                    select_field("embedding_model", "Model", OPENAI_EMBEDDING_MODEL,
                                 OPENAI_EMBEDDING_MODELS),
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
            model = selected_model(settings, f"{prefix}_model", model)
            return OpenAIProviderLLMModel(
                base_url=OPENAI_API_URL,
                api_key=api_key(settings, prefix),
                model_name=model,
                temperature=float_setting(settings, f"{prefix}_temperature", 1.0),
                reasoning_effort=selected_effort(settings.get(f"{prefix}_reasoning_effort"), reasoning, OPENAI_MODELS[model]),
                verbosity=string_setting(settings, f"{prefix}_verbosity", "low"),
                service_tier=string_setting(settings, f"{prefix}_service_tier", "default"),
                provider_name="openai",
            )
        if provider_id == "stt":
            return OpenAITranscribeModel(
                OPENAI_API_URL, api_key(settings, "stt"),
                OPENAI_STT_MODEL,
                str(settings.get("stt_language") or "") or None,
                str(settings.get("stt_prompt") or "") or None,
                provider_name="openai",
            )
        if provider_id == "tts":
            return OpenAITTSModel(
                OPENAI_API_URL, api_key(settings, "tts"),
                OPENAI_TTS_MODEL,
                provider_name="openai",
            )
        if provider_id == "embedding":
            model = settings.get("embedding_model")
            return OpenAIEmbeddingModel(
                OPENAI_API_URL, api_key(settings, "embedding"),
                model if model in OPENAI_EMBEDDING_MODELS else OPENAI_EMBEDDING_MODEL,
            )
        raise ValueError(f"Unknown OpenAI model provider: {provider_id}")
