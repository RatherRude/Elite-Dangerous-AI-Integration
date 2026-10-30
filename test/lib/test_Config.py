import ast
from copy import deepcopy
from pathlib import Path
import sys

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

    assert migrated["config_version"] == 26
    assert "tools_var" not in migrated
    assert migrated["llm_provider"] == "plugin:7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61:llm"
    assert migrated["tts_provider"] == "plugin:e2d57ec0-56f5-45de-88ed-621d4a28d7b5:tts"
    settings = migrated["plugin_settings"]["7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"]
    assert settings["api_key"] == "secret"
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

    assert migrated["config_version"] == 26
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

    assert updated["config_version"] == 26
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


def test_voice_activation_defaults_and_legacy_word_survive_updates(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = ConfigModule.load_config()
    assert config["ptt_var"] == "voice_activation"
    assert config["characters"][0]["name"] == "Default"
    assert config["characters"][0]["first_name"] == "Simone"
    assert "Your name is Simone." in config["characters"][0]["character"]
    assert "wake_word_name" not in config
    assert config["wake_word_timeout"] == 10.0
    assert config["wake_word_source"] == "main"
    assert config["wake_word_first_command"] == "retranscribe"
    updated = ConfigModule.update_config(config, {"ptt_var": "wake_word", "stt_required_word": "old word"})
    assert updated["stt_required_word"] == "old word"
    assert ConfigModule.load_config()["ptt_var"] == "wake_word"


def test_invalid_voice_config_is_not_persisted(monkeypatch):
    saved = []
    monkeypatch.setattr(ConfigModule, "save_config", saved.append)
    current = {"wake_word_timeout": 10.0}
    for change in ({"wake_word_timeout": 0}, {"wake_word_timeout": float("nan")}):
        assert ConfigModule.update_config(current, change) is current
    assert not saved


def test_migrate_default_avatar_preserves_custom_avatars_and_global_settings() -> None:
    custom = {
        "name": "Default", "first_name": "Astra",
        "personality_preset": "custom", "character": "Custom prompt",
    }
    data = {
        "config_version": 24,
        "characters": [
            {
                "name": "Default", "personality_preset": "default",
                "character": "Custom introduction. Your name is COVAS:NEXT.",
                "tts_voice": "my-voice", "event_reactions": {"Docked": "off"},
            },
            custom.copy(),
            {"name": "Astra", "personality_preset": "custom"},
        ],
        "active_character_index": 2,
        "ptt_var": "wake_word", "wake_word_name": "Obsolete",
        "wake_word_timeout": 17.5, "wake_word_source": "parakeet",
        "wake_word_first_command": "reuse",
    }

    expected_settings = {
        key: data[key]
        for key in ("ptt_var", "wake_word_timeout", "wake_word_source", "wake_word_first_command")
    }
    migrated = ConfigModule.migrate(data)

    assert migrated["config_version"] == 26
    assert [character["name"] for character in migrated["characters"]] == ["Default", "Default", "Astra"]
    assert [character["first_name"] for character in migrated["characters"]] == ["Simone", "Astra", "Simone"]
    assert migrated["characters"][0]["character"] == "Custom introduction. Your name is Simone."
    assert migrated["characters"][0]["tts_voice"] == "my-voice"
    assert migrated["characters"][0]["event_reactions"] == {"Docked": "off"}
    assert migrated["characters"][1] == custom
    assert migrated["active_character_index"] == 2
    assert "wake_word_name" not in migrated
    for key, value in expected_settings.items():
        assert migrated[key] == value
    assert ConfigModule.migrate(deepcopy(migrated)) == migrated


def test_versionless_backup_does_not_duplicate_simone() -> None:
    migrated = ConfigModule.migrate({
        "characters": [
            {"name": "Simone", "personality_preset": "default", "event_reaction_enabled_var": False},
            {"name": "Astra", "personality_preset": "custom"},
        ],
        "active_character_index": 1,
    })

    assert [character["name"] for character in migrated["characters"]] == ["Simone", "Astra"]
    assert migrated["active_character_index"] == 1
    assert migrated["characters"][0]["event_reaction_enabled_var"] is False


def test_migrate_preserves_custom_first_avatar_name() -> None:
    for name, preset in (("Default", "custom"), ("Astra", "default")):
        character = {"name": name, "personality_preset": preset}
        migrated = ConfigModule.migrate({
            "config_version": 24, "characters": [character.copy()],
            "active_character_index": 0,
        })
        assert migrated["characters"] == [{**character, "first_name": "Simone"}]
        assert migrated["active_character_index"] == 0


def test_avatar_switch_and_first_name_change_keep_dialogue_settings_global(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    config = ConfigModule.load_config()
    config["characters"].append({
        **config["characters"][0], "name": "Explorer", "first_name": "Astra",
    })
    config["ptt_var"] = "wake_word"
    config["wake_word_timeout"] = 17.5
    config["wake_word_source"] = "parakeet"
    config["wake_word_first_command"] = "reuse"
    monkeypatch.setattr(ConfigModule, "save_config", lambda config: None)
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)

    updated = ConfigModule.update_character(config, {"operation": "set_active", "index": 1})
    updated = ConfigModule.update_character(updated, {
        "operation": "update", "index": 1,
        "character": {**updated["characters"][1], "first_name": "L\u00e9a Marie"},
    })
    updated = ConfigModule.update_config(updated, {"wake_word_name": "Obsolete"})

    assert updated["characters"][0]["name"] == "Default"
    assert updated["characters"][0]["first_name"] == "Simone"
    assert updated["characters"][1]["name"] == "Explorer"
    assert updated["characters"][1]["first_name"] == "L\u00e9a Marie"
    assert updated["active_character_index"] == 1
    assert updated["ptt_var"] == "wake_word"
    assert updated["wake_word_timeout"] == 17.5
    assert updated["wake_word_source"] == "parakeet"
    assert updated["wake_word_first_command"] == "reuse"
    assert "wake_word_name" not in updated
    assert not any(key.startswith("wake_word_") for character in updated["characters"] for key in character)


def test_invalid_active_first_name_rejects_mode_switch_without_saving(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    config = ConfigModule.load_config()
    config["characters"][0]["first_name"] = "!!!"
    saved = []
    notified = []
    monkeypatch.setattr(ConfigModule, "save_config", saved.append)
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, "show_chat_message", lambda *args: notified.append(args))

    assert ConfigModule.validate_config(config) is config
    assert ConfigModule.update_config(config, {"ptt_var": "wake_word"}) is config
    assert config["ptt_var"] == "voice_activation"
    assert not saved
    assert notified and notified[-1][0] == "error"
    config["ptt_var"] = "wake_word"
    assert ConfigModule.validate_config(config) is None


def test_invalid_first_name_change_does_not_mutate_current_config(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    config = ConfigModule.load_config()
    config["ptt_var"] = "wake_word"
    saved = []
    monkeypatch.setattr(ConfigModule, "save_config", saved.append)
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)

    updated = ConfigModule.update_character(config, {
        "operation": "update", "index": 0,
        "character": {**config["characters"][0], "first_name": "!!!"},
    })

    assert updated is config
    assert config["characters"][0]["first_name"] == "Simone"
    assert not saved


def test_invalid_avatar_selection_keeps_previous_active_avatar(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    config = ConfigModule.load_config()
    config["characters"].append({**config["characters"][0], "name": "Explorer", "first_name": "!!!"})
    config["ptt_var"] = "wake_word"
    saved = []
    monkeypatch.setattr(ConfigModule, "save_config", saved.append)
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)

    updated = ConfigModule.update_character(config, {"operation": "set_active", "index": 1})

    assert updated is config
    assert updated["active_character_index"] == 0
    assert not saved


def test_version_25_copy_gets_default_first_name_without_changing_profile() -> None:
    character = {
        "name": "Default (Copy)", "character": "My custom prompt",
        "personality_preset": "custom", "tts_voice": "my-voice",
        "event_reactions": {"Docked": "off"},
    }
    migrated = ConfigModule.migrate({
        "config_version": 25, "characters": [character.copy()],
        "active_character_index": 0,
    })

    assert migrated["characters"] == [{**character, "first_name": "Simone"}]
    assert migrated["active_character_index"] == 0
    assert ConfigModule.migrate(deepcopy(migrated)) == migrated


def test_technical_profile_rename_does_not_change_activation(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    config = ConfigModule.load_config()
    config["ptt_var"] = "wake_word"
    monkeypatch.setattr(ConfigModule, "save_config", lambda config: None)
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)

    updated = ConfigModule.update_character(config, {
        "operation": "update", "index": 0,
        "character": {**config["characters"][0], "name": "Default (Copy)"},
    })

    assert updated["characters"][0]["name"] == "Default (Copy)"
    assert updated["characters"][0]["first_name"] == "Simone"
    assert ConfigModule.validate_config(updated) is updated
