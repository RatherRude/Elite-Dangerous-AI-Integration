import json
from copy import deepcopy
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
from plugins.OpenAIPlugin import OPENAI_PLUGIN_GUID, OPENAI_LLM_MODEL, OpenAIPlugin
from plugins.GoogleAIStudioPlugin import GOOGLE_AI_STUDIO_PLUGIN_GUID, GOOGLE_LLM_MODEL, GoogleAIStudioPlugin
from plugins.OpenRouterPlugin import OPENROUTER_PLUGIN_GUID, OpenRouterPlugin


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


@pytest.mark.parametrize("plugin_type,guid,legacy_provider,old_model,new_model", [
    (OpenAIPlugin, OPENAI_PLUGIN_GUID, "openai", "gpt-5.4-nano", OPENAI_LLM_MODEL),
    (GoogleAIStudioPlugin, GOOGLE_AI_STUDIO_PLUGIN_GUID, "google-ai-studio", "gemini-3.1-flash-lite-preview", GOOGLE_LLM_MODEL),
])
def test_running_backup_import_applies_and_persists_plugin_migrations(
    plugin_type, guid, legacy_provider, old_model, new_model, monkeypatch,
) -> None:
    import lib.Config as ConfigModule
    import lib.PluginManager as PluginManagerModule

    current: Any = {"config_version": 24, "plugin_settings": {
        guid: {"settings_version": plugin_type.settings_schema_version, "api_key": "current", "llm_model": new_model},
    }}
    manager = PluginManager(current)
    plugin = plugin_type(PluginManifest(json.dumps({"guid": guid, "name": legacy_provider})))
    manager.plugin_list[guid] = manager._initialize_plugin_settings(plugin)
    saved = []
    emitted = []
    monkeypatch.setattr(ConfigModule, "save_config", lambda config: None)
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(PluginManagerModule, "save_config", lambda config: saved.append(deepcopy(config)))
    monkeypatch.setattr(PluginManagerModule, "emit_message", lambda kind, **kwargs: emitted.append((kind, deepcopy(kwargs))))

    imported = ConfigModule.update_config(current, {
        "config_version": 21, "llm_provider": legacy_provider, "llm_model_name": old_model,
        "llm_api_key": "imported-secret", "llm_temperature": 0.0, "llm_reasoning_effort": "none",
    })
    assert "settings_version" not in imported["plugin_settings"][guid]
    manager.on_settings_changed(imported)

    settings = imported["plugin_settings"][guid]
    assert settings["settings_version"] == plugin_type.settings_schema_version
    assert settings["api_key"] == "imported-secret"
    assert settings["llm_model"] == new_model
    assert settings["llm_temperature"] == 0.0
    if plugin_type is GoogleAIStudioPlugin:
        assert settings["llm_custom_temperature"] is True
        assert settings["llm_reasoning_effort"] == "minimal"
    assert plugin.settings == settings
    assert saved == [imported]
    assert emitted == [("config", {"config": imported})]
    assert manager.settings_migrated is False

    # Ordinary subsequent updates must not repeat migrations or restore defaults.
    if plugin_type is GoogleAIStudioPlugin:
        settings["llm_custom_temperature"] = False
    manager.on_settings_changed(imported)
    assert len(saved) == 1 and len(emitted) == 1
    assert plugin.settings == settings


@pytest.mark.parametrize("plugin_type,guid,model", [
    (OpenAIPlugin, OPENAI_PLUGIN_GUID, "gpt-6-sol"),
    (GoogleAIStudioPlugin, GOOGLE_AI_STUDIO_PLUGIN_GUID, "gemini-3.8-flash"),
])
def test_plugin_version_one_only_repairs_credentials(plugin_type, guid, model) -> None:
    previous = {"settings_version": 1, "api_key": "", "stt_api_key": "role-secret", "llm_model": model,
                "llm_temperature": 0.0, "llm_custom_temperature": False, "extra": {"keep": True}}
    config: Any = {"config_version": 24, "plugin_settings": {guid: deepcopy(previous)}}
    manager = PluginManager(config)
    plugin = plugin_type(PluginManifest(json.dumps({"guid": guid, "name": "Provider"})))
    manager._initialize_plugin_settings(plugin)
    assert plugin.settings == {**previous, "api_key": "role-secret", "settings_version": plugin_type.settings_schema_version}
    assert config["config_version"] == 24


