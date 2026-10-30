from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.Event import ConversationEvent, Event, GameEvent, GameEventContent
from src.lib.PromptGenerator import PromptGenerator
from src.lib.SystemDatabase import SystemDatabase


class StationEventContent(GameEventContent):
    StationName: str


@pytest.fixture
def prompt_generator(monkeypatch: pytest.MonkeyPatch) -> PromptGenerator:
    monkeypatch.setattr("src.lib.PromptGenerator.QuestDatabase", Mock())
    return PromptGenerator(
        commander_name="Test Commander",
        character_prompt="You assist {commander_name}.",
        important_game_events=["Undocked"],
        system_db=Mock(spec=SystemDatabase),
    )


def test_undocked_event_does_not_imply_station_exit(prompt_generator: PromptGenerator) -> None:
    payload: StationEventContent = {
        "event": "Undocked",
        "timestamp": "2026-10-30T15:52:08Z",
        "StationName": "Test Station",
    }
    event = GameEvent(content=payload, historic=False)

    message = prompt_generator.get_event_template(event)

    assert message is not None
    assert "Test Commander has been released from the landing pad at Test Station" in message
    assert "does not confirm that the ship has exited the station" in message
    assert "Do not change throttle or boost solely in response to this event" in message


def test_launch_prompt_requires_explicit_request_for_additional_flight_actions(
    prompt_generator: PromptGenerator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prompt_generator, "generate_status_message", Mock(return_value="Ship status"))
    events: list[Event] = [ConversationEvent(kind="user", content="OK, take off.")]

    prompt, _ = prompt_generator.generate_prompt(
        events=events,
        projected_states={},
        pending_events=events,
        memories=[],
    )

    assert prompt[0]["role"] == "system"
    system_prompt = prompt[0]["content"]
    assert "A request to launch, undock or lift off alone does not authorize throttle changes or boost" in system_prompt
    assert "Do not follow liftoff or an Undocked event with setSpeed or engineBoost unless the commander explicitly requested that additional action" in system_prompt
    assert "leave any automated undocking in control" in system_prompt
