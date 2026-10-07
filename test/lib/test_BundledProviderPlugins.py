import base64
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
import speech_recognition as sr
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lib.Models import (
    OpenAIEmbeddingModel,
    OpenAILLMModel,
    OpenAIMultiModalSTTModel,
    OpenAIResponsesLLMModel,
    OpenAISTTModel,
    OpenAITTSModel,
)
from lib.PluginBase import PluginManifest
from lib.PluginSettingDefinitions import resolve_voice_settings, settings_fields
from plugins.EdgeTTSPlugin import EDGE_TTS_PLUGIN_GUID, EdgeTTSModel, EdgeTTSPlugin
from plugins.GoogleAIStudioPlugin import (
    GOOGLE_AI_STUDIO_API_URL,
    GOOGLE_AI_STUDIO_PLUGIN_GUID,
    GOOGLE_STT_MODEL,
    GOOGLE_TRANSCRIBE_MODEL,
    GoogleAIStudioLLMModel,
    GoogleAIStudioPlugin,
    GoogleAIStudioTTSModel,
    GoogleAIStudioTranscribeModel,
)
from plugins.MistralPlugin import MISTRAL_API_URL, MISTRAL_PLUGIN_GUID, MistralPlugin
from plugins.OpenAICompatiblePlugin import OPENAI_COMPATIBLE_PLUGIN_GUID, OpenAICompatiblePlugin
from plugins.OpenAIPlugin import OPENAI_API_URL, OPENAI_PLUGIN_GUID, OpenAIPlugin
from plugins.OpenRouterPlugin import OPENROUTER_API_URL, OPENROUTER_PLUGIN_GUID, OpenRouterPlugin
from plugins.ProviderPluginHelpers import ToolToggleOpenAILLMModel, api_key


def manifest(guid: str, name: str) -> PluginManifest:
    return PluginManifest(json.dumps({
        "guid": guid,
        "name": name,
        "author": "tests",
        "version": "1.0.0",
        "repository": "",
    }))


def provider_ids(plugin: Any) -> set[str]:
    return {provider["id"] for provider in plugin.model_providers or []}


def setting_keys(plugin: Any) -> set[str]:
    return {
        field["key"]
        for provider in plugin.model_providers or []
        for grid in provider["settings_config"]
        for field in settings_fields(grid["fields"])
        if field["type"] not in {"paragraph", "error", "button"}
    }


def voice_setting_keys(plugin: Any, provider_id: str) -> set[str]:
    provider = next(provider for provider in plugin.model_providers or [] if provider["id"] == provider_id)
    return {
        field["key"]
        for grid in provider.get("voice_settings_config", [])
        for field in settings_fields(grid["fields"])
        if field["type"] not in {"paragraph", "error", "button"}
    }


def test_bundled_tts_providers_define_character_scoped_voice_settings() -> None:
    assert voice_setting_keys(OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI")), "tts") == {
        "voice", "instructions",
    }
    assert voice_setting_keys(EdgeTTSPlugin(manifest(EDGE_TTS_PLUGIN_GUID, "Edge")), "tts") == {"voice"}
    assert voice_setting_keys(MistralPlugin(manifest(MISTRAL_PLUGIN_GUID, "Mistral")), "tts") == {"voice"}
    assert voice_setting_keys(GoogleAIStudioPlugin(manifest(GOOGLE_AI_STUDIO_PLUGIN_GUID, "Google")), "tts") == {
        "voice", "instructions",
    }
    compatible = OpenAICompatiblePlugin(manifest(OPENAI_COMPATIBLE_PLUGIN_GUID, "Compatible"))
    assert voice_setting_keys(compatible, "custom-tts") == {"voice", "instructions"}
    assert voice_setting_keys(compatible, "local-tts") == {"voice", "instructions"}


