import ast
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import src.lib.Config as ConfigModule
from src.lib.Config import (
    default_allowed_actions,
    migrate,
)


@pytest.mark.parametrize('event_name', ['VoiceDamaged', 'VoiceRepaired'])
def test_voice_events_have_enabled_default_reactions(event_name):
    assert ConfigModule.game_events[event_name] is True
    assert ConfigModule.default_event_reactions[event_name] == 'on'


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

    assert migrated["config_version"] == 25
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

    assert migrated["config_version"] == 25
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

    assert updated["config_version"] == 25
    assert updated["llm_provider"].endswith(":llm")
    assert updated["plugin_settings"]["7f6f8e98-576f-4d1d-9d87-0f8f7f2f3c61"]["llm_model"] == "legacy-model"
    assert "llm_model_name" not in updated


def crew_config(primary=0, active=None):
    return {
        "config_version": 25,
        "characters": [{"name": name} for name in ("Default", "Nyx", "Orion", "Spare")],
        "active_character_index": primary,
        "active_characters": [primary] if active is None else active,
    }


def test_migrate_initializes_active_crew_from_existing_primary() -> None:
    config = crew_config(primary=2)
    config["config_version"] = 24
    config.pop("active_characters")

    migrated = migrate(config)

    assert migrated["config_version"] == 25
    assert migrated["active_characters"] == [2]


@pytest.mark.parametrize("active, expected", [
    ([2, 2, -1, 99, "1", True, 1.5, 1], [0, 2, 1]),
    ([], [0]),
    (None, [0]),
    ("invalid", [0]),
])
def test_normalize_active_crew_removes_invalid_indices_and_includes_primary(active, expected) -> None:
    config = crew_config()
    config["active_characters"] = active

    assert ConfigModule.normalize_active_crew(config)["active_characters"] == expected


def test_normalize_active_crew_recovers_invalid_primary() -> None:
    config = ConfigModule.normalize_active_crew(crew_config(primary=99, active=[2, 1]))

    assert config["active_character_index"] == 2
    assert config["active_characters"] == [2, 1]


@pytest.mark.parametrize('primary', [0, 5])
def test_active_crew_limit_includes_primary_on_migration_and_save(monkeypatch, primary) -> None:
    monkeypatch.setattr(ConfigModule, 'emit_message', lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, 'save_config', lambda config: None)
    config = crew_config(primary=primary)
    config['characters'].extend([{'name': 'Fourth'}, {'name': 'Fifth'}])
    config['active_characters'] = [0, 1, 2, 3, 4, 5]

    migrated = migrate(config.copy())
    updated = ConfigModule.update_config(config, {'active_characters': [0, 1, 2, 3, 4, 5]})

    expected = [primary, *[index for index in range(6) if index != primary]][:3]
    assert migrated['active_characters'] == updated['active_characters'] == expected


def test_adding_a_new_primary_never_exceeds_three_active_characters(monkeypatch) -> None:
    monkeypatch.setattr(ConfigModule, 'emit_message', lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, 'save_config', lambda config: None)
    updated = ConfigModule.update_character(crew_config(active=[0, 1, 2, 3]), {
        'operation': 'add', 'character': {'name': 'New'}, 'set_active': True,
    })

    assert len(updated['active_characters']) == 3
    assert updated['active_characters'][0] == updated['active_character_index'] == 4


def test_active_crew_saves_and_reloads(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    emitted = Mock()
    monkeypatch.setattr(ConfigModule, "emit_message", emitted)
    monkeypatch.setattr(ConfigModule, "get_default_input_device_name", lambda: "")
    monkeypatch.setattr(ConfigModule, "get_default_output_device_name", lambda: "")

    updated = ConfigModule.update_config(crew_config(), {"active_characters": [0, 2, 3]})
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    reloaded = ConfigModule.load_config()

    assert saved["active_characters"] == reloaded["active_characters"] == [0, 2, 3]
    assert reloaded["active_character_index"] == 0
    emitted.assert_called_once_with("config", config=updated)


def test_character_color_saves_and_survives_reload(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, "get_default_input_device_name", lambda: "")
    monkeypatch.setattr(ConfigModule, "get_default_output_device_name", lambda: "")
    config = crew_config(primary=1, active=[1, 2])
    character = {**config['characters'][1], 'color': '#e91e63'}

    ConfigModule.update_character(config, {
        'operation': 'update', 'index': 1, 'character': character,
    })
    reloaded = ConfigModule.load_config()

    assert reloaded['characters'][1]['color'] == '#e91e63'
    assert reloaded['characters'][0]['color'] == '#00bcd4'
    assert reloaded['active_characters'] == [1, 2]


@pytest.mark.parametrize("operation, primary, active, index, expected_primary, expected_active", [
    ("set_active", 0, [0], 2, 2, [2]),
    ("set_active", 0, [0, 1], 1, 1, [1, 0]),
    ("set_active", 0, [0, 1], 2, 2, [2, 0, 1]),
    ("delete", 2, [2, 0], 1, 1, [1, 0]),
    ("delete", 0, [0, 1, 2], 1, 0, [0, 1]),
    ("delete", 1, [1, 2], 1, 1, [1]),
    ("delete", 1, [1], 1, 0, [0]),
])
def test_character_operations_keep_roster_valid(
    monkeypatch, operation, primary, active, index, expected_primary, expected_active,
) -> None:
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, "save_config", lambda config: None)

    updated = ConfigModule.update_character(
        crew_config(primary, active), {"operation": operation, "index": index},
    )

    assert updated["active_character_index"] == expected_primary
    assert updated["active_characters"] == expected_active


@pytest.mark.parametrize("active, expected", [([0], [4]), ([0, 2], [4, 0, 2])])
def test_new_primary_preserves_only_existing_multicrew(monkeypatch, active, expected) -> None:
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, "save_config", lambda config: None)

    updated = ConfigModule.update_character(crew_config(active=active), {
        "operation": "add", "character": {"name": "New"}, "set_active": True,
    })

    assert updated["active_character_index"] == 4
    assert updated["active_characters"] == expected


def test_direct_primary_update_keeps_single_character_mode(monkeypatch) -> None:
    monkeypatch.setattr(ConfigModule, "emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(ConfigModule, "save_config", lambda config: None)

    updated = ConfigModule.update_config(crew_config(), {"active_character_index": 2})

    assert updated["active_characters"] == [2]


def test_empty_characters_have_no_active_crew() -> None:
    config = ConfigModule.normalize_active_crew({
        "characters": [], "active_character_index": 0, "active_characters": [0, 1],
    })

    assert config["active_characters"] == []
    assert config["active_character_index"] == -1


def test_default_config_uses_plugins_and_has_no_legacy_provider_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    config = ConfigModule.load_config()

    assert config["llm_provider"].startswith("plugin:")
    assert config["agent_llm_provider"].startswith("plugin:")
    assert config["embedding_provider"].startswith("plugin:")
    assert "tools_var" not in config
    assert not set(ConfigModule.LEGACY_PROVIDER_SETTING_KEYS).intersection(config)
