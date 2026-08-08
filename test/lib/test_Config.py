import ast
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.Config import (
    default_allowed_actions,
    merge_config_data,
    migrate,
    migrate_allowed_actions,
    update_config,
)


def test_migrate_empty_allowed_actions_enables_all_current_actions() -> None:
    migrated = migrate({"config_version": 18, "allowed_actions": []})

    assert migrated["config_version"] == 20
    assert migrated["allowed_actions"] == default_allowed_actions
    assert all(migrated["allowed_actions"].values())


def test_migrate_restrictive_allowed_actions_preserves_selection() -> None:
    migrated = migrate({
        "config_version": 18,
        "allowed_actions": ["fireWeapons", "setSpeed"],
    })

    assert migrated["allowed_actions"]["fireWeapons"] is True
    assert migrated["allowed_actions"]["setSpeed"] is True
    assert migrated["allowed_actions"]["textMessage"] is False
    assert set(migrated["allowed_actions"]) == set(default_allowed_actions)


def test_migrate_adds_engine_boost_permission() -> None:
    migrated = migrate({
        "config_version": 19,
        "allowed_actions": {"fireWeapons": True},
    })

    assert migrated["config_version"] == 20
    assert migrated["allowed_actions"]["engineBoost"] is True


def test_migrate_version_17_enables_plot_to_target_before_map_conversion() -> None:
    migrated = migrate({
        "config_version": 17,
        "allowed_actions": ["fireWeapons"],
    })

    assert migrated["allowed_actions"]["fireWeapons"] is True
    assert migrated["allowed_actions"]["plotToTarget"] is True
    assert migrated["allowed_actions"]["setSpeed"] is False


@pytest.mark.parametrize("legacy_value", [None, "invalid", 123])
def test_invalid_legacy_allowed_actions_preserves_allow_all_behavior(
    legacy_value: object,
) -> None:
    assert migrate_allowed_actions(legacy_value) == default_allowed_actions


def test_action_map_merge_adds_new_defaults_and_preserves_user_values() -> None:
    defaults = {
        "allowed_actions": {
            "existingAction": True,
            "newEnabledAction": True,
            "newDisabledAction": False,
        }
    }
    user = {"allowed_actions": {"existingAction": False}}

    assert merge_config_data(defaults, user) == {
        "allowed_actions": {
            "existingAction": False,
            "newEnabledAction": True,
            "newDisabledAction": False,
        }
    }


def test_legacy_backup_update_runs_full_action_migration(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.lib.Config.emit_message",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "src.lib.Config.save_config",
        lambda config: None,
    )
    current = {
        "config_version": 19,
        "allowed_actions": default_allowed_actions.copy(),
    }
    legacy_backup = {
        "config_version": 17,
        "allowed_actions": ["fireWeapons"],
    }

    updated = update_config(current, legacy_backup)  # type: ignore[arg-type]

    assert updated["config_version"] == 19
    assert updated["allowed_actions"]["fireWeapons"] is True
    assert updated["allowed_actions"]["plotToTarget"] is True
    assert updated["allowed_actions"]["setSpeed"] is False


def test_mistral_provider_selection_applies_defaults(monkeypatch) -> None:
    monkeypatch.setattr("src.lib.Config.emit_message", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.lib.Config.save_config", lambda config: None)
    current = {
        "config_version": 19,
        "characters": [{"tts_voice": "nova"}],
    }

    updated = update_config(current, {  # type: ignore[arg-type]
        "llm_provider": "mistral",
        "agent_llm_provider": "mistral",
        "stt_provider": "mistral",
        "tts_provider": "mistral",
    })

    assert updated["llm_endpoint"] == "https://api.mistral.ai/v1"
    assert updated["llm_model_name"] == "mistral-small-latest"
    assert updated["llm_reasoning_effort"] == "none"
    assert updated["llm_temperature"] == 1.0
    assert updated["tools_var"] is True
    assert updated["agent_llm_endpoint"] == "https://api.mistral.ai/v1"
    assert updated["agent_llm_model_name"] == "mistral-medium-latest"
    assert updated["agent_llm_reasoning_effort"] == "none"
    assert updated["agent_llm_temperature"] == 1.0
    assert updated["stt_endpoint"] == "https://api.mistral.ai/v1"
    assert updated["stt_model_name"] == "voxtral-mini-latest"
    assert updated["stt_language"] == ""
    assert updated["tts_endpoint"] == "https://api.mistral.ai/v1"
    assert updated["tts_model_name"] == "voxtral-mini-tts-2603"
    assert updated["characters"][0]["tts_voice"] == "en_paul_neutral"


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
