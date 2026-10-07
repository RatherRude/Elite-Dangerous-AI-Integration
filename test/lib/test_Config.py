import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import src.lib.Config as ConfigModule
from src.lib.Config import (
    default_allowed_actions,
    migrate,
)


def test_action_defaults_match_registered_permissions() -> None:
    actions_source = (
        ROOT_DIR / "src" / "lib" / "actions" / "Actions.py"
    ).read_text(encoding="utf-8")
    registered_permissions = {
        keyword.value.value
        for node in ast.walk(ast.parse(actions_source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "registerAction"
        for keyword in node.keywords
        if keyword.arg == "permission"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    }

    assert set(default_allowed_actions) == registered_permissions


def test_migrate_removes_tools_var_and_migrates_providers() -> None:
    migrated = migrate({
        "config_version": 20,
        "tools_var": False,
        "allowed_actions": {},
        "api_key": "secret",
        "llm_provider": "openai",
        "llm_model_name": "custom-model",
        "llm_endpoint": "https://example.test/v1",
        "llm_api_key": "override",
        "llm_temperature": 0.5,
        "llm_reasoning_effort": "low",
        "tts_provider": "edge-tts",
    })

    assert migrated["config_version"] == 24
    assert "tools_var" not in migrated
    assert migrated["llm_provider"] == "plugin:7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61:llm"
    assert migrated["tts_provider"] == "plugin:e2d57ec0-56f5-45de-88ed-621d4a28d7b5:tts"
    settings = migrated["plugin_settings"]["7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"]
    assert settings["api_key"] == "override"
    assert settings["llm_model"] == "custom-model"
    assert settings["llm_endpoint"] == "https://example.test/v1"
    assert settings["llm_api_key"] == "override"
    assert "llm_model_name" not in migrated
    assert "llm_endpoint" not in migrated


def test_migrate_tools_var_to_selected_provider_tool_toggles() -> None:
    migrated = migrate({
        "config_version": 21,
        "tools_var": False,
        "llm_provider": "openrouter",
        "agent_llm_provider": "custom",
    })

    openrouter = migrated["plugin_settings"]["a9d9fb7a-18df-4602-bf7d-53f3486f7d18"]
    compatible = migrated["plugin_settings"]["64a79751-078d-48c6-9540-193afde6c469"]
    assert openrouter["llm_tools_enabled"] is False
    assert compatible["custom_agent_llm_tools_enabled"] is False
    assert "tools_var" not in migrated


def test_migrate_removes_tools_var_from_current_config() -> None:
    migrated = migrate({
        "config_version": 23,
        "tools_var": True,
    })

    assert migrated["config_version"] == 24
    assert "tools_var" not in migrated


def test_migrate_character_voice_settings_for_selected_provider() -> None:
    provider = "plugin:d17f20f6-2514-4a1f-9e54-2a3c089f5c2b:tts"
    migrated = migrate({
        "config_version": 23,
        "tts_provider": provider,
        "characters": [{
            "name": "Commander",
            "tts_voice": "en_diana_happy",
            "tts_prompt": "Sound calm.",
            "tts_voice_settings": {"plugin:other:tts": {"voice": "other"}},
        }],
        "plugin_settings": {
            "d17f20f6-2514-4a1f-9e54-2a3c089f5c2b": {"tts_voice": "ignored-global"},
        },
    })

    character = migrated["characters"][0]
    assert character["tts_voice_settings"] == {
        "plugin:other:tts": {"voice": "other"},
        provider: {"voice": "en_diana_happy", "instructions": "Sound calm."},
    }
    assert "tts_voice" not in migrated["plugin_settings"]["d17f20f6-2514-4a1f-9e54-2a3c089f5c2b"]


def test_character_voice_settings_survive_default_merge() -> None:
    provider_settings = {"plugin:example:tts": {"voice": "sample.wav", "style": "warm"}}
    merged = ConfigModule.merge_config_data(
        {"tts_voice": "nova", "tts_voice_settings": {}},
        {"tts_voice": "sample.wav", "tts_voice_settings": provider_settings},
    )

    assert merged["tts_voice_settings"] == provider_settings


def test_provider_migration_preserves_third_party_settings() -> None:
    third_party = {"token": "value", "nested": {"enabled": True}}
    migrated = migrate({
        "config_version": 21,
        "api_key": "global",
        "llm_provider": "local-ai-server",
        "llm_model_name": "local-model",
        "llm_endpoint": "http://localhost:1234/v1",
        "llm_api_key": "",
        "llm_temperature": 0.0,
        "llm_reasoning_effort": "default",
        "plugin_settings": {"third-party": third_party.copy()},
    })

    assert migrated["plugin_settings"]["third-party"] == third_party
    assert migrated["llm_provider"] == "plugin:64a79751-078d-48c6-9540-193afde6c469:local-llm"
    settings = migrated["plugin_settings"]["64a79751-078d-48c6-9540-193afde6c469"]
    assert settings["local_llm_model"] == "local-model"
    assert settings["local_llm_endpoint"] == "http://localhost:1234/v1"
    assert settings["local_llm_api_key"] == "global"
    assert settings["local_llm_temperature"] == 0.0


def test_provider_migration_preserves_recognizable_unselected_builtin_settings() -> None:
    migrated = migrate({
        "config_version": 21,
        "api_key": "global",
        "llm_provider": "plugin:third-party:llm",
        "llm_model_name": "remembered-openai-model",
        "llm_endpoint": "https://api.openai.com/v1",
        "llm_api_key": "remembered-key",
        "llm_temperature": 0.4,
        "llm_reasoning_effort": "low",
    })

    assert migrated["llm_provider"] == "plugin:third-party:llm"
    settings = migrated["plugin_settings"]["7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"]
    assert settings["llm_model"] == "remembered-openai-model"
    assert settings["llm_api_key"] == "remembered-key"
    assert settings["llm_temperature"] == 0.4


def test_provider_migration_does_not_guess_lookalike_endpoint_ownership() -> None:
    migrated = migrate({
        "config_version": 21,
        "llm_provider": "plugin:third-party:llm",
        "llm_model_name": "third-party-model",
        "llm_endpoint": "https://api.openai.com.example.test/v1",
    })

    assert "7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61" not in migrated.get("plugin_settings", {})


def test_backup_import_does_not_restore_removed_provider_keys(monkeypatch) -> None:
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, "save_config", lambda config: None)
    current = {"config_version": 24, "plugin_settings": {}}

    updated = ConfigModule.update_config(current, {
        "config_version": 21,
        "api_key": "secret",
        "llm_provider": "openai",
        "llm_model_name": "legacy-model",
        "llm_endpoint": "https://legacy.test/v1",
        "llm_api_key": "",
        "llm_temperature": 1.0,
        "llm_reasoning_effort": "none",
    })

    assert "llm_model_name" not in updated
    assert "llm_endpoint" not in updated
    assert updated["llm_provider"].endswith(":llm")
    assert updated["plugin_settings"]["7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"]["llm_model"] == "legacy-model"


def test_versionless_backup_import_migrates_legacy_providers(monkeypatch) -> None:
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, "save_config", lambda config: None)
    current = {"config_version": 24, "plugin_settings": {}, "characters": []}

    updated = ConfigModule.update_config(current, {
        "commander_name": "Test",
        "characters": [],
        "active_character_index": 0,
        "api_key": "secret",
        "llm_provider": "openai",
        "llm_model_name": "legacy-model",
        "llm_endpoint": "https://api.openai.com/v1",
        "llm_api_key": "",
        "llm_temperature": 1.0,
        "llm_reasoning_effort": "none",
    })

    assert updated["config_version"] == 24
    assert updated["llm_provider"].endswith(":llm")
    assert updated["plugin_settings"]["7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"]["llm_model"] == "legacy-model"
    assert "llm_model_name" not in updated


