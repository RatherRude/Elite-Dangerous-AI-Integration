import json
from pathlib import Path
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginManager import PluginManager
from lib.Logger import ModelUsageStats
from lib.Models import EmbeddingModel, LLMModel, OpenAILLMModel, OpenAIResponsesLLMModel, STTModel, TTSModel
from plugins.OpenAIPlugin import OPENAI_PLUGIN_GUID


class MigratingPlugin(PluginBase):
    settings_schema_version = 2

    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)

    def migrate_settings(self, settings: dict[str, Any], from_version: int) -> None:
        settings[f"migration_{from_version}"] = True


class CompatibleLLM(LLMModel):
    def __init__(self, prefix: str):
        super().__init__("compatible-model")
        self.prefix = prefix

    def generate(self, messages, tools=None, tool_choice=None):
        return f"{self.prefix}:{messages[-1]['content']}", tools, ModelUsageStats()


class CompatibleSTT(STTModel):
    def __init__(self):
        super().__init__("compatible-stt")

    def transcribe(self, audio):
        return "transcribed"


class CompatibleTTS(TTSModel):
    def __init__(self):
        super().__init__("compatible-tts")

    def synthesize(self, text, voice):
        yield f"{voice}:{text}".encode()


class CompatibleEmbedding(EmbeddingModel):
    def __init__(self):
        super().__init__("compatible-embedding")

    def create_embedding(self, input_text):
        return self.model_name, [float(len(input_text))]


class MetadataFreeProviderPlugin(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        self.model_providers = [{
            "kind": "llm",
            "id": "llm",
            "label": "Compatible LLM",
            "settings_config": [],
        }, {
            "kind": "llm", "id": "openai-compatible", "label": "OpenAI-compatible", "settings_config": [],
        }, {
            "kind": "stt", "id": "stt", "label": "Compatible STT", "settings_config": [],
        }, {
            "kind": "tts", "id": "tts", "label": "Compatible TTS", "settings_config": [],
        }, {
            "kind": "embedding", "id": "embedding", "label": "Compatible Embedding", "settings_config": [],
        }]

    def create_model(self, provider_id: str, settings: dict[str, Any]):
        if provider_id == "llm":
            return CompatibleLLM(str(settings.get("prefix") or "default"))
        if provider_id == "openai-compatible":
            return OpenAILLMModel("http://localhost:1234/v1", "-", "compatible-model", 1.0)
        if provider_id == "stt":
            return CompatibleSTT()
        if provider_id == "tts":
            return CompatibleTTS()
        if provider_id == "embedding":
            return CompatibleEmbedding()
        raise ValueError(provider_id)


def test_initialize_plugin_settings_uses_fresh_dict_and_runs_migrations() -> None:
    guid = "test-plugin"
    config: Any = {"plugin_settings": {guid: {"existing": "value"}}}
    manager = PluginManager(config)
    plugin = MigratingPlugin(PluginManifest(json.dumps({"guid": guid, "name": "Test"})))

    manager._initialize_plugin_settings(plugin)

    assert plugin.settings == {
        "existing": "value",
        "migration_0": True,
        "migration_1": True,
        "settings_version": 2,
    }
    assert plugin.settings is not config["plugin_settings"][guid] or manager.settings_migrated
    assert manager.settings_migrated is True


def test_initialize_plugins_without_settings_do_not_share_state() -> None:
    manager = PluginManager({"plugin_settings": {}})  # type: ignore[arg-type]
    first = MigratingPlugin(PluginManifest(json.dumps({"guid": "first", "name": "First"})))
    second = MigratingPlugin(PluginManifest(json.dumps({"guid": "second", "name": "Second"})))

    manager._initialize_plugin_settings(first)
    manager._initialize_plugin_settings(second)
    first.settings["only_first"] = True

    assert "only_first" not in second.settings


def test_default_provider_plugins_register_and_create_models() -> None:
    manager = PluginManager({"plugin_settings": {}})  # type: ignore[arg-type]
    manager.load_default_plugins()
    manager.register_settings()

    model = manager.create_plugin_model(OPENAI_PLUGIN_GUID, "llm", "llm")

    assert isinstance(model, OpenAIResponsesLLMModel)
    assert OPENAI_PLUGIN_GUID in manager.builtin_plugin_guids


def test_metadata_free_third_party_provider_contract_remains_compatible() -> None:
    guid = "unchanged-third-party"
    manager = PluginManager({"plugin_settings": {guid: {"prefix": "plugin"}}})  # type: ignore[arg-type]
    plugin = MetadataFreeProviderPlugin(PluginManifest(json.dumps({"guid": guid, "name": "Compatible"})))
    manager.plugin_list[guid] = manager._initialize_plugin_settings(plugin)

    manager.register_settings()
    model = manager.create_plugin_model(guid, "llm", "llm")

    assert isinstance(model, CompatibleLLM)
    text, received_tools, _ = model.generate(
        [{"role": "user", "content": "hello"}],
        [{"type": "function", "function": {"name": "test"}}],
    )
    assert text == "plugin:hello"
    assert received_tools == [{"type": "function", "function": {"name": "test"}}]

    openai_compatible = manager.create_plugin_model(guid, "openai-compatible", "llm")
    stt = manager.create_plugin_model(guid, "stt", "stt")
    tts = manager.create_plugin_model(guid, "tts", "tts")
    embedding = manager.create_plugin_model(guid, "embedding", "embedding")

    assert isinstance(openai_compatible, OpenAILLMModel)
    assert isinstance(stt, CompatibleSTT) and stt.transcribe(None) == "transcribed"
    assert isinstance(tts, CompatibleTTS) and b"nova:hello" == b"".join(tts.synthesize("hello", "nova"))
    assert isinstance(embedding, CompatibleEmbedding)
    assert embedding.create_embedding("hello") == ("compatible-embedding", [5.0])


def test_unchanged_elevenlabs_plugin_loads_creates_and_executes_tts() -> None:
    plugin_dir = ROOT_DIR / "plugins" / "plugin-elevenlabs"
    manifest_path = plugin_dir / "manifest.json"
    if not manifest_path.is_file():
        pytest.skip("ElevenLabs plugin checkout is not available")

    manifest = PluginManifest(manifest_path.read_text(encoding="utf-8"))
    manager = PluginManager({
        "plugin_settings": {
            manifest.guid: {
                "elevenlabs_api_key": "test-key",
                "elevenlabs_model_id": "eleven_flash_v2_5",
            },
        },
    })  # type: ignore[arg-type]
    plugin = manager.load_plugin_module(manifest, str(plugin_dir / manifest.entrypoint))
    manager.plugin_list[manifest.guid] = plugin

    manager.register_settings()
    model = manager.create_plugin_model(manifest.guid, "elevenlabs-tts", "tts")

    assert isinstance(model, TTSModel)
    model._client = MagicMock()  # type: ignore[attr-defined]
    model._client.text_to_speech.stream.return_value = [b"first", b"second"]  # type: ignore[attr-defined]
    assert b"".join(model.synthesize("hello", "voice-id")) == b"firstsecond"
    model._client.text_to_speech.stream.assert_called_once_with(  # type: ignore[attr-defined]
        text="hello",
        voice_id="voice-id",
        model_id="eleven_flash_v2_5",
        output_format="pcm_24000",
        voice_settings={
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    )
