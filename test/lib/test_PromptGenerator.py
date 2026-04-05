import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.PromptGenerator import PromptGenerator


def make_prompt_generator(monkeypatch, active_characters=None):
    monkeypatch.setattr("src.lib.PromptGenerator.QuestDatabase", MagicMock(return_value=MagicMock()))
    return PromptGenerator(
        commander_name="Rude",
        character_prompt="I am {commander_name}'s main ship voice.",
        important_game_events=[],
        system_db=MagicMock(),
        active_characters=active_characters,
    )


def test_get_character_prompt_block_uses_main_prompt_with_one_active_character(monkeypatch):
    generator = make_prompt_generator(
        monkeypatch,
        active_characters=[
            {
                "speaker_id": "character_0",
                "name": "COVAS",
                "is_primary": True,
                "character_prompt": "I am {commander_name}'s main ship voice.",
            },
        ],
    )

    prompt_block = generator.get_character_prompt_block()

    assert prompt_block == "Your character prompt is: I am Rude's main ship voice."
    assert "Crew roster:" not in prompt_block


def test_get_character_prompt_block_uses_multicrew_roster_when_multiple_active_characters(monkeypatch):
    generator = make_prompt_generator(
        monkeypatch,
        active_characters=[
            {
                "speaker_id": "character_0",
                "name": "COVAS",
                "is_primary": True,
                "character_prompt": "I am {commander_name}'s main ship voice.",
            },
            {
                "speaker_id": "character_2",
                "name": "Nyx",
                "is_primary": False,
                "character_prompt": "I am the gunner covering {commander_name}.",
            },
        ],
    )

    prompt_block = generator.get_character_prompt_block()

    assert "Your character prompt is:" not in prompt_block
    assert "Multicrew is active" in prompt_block
    assert "Crew roster by speaker_id for crewTalk:" in prompt_block
    assert "character_0 -> COVAS (primary): I am Rude's main ship voice." in prompt_block
    assert "character_2 -> Nyx (active): I am the gunner covering Rude." in prompt_block
