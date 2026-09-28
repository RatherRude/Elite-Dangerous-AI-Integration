import json
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch


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
from plugins.EdgeTTSPlugin import EDGE_TTS_PLUGIN_GUID, EdgeTTSModel, EdgeTTSPlugin
from plugins.GoogleAIStudioPlugin import GOOGLE_AI_STUDIO_API_URL, GOOGLE_AI_STUDIO_PLUGIN_GUID, GoogleAIStudioPlugin, GoogleAIStudioLLMModel
from plugins.MistralPlugin import MISTRAL_API_URL, MISTRAL_PLUGIN_GUID, MistralPlugin
from plugins.OpenAICompatiblePlugin import OPENAI_COMPATIBLE_PLUGIN_GUID, OpenAICompatiblePlugin
from plugins.OpenAIPlugin import OPENAI_API_URL, OPENAI_PLUGIN_GUID, OpenAIPlugin
from plugins.OpenRouterPlugin import OPENROUTER_API_URL, OPENROUTER_PLUGIN_GUID, OpenRouterPlugin
from plugins.ProviderPluginHelpers import ToolToggleOpenAILLMModel


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
        for field in grid["fields"]
        if "key" in field
    }


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
    assert provider_ids(plugin) == {"llm", "agent-llm", "vlm", "stt", "embedding"}
    assert isinstance(plugin.create_model("llm", {}), GoogleAIStudioLLMModel)
    assert isinstance(plugin.create_model("stt", {}), OpenAIMultiModalSTTModel)
    assert isinstance(plugin.create_model("embedding", {}), OpenAIEmbeddingModel)


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