def test_default_config_uses_plugins_and_has_no_legacy_provider_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    config = ConfigModule.load_config()

    assert config["llm_provider"].startswith("plugin:")
    assert config["agent_llm_provider"].startswith("plugin:")
    assert config["embedding_provider"].startswith("plugin:")
    assert "tools_var" not in config
    assert not set(ConfigModule.LEGACY_PROVIDER_SETTING_KEYS).intersection(config)


@pytest.mark.parametrize("version", [None, 5, 12, 21])
def test_legacy_json_config_loads_then_migrates_through_current_provider_plugins(version, monkeypatch, tmp_path) -> None:
    from lib.PluginManager import PluginManager
    from plugins.OpenAIPlugin import OPENAI_PLUGIN_GUID, OPENAI_LLM_MODEL, OPENAI_STT_MODEL, OpenAIPlugin
    from plugins.GoogleAIStudioPlugin import (
        GOOGLE_AI_STUDIO_PLUGIN_GUID, GOOGLE_AGENT_LLM_MODEL, GOOGLE_VLM_MODEL, GOOGLE_TTS_MODEL, GoogleAIStudioPlugin,
    )

    third_party = {"settings_version": 9, "token": "keep", "nested": {"enabled": False}}
    legacy = {
        "commander_name": "Legacy Commander",
        "characters": [{"name": "Default", "tts_voice": "Kore", "tts_prompt": "Warm and calm."}],
        "llm_provider": "openai", "llm_model_name": "gpt-5.4-nano", "llm_api_key": "openai-secret",
        "llm_endpoint": "https://api.openai.com/v1", "llm_temperature": 0.0, "llm_reasoning_effort": "none",
        "agent_llm_provider": "google-ai-studio", "agent_llm_model_name": "gemini-3.1-flash-lite-preview",
        "agent_llm_api_key": "google-secret", "agent_llm_temperature": 0.35, "agent_llm_reasoning_effort": "low",
        "vision_provider": "google-ai-studio", "vision_model_name": "gemini-2.5-flash",
        "vision_api_key": "google-secret", "vision_temperature": 0.0, "vision_reasoning_effort": "low",
        "stt_provider": "openai", "stt_model_name": "gpt-4o-mini-transcribe", "stt_api_key": "openai-secret",
        "stt_language": "en", "stt_custom_prompt": "Elite Dangerous",
        "tts_provider": "google-ai-studio", "tts_model_name": "gemini-3.8-flash-lite-tts", "tts_api_key": "google-secret",
        "embedding_provider": "openai", "embedding_model_name": "text-embedding-3-large",
        "embedding_api_key": "openai-secret", "plugin_settings": {"third-party": deepcopy(third_party)},
    }
    if version is not None:
        legacy["config_version"] = version
        legacy["active_character_index"] = 0
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ConfigModule, "get_default_input_device_name", lambda: "input")
    monkeypatch.setattr(ConfigModule, "get_default_output_device_name", lambda: "output")
    (tmp_path / "config.json").write_text(json.dumps(legacy), encoding="utf-8")
    config = ConfigModule.load_config()

    assert config["config_version"] == 24
    assert not set(ConfigModule.LEGACY_PROVIDER_SETTING_KEYS).intersection(config)
    assert config["llm_provider"] == f"plugin:{OPENAI_PLUGIN_GUID}:llm"
    assert config["agent_llm_provider"] == f"plugin:{GOOGLE_AI_STUDIO_PLUGIN_GUID}:agent-llm"
    assert config["vision_provider"] == f"plugin:{GOOGLE_AI_STUDIO_PLUGIN_GUID}:vlm"
    assert config["tts_provider"] == f"plugin:{GOOGLE_AI_STUDIO_PLUGIN_GUID}:tts"
    assert "settings_version" not in config["plugin_settings"][OPENAI_PLUGIN_GUID]
    assert "settings_version" not in config["plugin_settings"][GOOGLE_AI_STUDIO_PLUGIN_GUID]
    assert config["plugin_settings"]["third-party"] == third_party
    voice = config["characters"][0]["tts_voice_settings"][config["tts_provider"]]
    assert voice == {"voice": "Kore", "instructions": "Warm and calm."}

    manager = PluginManager(config)
    manager.load_default_plugins()
    openai = manager.plugin_list[OPENAI_PLUGIN_GUID]
    google = manager.plugin_list[GOOGLE_AI_STUDIO_PLUGIN_GUID]
    assert openai.settings["settings_version"] == OpenAIPlugin.settings_schema_version
    assert google.settings["settings_version"] == GoogleAIStudioPlugin.settings_schema_version
    assert openai.settings["api_key"] == "openai-secret"
    assert google.settings["api_key"] == "google-secret"
    assert openai.settings["llm_model"] == OPENAI_LLM_MODEL
    assert openai.settings["llm_temperature"] == 0.0
    assert openai.settings["stt_model"] == OPENAI_STT_MODEL
    assert openai.settings["stt_language"] == "en"
    assert openai.settings["stt_prompt"] == "Elite Dangerous"
    assert google.settings["agent_llm_model"] == GOOGLE_AGENT_LLM_MODEL
    assert google.settings["agent_llm_custom_temperature"] is True
    assert google.settings["vlm_model"] == GOOGLE_VLM_MODEL
    assert google.settings["vlm_temperature"] == 0.0
    assert google.settings["vlm_custom_temperature"] is True
    assert google.settings["tts_model"] == GOOGLE_TTS_MODEL
    assert config["plugin_settings"]["third-party"] == third_party
    assert config["characters"][0]["tts_voice_settings"][config["tts_provider"]] == voice
    assert openai.create_model("llm", openai.settings).client.api_key == "openai-secret"
    assert google.create_model("agent-llm", google.settings).client.api_key == "google-secret"

    # Save and reload the fully migrated result: neither migration stage repeats.
    ConfigModule.save_config(config)
    saved = deepcopy(config)
    reloaded = ConfigModule.load_config()
    second_manager = PluginManager(reloaded)
    second_manager.load_default_plugins()
    assert reloaded == saved
    assert second_manager.settings_migrated is False


