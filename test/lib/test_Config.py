import ast
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

    assert migrated["config_version"] == 23
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

    assert migrated["config_version"] == 23
    assert "tools_var" not in migrated


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
    current = {"config_version": 23, "plugin_settings": {}}

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
    current = {"config_version": 23, "plugin_settings": {}, "characters": []}

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

    assert updated["config_version"] == 23
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
