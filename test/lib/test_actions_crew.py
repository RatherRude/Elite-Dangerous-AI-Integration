import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.actions.actions_crew import register_crew_actions


class FakeActionManager:
    def __init__(self):
        self.calls = []

    def registerAction(self, name, description, parameters, method, action_type="ship"):
        self.calls.append(
            {
                "name": name,
                "description": description,
                "parameters": parameters,
                "method": method,
                "action_type": action_type,
            }
        )


def test_register_crew_actions_sets_speaker_id_enum():
    action_manager = FakeActionManager()
    config = {
        "characters": [
            {"name": "COVAS"},
            {"name": "Spare"},
            {"name": "Nyx"},
        ],
        "active_character_index": 0,
        "active_characters": [0, 2],
    }

    register_crew_actions(action_manager, MagicMock(), config)

    assert len(action_manager.calls) == 1
    speaker_id_schema = action_manager.calls[0]["parameters"]["properties"]["utterances"]["items"]["properties"]["speaker_id"]
    assert speaker_id_schema["enum"] == ["character_0", "character_2"]


def test_register_crew_actions_skips_registration_without_multicrew():
    action_manager = FakeActionManager()
    config = {
        "characters": [{"name": "COVAS"}],
        "active_character_index": 0,
        "active_characters": [0],
    }

    register_crew_actions(action_manager, MagicMock(), config)

    assert action_manager.calls == []