def test_fixed_providers_do_not_expose_or_accept_endpoint_overrides() -> None:
    fixed_providers = (
        (OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI")), "llm_endpoint", OPENAI_API_URL),
        (GoogleAIStudioPlugin(manifest(GOOGLE_AI_STUDIO_PLUGIN_GUID, "Google")), "llm_endpoint", GOOGLE_AI_STUDIO_API_URL),
        (OpenRouterPlugin(manifest(OPENROUTER_PLUGIN_GUID, "OpenRouter")), "llm_endpoint", OPENROUTER_API_URL),
        (MistralPlugin(manifest(MISTRAL_PLUGIN_GUID, "Mistral")), "endpoint", MISTRAL_API_URL),
    )

    for plugin, stale_key, expected_endpoint in fixed_providers:
        assert not any(key == "endpoint" or key.endswith("_endpoint") for key in setting_keys(plugin))
        model = plugin.create_model("llm", {stale_key: "https://invalid.example/v1"})
        assert str(model.client.base_url).rstrip("/") == expected_endpoint.rstrip("/")


def test_shared_key_providers_expose_one_api_key_field() -> None:
    plugins = (
        OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI")),
        GoogleAIStudioPlugin(manifest(GOOGLE_AI_STUDIO_PLUGIN_GUID, "Google")),
        OpenRouterPlugin(manifest(OPENROUTER_PLUGIN_GUID, "OpenRouter")),
    )

    for plugin in plugins:
        for provider in plugin.model_providers or []:
            api_key_fields = [
                field["key"]
                for grid in provider["settings_config"]
                for field in grid["fields"]
                if field.get("key", "").endswith("api_key")
            ]
            assert api_key_fields == ["api_key"]


def test_shared_api_key_precedes_legacy_role_override() -> None:
    assert api_key({"api_key": "shared", "stt_api_key": "legacy"}, "stt") == "shared"
    assert api_key({"stt_api_key": "legacy"}, "stt") == "legacy"


def test_openai_compatible_endpoints_remain_configurable() -> None:
    plugin = OpenAICompatiblePlugin(manifest(OPENAI_COMPATIBLE_PLUGIN_GUID, "Compatible"))
    assert {"custom_llm_endpoint", "local_llm_endpoint"} <= setting_keys(plugin)

    model = plugin.create_model("custom-llm", {"custom_llm_endpoint": "https://example.test/v1"})
    assert str(model.client.base_url) == "https://example.test/v1/"


def test_openai_provider_definitions_and_models() -> None:
    plugin = OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI"))
    assert provider_ids(plugin) == {"llm", "agent-llm", "vlm", "stt", "tts", "embedding"}
    assert isinstance(plugin.create_model("llm", {}), OpenAIResponsesLLMModel)
    assert isinstance(plugin.create_model("agent-llm", {}), OpenAIResponsesLLMModel)
    assert isinstance(plugin.create_model("stt", {}), OpenAISTTModel)
    assert isinstance(plugin.create_model("tts", {}), OpenAITTSModel)
    assert isinstance(plugin.create_model("embedding", {}), OpenAIEmbeddingModel)


def test_google_provider_definitions_and_models() -> None:
    plugin = GoogleAIStudioPlugin(manifest(GOOGLE_AI_STUDIO_PLUGIN_GUID, "Google"))
    assert provider_ids(plugin) == {"llm", "agent-llm", "vlm", "stt", "tts", "embedding"}
    assert isinstance(plugin.create_model("llm", {}), GoogleAIStudioLLMModel)
    assert isinstance(plugin.create_model("stt", {}), OpenAIMultiModalSTTModel)
    assert plugin.create_model("stt", {}).model_name == GOOGLE_STT_MODEL
    assert isinstance(
        plugin.create_model("stt", {"stt_model": GOOGLE_TRANSCRIBE_MODEL}),
        GoogleAIStudioTranscribeModel,
    )
    assert isinstance(plugin.create_model("tts", {}), GoogleAIStudioTTSModel)
    assert isinstance(plugin.create_model("embedding", {}), OpenAIEmbeddingModel)

    detection = plugin.model_providers[0]["api_key_detection"]["provider_selections"]
    assert detection["tts_provider"] == f"plugin:{EDGE_TTS_PLUGIN_GUID}:tts"


def test_google_transcribe_uses_interactions() -> None:
    model = GoogleAIStudioTranscribeModel("test-key", GOOGLE_TRANSCRIBE_MODEL)

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        assert request.url.path.endswith("/interactions")
        payload = json.loads(request.content)
        assert payload["model"] == GOOGLE_TRANSCRIBE_MODEL
        audio_part = payload["input"][0]
        assert audio_part["type"] == "audio"
        assert audio_part["mime_type"] == "audio/wav"
        assert base64.b64decode(audio_part["data"]).startswith(b"RIFF")
        return httpx.Response(200, json={
            "outputs": [{"type": "text", "text": "Landing gear deployed."}]
        })

    model.client = httpx.Client(
        base_url=f"{GOOGLE_AI_STUDIO_API_URL}/",
        headers={"x-goog-api-key": "test-key"},
        transport=httpx.MockTransport(handle),
    )
    audio = sr.AudioData(b"\x00\x00" * 160, 16000, 2)

    assert model.transcribe(audio) == "Landing gear deployed."


def test_google_transcribe_extracts_standard_text_parts() -> None:
    assert GoogleAIStudioTranscribeModel._extract_transcript({
        "candidates": [{"content": {"parts": [{"text": "Docking request granted."}]}}]
    }) == "Docking request granted."


def test_google_tts_streams_pcm_and_voice_settings() -> None:
    model = GoogleAIStudioTTSModel("test-key", "gemini-3.8-flash-lite-tts")
    first_chunk = b"\x01\x02\x03\x04"
    second_chunk = b"\x05\x06"

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models/gemini-3.8-flash-lite-tts:streamGenerateContent")
        assert request.url.params["alt"] == "sse"
        payload = json.loads(request.content)
        assert payload["contents"][0]["parts"][0] == {
            "text": "Frame shift drive charging.",
            "speechMetadata": {"style": "calm and precise"},
        }
        assert payload["generationConfig"]["speechConfig"]["voiceConfig"] == {"voice": "Kore"}
        events = [
            {"candidates": [{"content": {"parts": [{"inlineData": {
                "mimeType": "audio/l16", "data": base64.b64encode(first_chunk).decode("ascii")
            }}]}}]},
            {"candidates": [{"content": {"parts": [{"inlineData": {
                "mimeType": "audio/l16", "data": base64.b64encode(second_chunk).decode("ascii")
            }}]}}]},
        ]
        content = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
        return httpx.Response(200, text=content, headers={"content-type": "text/event-stream"})

    model.client = httpx.Client(
        base_url=f"{GOOGLE_AI_STUDIO_API_URL}/",
        headers={"x-goog-api-key": "test-key"},
        transport=httpx.MockTransport(handle),
    )

    chunks = list(model.synthesize_with_settings(
        "Frame shift drive charging.",
        {"voice": "Kore", "instructions": "calm and precise"},
    ))

    assert chunks == [first_chunk, second_chunk]


def test_openrouter_slots_and_models_are_independent() -> None:
    plugin = OpenRouterPlugin(manifest(OPENROUTER_PLUGIN_GUID, "OpenRouter"))
    providers = {provider["id"]: provider for provider in plugin.model_providers or []}
    assert providers["llm"]["slots"] == ["llm"]
    assert providers["agent-llm"]["slots"] == ["agent_llm"]
    settings = {"llm_model": "main", "agent_llm_model": "agent"}
    main = plugin.create_model("llm", settings)
    agent = plugin.create_model("agent-llm", settings)
    assert isinstance(main, OpenAILLMModel)
    assert main.model_name == "main"
    assert agent.model_name == "agent"


def test_openrouter_tool_toggle_suppresses_tools_per_role() -> None:
    plugin = OpenRouterPlugin(manifest(OPENROUTER_PLUGIN_GUID, "OpenRouter"))
    providers = {provider["id"]: provider for provider in plugin.model_providers or []}
    main_fields = providers["llm"]["settings_config"][0]["fields"]
    assert any(field["key"] == "llm_tools_enabled" for field in main_fields)
    model = plugin.create_model("llm", {"llm_tools_enabled": False})
    assert isinstance(model, ToolToggleOpenAILLMModel)

    tools = [{"type": "function", "function": {"name": "test"}}]
    with patch.object(OpenAILLMModel, "generate", return_value=("ok", None, None)) as generate:
        model.generate([{"role": "user", "content": "hello"}], tools, "auto")

    generate.assert_called_once_with([{"role": "user", "content": "hello"}], None, None)


def test_openai_compatible_models_cover_existing_modalities() -> None:
    plugin = OpenAICompatiblePlugin(manifest(OPENAI_COMPATIBLE_PLUGIN_GUID, "Compatible"))
    assert isinstance(plugin.create_model("custom-llm", {}), OpenAILLMModel)
    assert isinstance(plugin.create_model("custom-stt", {}), OpenAISTTModel)
    assert isinstance(plugin.create_model("custom-multimodal-stt", {}), OpenAIMultiModalSTTModel)
    assert isinstance(plugin.create_model("custom-tts", {}), OpenAITTSModel)
    assert isinstance(plugin.create_model("local-embedding", {}), OpenAIEmbeddingModel)


def test_openai_compatible_tool_toggle_defaults_on_and_can_be_disabled() -> None:
    plugin = OpenAICompatiblePlugin(manifest(OPENAI_COMPATIBLE_PLUGIN_GUID, "Compatible"))
    providers = {provider["id"]: provider for provider in plugin.model_providers or []}
    fields = providers["custom-llm"]["settings_config"][0]["fields"]
    assert any(field["key"] == "custom_llm_tools_enabled" for field in fields)
    tools = [{"type": "function", "function": {"name": "test"}}]

    enabled = plugin.create_model("custom-llm", {})
    with patch.object(OpenAILLMModel, "generate", return_value=("ok", None, None)) as generate:
        enabled.generate([{"role": "user", "content": "hello"}], tools, "auto")
    generate.assert_called_once_with([{"role": "user", "content": "hello"}], tools, "auto")

    disabled = plugin.create_model("custom-llm", {"custom_llm_tools_enabled": False})
    with patch.object(OpenAILLMModel, "generate", return_value=("ok", None, None)) as generate:
        disabled.generate([{"role": "user", "content": "hello"}], tools, "auto")
    generate.assert_called_once_with([{"role": "user", "content": "hello"}], None, None)

    local_fields = providers["local-llm"]["settings_config"][0]["fields"]
    assert not any(field["key"] == "local_llm_tools_enabled" for field in local_fields)
    assert type(plugin.create_model("local-llm", {})) is OpenAILLMModel


def test_edge_tts_provider_uses_existing_model() -> None:
    plugin = EdgeTTSPlugin(manifest(EDGE_TTS_PLUGIN_GUID, "Edge"))
    model = plugin.create_model("tts", {})
    assert isinstance(model, EdgeTTSModel)
    assert model.model_name == "edge-tts"


def capture_llm_request(model: Any, *, responses: bool = False) -> dict[str, Any]:
    """Exercise generate(), including the provider's request compatibility hook."""
    payload = SimpleNamespace(error=None, usage=None, output=[], output_text="ok") if responses else ChatCompletion.model_construct(
        id="test", model=model.model_name, object="chat.completion", created=0, usage=None,
        choices=[Choice.model_construct(index=0, finish_reason="stop", message=ChatCompletionMessage.model_construct(role="assistant", content="ok"))],
    )
    raw = SimpleNamespace(parse=lambda: payload, retries_taken=0)
    endpoint = model.client.responses if responses else model.client.chat.completions
    endpoint.with_raw_response.create = MagicMock(return_value=raw)
    model.generate([{"role": "user", "content": "Hello"}])
    return endpoint.with_raw_response.create.call_args.kwargs


@pytest.mark.parametrize("provider_id,prefix", [("llm", "llm"), ("agent-llm", "agent_llm"), ("vlm", "vlm")])
def test_openai_requests_explicit_none_and_suppresses_hidden_temperature(provider_id: str, prefix: str) -> None:
    plugin = OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI"))
    base = {f"{prefix}_model": "gpt-5.4", f"{prefix}_temperature": 0.4}
    none = capture_llm_request(plugin.create_model(provider_id, {**base, f"{prefix}_reasoning_effort": "none"}), responses=True)
    assert none["reasoning"] == {"effort": "none"}
    assert none["temperature"] == 0.4
    high = capture_llm_request(plugin.create_model(provider_id, {**base, f"{prefix}_reasoning_effort": "high"}), responses=True)
    assert high["reasoning"] == {"effort": "high"}
    assert "temperature" not in high


def test_openai_model_default_fast_and_verbosity_are_independent() -> None:
    plugin = OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI"))
    params = capture_llm_request(plugin.create_model("llm", {
        "llm_model": "gpt-6-luna", "llm_reasoning_effort": "default",
        "llm_service_tier": "fast", "llm_verbosity": "high", "llm_temperature": 0.2,
    }), responses=True)
    assert "reasoning" not in params
    assert "temperature" not in params  # This model's default is medium, not none.
    assert params["service_tier"] == "fast"
    assert params["text"] == {"verbosity": "high"}
    params = capture_llm_request(plugin.create_model("llm", {
        "llm_model": "gpt-6-astra", "llm_reasoning_effort": "none",
        "llm_service_tier": "auto", "llm_verbosity": "default",
    }), responses=True)
    assert params["reasoning"] == {"effort": "low"}
    assert params["service_tier"] == "auto"
    assert "text" not in params and "temperature" not in params


def test_curated_language_dropdowns_and_settings_migration() -> None:
    openai = OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI"))
    google = GoogleAIStudioPlugin(manifest(GOOGLE_AI_STUDIO_PLUGIN_GUID, "Google"))
    for plugin in (openai, google):
        for provider in plugin.model_providers:
            if provider["kind"] not in {"llm", "vlm"}:
                continue
            model_field = next(field for field in provider["settings_config"][0]["fields"] if field["key"].endswith("_model"))
            assert model_field["type"] == "select"
            values = [option["value"] for option in model_field["select_options"]]
            assert not any("codex" in value or "preview" in value or "pro" in value for value in values)
            assert "gpt-5.4-nano" not in values
            assert not any(value.startswith("gemini-2.5") for value in values)
    settings = {"llm_model": "gpt-5.4-nano", "llm_reasoning_effort": "minimal"}
    openai.migrate_settings(settings, 0)
    assert settings == {"llm_model": "gpt-6-luna", "llm_reasoning_effort": "none"}
    settings = {"llm_model": "gemini-3.1-flash-lite-preview", "llm_reasoning_effort": "none", "llm_temperature": 0.5}
    google.migrate_settings(settings, 0)
    assert settings["llm_model"] == "gemini-3.5-flash-lite"
    assert settings["llm_reasoning_effort"] == "minimal"
    assert settings["llm_custom_temperature"] is True


def test_google_native_thinking_and_temperature_opt_in() -> None:
    plugin = GoogleAIStudioPlugin(manifest(GOOGLE_AI_STUDIO_PLUGIN_GUID, "Google"))
    params = capture_llm_request(plugin.create_model("llm", {"llm_temperature": 0.2}))
    assert params["extra_body"] == {"google": {"thinking_config": {"thinking_level": "minimal"}}}
    assert "reasoning_effort" not in params and "temperature" not in params
    params = capture_llm_request(plugin.create_model("llm", {
        "llm_model": "gemini-3.8-flash", "llm_reasoning_effort": "minimal",
        "llm_custom_temperature": True, "llm_temperature": 0.5,
    }))
    assert params["extra_body"]["google"]["thinking_config"]["thinking_level"] == "low"
    assert params["temperature"] == 0.5
    params = capture_llm_request(plugin.create_model("llm", {"llm_reasoning_effort": "default"}))
    assert "extra_body" not in params and "reasoning_effort" not in params


def test_voice_settings_merge_globals_nested_defaults_and_character_overrides() -> None:
    plugin = OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI"))
    provider = next(provider for provider in plugin.model_providers if provider["id"] == "tts")
    globals = {"tts_model": "gpt-4o-mini-tts", "instructions": "global style", "enabled": True}
    character = {"instructions": "", "enabled": False, "voice": "cedar"}
    result = resolve_voice_settings(provider["voice_settings_config"], globals, character)
    assert result == {"tts_model": "gpt-4o-mini-tts", "instructions": "", "enabled": False, "voice": "cedar"}
    assert resolve_voice_settings(provider["voice_settings_config"], {}, {})["instructions"] == ""
    assert globals["enabled"] is True and character["voice"] == "cedar"


def test_openai_transcribe_uses_plural_languages() -> None:
    plugin = OpenAIPlugin(manifest(OPENAI_PLUGIN_GUID, "OpenAI"))
    model = plugin.create_model("stt", {"stt_language": "en, de", "stt_prompt": "Elite Dangerous"})
    model.client.audio.transcriptions.create = MagicMock(return_value=SimpleNamespace(text="Docking"))
    assert model.transcribe(sr.AudioData(b"\x00\x00" * 160, 16000, 2)) == "Docking"
    params = model.client.audio.transcriptions.create.call_args.kwargs
    assert params["model"] == "gpt-transcribe" and params["languages"] == ["en", "de"]
    assert "language" not in params and params["prompt"] == "Elite Dangerous"