@pytest.mark.parametrize("settings_version", [2, 99])
def test_current_and_future_plugin_versions_are_not_migrated(settings_version) -> None:
    stored = {"settings_version": settings_version, "api_key": "explicit", "llm_model": "gpt-6-sol", "extra": "keep"}
    config: Any = {"config_version": 24, "plugin_settings": {OPENAI_PLUGIN_GUID: deepcopy(stored)}}
    manager = PluginManager(config)
    plugin = OpenAIPlugin(PluginManifest(json.dumps({"guid": OPENAI_PLUGIN_GUID, "name": "OpenAI"})))
    plugin.migrate_settings = MagicMock(side_effect=AssertionError("Migration must not repeat"))
    manager._initialize_plugin_settings(plugin)
    manager.plugin_list[OPENAI_PLUGIN_GUID] = plugin
    manager.on_settings_changed(config)
    plugin.migrate_settings.assert_not_called()
    assert plugin.settings == stored and config["plugin_settings"][OPENAI_PLUGIN_GUID] == stored
    assert manager.settings_migrated is False


def test_settings_update_clears_removed_plugin_state() -> None:
    guid = "metadata-free"
    manager = PluginManager({"plugin_settings": {guid: {"prefix": "stale"}}})  # type: ignore[arg-type]
    plugin = MetadataFreeProviderPlugin(PluginManifest(json.dumps({"guid": guid, "name": "Compatible"})))
    manager.plugin_list[guid] = manager._initialize_plugin_settings(plugin)
    manager.on_settings_changed({"plugin_settings": {}})  # type: ignore[arg-type]
    assert plugin.settings == {}


@pytest.mark.parametrize("plugin_type,guid,provider", [
    (OpenAIPlugin, OPENAI_PLUGIN_GUID, "openai"),
    (GoogleAIStudioPlugin, GOOGLE_AI_STUDIO_PLUGIN_GUID, "google-ai-studio"),
    (OpenRouterPlugin, OPENROUTER_PLUGIN_GUID, "openrouter"),
])
@pytest.mark.parametrize("empty_agent_override", [True, False])
def test_legacy_role_credentials_survive_shared_key_migration(
    plugin_type, guid, provider, empty_agent_override,
) -> None:
    from lib.Config import migrate

    legacy = {
        "config_version": 21, "api_key": "global-secret",
        "llm_provider": provider, "llm_api_key": "main-override",
        "agent_llm_provider": provider,
    }
    if empty_agent_override:
        legacy["agent_llm_api_key"] = ""
    config: Any = migrate(legacy)
    manager = PluginManager(config)
    plugin = plugin_type(PluginManifest(json.dumps({"guid": guid, "name": provider})))
    manager._initialize_plugin_settings(plugin)
    assert plugin.settings["api_key"] == "main-override"
    assert plugin.create_model("llm", plugin.settings).client.api_key == "main-override"
    assert plugin.create_model("agent-llm", plugin.settings).client.api_key == "global-secret"

    # A user-entered shared key supersedes the imported role overrides.
    plugin.settings["api_key"] = "replacement"
    assert plugin.create_model("llm", plugin.settings).client.api_key == "replacement"
    assert plugin.create_model("agent-llm", plugin.settings).client.api_key == "replacement"
    plugin.settings["api_key"] = ""
    assert plugin.create_model("llm", plugin.settings).client.api_key == "-"


def test_mixed_legacy_provider_keys_are_not_assigned_to_the_wrong_plugin() -> None:
    from lib.Config import migrate

    config: Any = migrate({
        "config_version": 21, "api_key": "openai-global",
        "llm_provider": "openai", "llm_api_key": "",
        "agent_llm_provider": "google-ai-studio", "agent_llm_api_key": "google-override",
    })
    manager = PluginManager(config)
    openai = manager._initialize_plugin_settings(OpenAIPlugin(PluginManifest(json.dumps({"guid": OPENAI_PLUGIN_GUID, "name": "OpenAI"}))))
    google = manager._initialize_plugin_settings(GoogleAIStudioPlugin(PluginManifest(json.dumps({"guid": GOOGLE_AI_STUDIO_PLUGIN_GUID, "name": "Google"}))))
    assert openai.settings["api_key"] == "openai-global"
    assert google.settings["api_key"] == "google-override"
    assert openai.create_model("llm", openai.settings).client.api_key == "openai-global"
    assert google.create_model("agent-llm", google.settings).client.api_key == "google-override"


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