def test_legacy_handoff_preserves_existing_plugin_values_and_version() -> None:
    guid = "7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"
    existing = {"settings_version": 2, "api_key": "plugin-key", "llm_model": "gpt-6-sol", "llm_temperature": 0.8}
    migrated = migrate({
        "config_version": 21, "api_key": "old-key", "llm_provider": "openai",
        "llm_model_name": "gpt-5.4-nano", "llm_temperature": 0.0,
        "plugin_settings": {guid: deepcopy(existing)},
    })
    assert migrated["plugin_settings"][guid] == existing


def test_current_config_keeps_vision_plugin_selection_when_disabled() -> None:
    provider = "plugin:51f1df0c-479d-4f0f-a585-57c08d9e1901:vlm"
    migrated = migrate({"config_version": 24, "vision_var": False, "vision_provider": provider})
    assert migrated["vision_provider"] == provider
    legacy = migrate({"config_version": 21, "vision_var": False, "vision_provider": "google-ai-studio"})
    assert legacy["vision_provider"] == "none"


@pytest.mark.parametrize("provider", ["openai", "google-ai-studio"])
def test_very_old_shared_key_config_does_not_require_role_api_key(provider) -> None:
    migrated = migrate({
        "config_version": 5, "api_key": "shared-secret", "llm_provider": provider, "characters": [],
    })
    guid = "7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61" if provider == "openai" else "51f1df0c-479d-4f0f-a585-57c08d9e1901"
    assert migrated["plugin_settings"][guid]["api_key"] == "shared-secret"
    assert migrated["plugin_settings"][guid]["embedding_api_key"] == "shared-secret"
