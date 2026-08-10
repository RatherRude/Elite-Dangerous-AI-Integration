from pathlib import Path
import sys
from typing import cast


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from lib.Models import OpenAIEmbeddingModel, OpenAILLMModel, OpenAISTTModel
from lib.Config import Config
from lib.PluginBase import PluginManifest
from lib.PluginManager import PluginManager
from plugins.MistralPlugin import (
    MISTRAL_PLUGIN_GUID,
    MistralLLMModel,
    MistralPlugin,
    MistralTTSModel,
)


def create_plugin() -> MistralPlugin:
    return MistralPlugin(PluginManifest("""{
        "guid": "d17f20f6-2514-4a1f-9e54-2a3c089f5c2b",
        "name": "Mistral Plugin"
    }"""))


def test_mistral_plugin_declares_all_model_providers() -> None:
    plugin = create_plugin()

    assert plugin.settings_config is not None
    assert plugin.model_providers is not None
    assert {
        (provider["kind"], provider["id"])
        for provider in plugin.model_providers
    } == {
        ("llm", "llm"),
        ("embedding", "embedding"),
        ("stt", "stt"),
        ("tts", "tts"),
    }


def test_mistral_plugin_has_stable_provider_ids() -> None:
    plugin = create_plugin()

    assert plugin.plugin_manifest.guid == MISTRAL_PLUGIN_GUID
    assert {
        f"plugin:{MISTRAL_PLUGIN_GUID}:{provider['id']}"
        for provider in plugin.model_providers or []
    } == {
        f"plugin:{MISTRAL_PLUGIN_GUID}:llm",
        f"plugin:{MISTRAL_PLUGIN_GUID}:embedding",
        f"plugin:{MISTRAL_PLUGIN_GUID}:stt",
        f"plugin:{MISTRAL_PLUGIN_GUID}:tts",
    }


def test_plugin_manager_marks_builtin_model_providers(monkeypatch) -> None:
    monkeypatch.setattr("lib.PluginManager.emit_message", lambda *args, **kwargs: None)
    manager = PluginManager(cast(Config, {"plugin_settings": {}}))
    manager.plugin_list[MISTRAL_PLUGIN_GUID] = create_plugin()
    manager.builtin_plugin_guids.add(MISTRAL_PLUGIN_GUID)

    manager.register_settings()

    assert manager.plugin_model_providers
    assert all(provider["is_builtin"] for provider in manager.plugin_model_providers)

    manager.builtin_plugin_guids.clear()
    manager.register_settings()

    assert all(not provider["is_builtin"] for provider in manager.plugin_model_providers)


def test_mistral_plugin_creates_models_with_defaults() -> None:
    plugin = create_plugin()

    llm = plugin.create_model("llm", {"api_key": "test-key"})
    embedding = plugin.create_model("embedding", {"api_key": "test-key"})
    stt = plugin.create_model("stt", {"api_key": "test-key"})
    tts = plugin.create_model("tts", {"api_key": "test-key"})

    assert isinstance(llm, MistralLLMModel)
    assert isinstance(llm, OpenAILLMModel)
    assert llm.provider_name == "mistral"
    assert llm.model_name == "mistral-small-latest"
    assert str(llm.client.base_url) == "https://api.mistral.ai/v1/"
    assert isinstance(embedding, OpenAIEmbeddingModel)
    assert embedding.model_name == "mistral-embed"
    assert str(embedding.client.base_url) == "https://api.mistral.ai/v1/"
    assert isinstance(stt, OpenAISTTModel)
    assert stt.provider_name == "mistral"
    assert stt.model_name == "voxtral-mini-latest"
    assert str(stt.client.base_url) == "https://api.mistral.ai/v1/"
    assert isinstance(tts, MistralTTSModel)
    assert tts.provider_name == "mistral"
    assert tts.model_name == "voxtral-mini-tts-2603"
    assert tts.default_voice == "en_paul_neutral"
    assert str(tts.client.base_url) == "https://api.mistral.ai/v1/"
