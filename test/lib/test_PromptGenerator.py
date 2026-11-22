from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.lib.PromptGenerator import PromptGenerator
from src.lib.Event import ConversationEvent, PluginEvent


def test_history_uses_recorded_speakers_and_renders_external_dialogue_once(monkeypatch):
    generator = PromptGenerator.__new__(PromptGenerator)
    generator.commander_name = 'Commander'
    generator.character_prompt = 'Pilot the ship.'
    generator.registered_prompt_event_handlers = []
    monkeypatch.setattr(generator, 'generate_status_message', lambda states: 'Status')
    generator.register_prompt_event_handler(lambda event: event.plugin_event_content['text']
                                            if isinstance(event, PluginEvent) else None)
    events = [
        ConversationEvent(kind='user', content='Report.'),
        ConversationEvent(kind='assistant', content='Legacy reply.'),
        ConversationEvent(kind='assistant', character_name='Pilot', content='Standing by.'),
        ConversationEvent(kind='assistant', character_name='Navigator', content='Course set.'),
        ConversationEvent(kind='assistant', character_name='Tower Seven', plugin_guid='tower',
                          plugin_event_name='TowerNotice', content='Pad clear.'),
        PluginEvent(plugin_event_name='TowerNotice', plugin_event_content={'text': 'Pad clear.'}, has_conversation_line=True),
        PluginEvent(plugin_event_name='TowerNotice', plugin_event_content={'text': 'Beacon offline.'}),
        ConversationEvent(kind='assistant', plugin_guid='tower', content='Channel closed.'),
    ]
    prompt, _ = generator.generate_prompt(events, {}, events, [])
    assert prompt[2:] == [
        {'role': 'user', 'content': 'Report.'},
        {'role': 'assistant', 'content': 'Legacy reply.'},
        {'role': 'assistant', 'content': '[Speaker: Pilot] Standing by.'},
        {'role': 'assistant', 'content': '[Speaker: Navigator] Course set.'},
        {'role': 'user', 'content': '[Speaker: Tower Seven] Pad clear.'},
        {'role': 'user', 'content': '[External Event, less than a minute ago] Beacon offline.'},
        {'role': 'user', 'content': '[Speaker: Unknown] Channel closed.'},
    ]


@pytest.mark.parametrize("raw_format", [False, True], ids=["projection", "raw-api"])
@pytest.mark.parametrize(
    ("government_fields", "expected_government", "engineer"),
    [
        pytest.param({}, "Federation None", False, id="missing"),
        pytest.param({"government": None}, "Federation None", False, id="null"),
        pytest.param({"government": ""}, "Federation ", False, id="empty"),
        pytest.param({"government": "Corporate"}, "Federation Corporate", False, id="corporate"),
        pytest.param({"government": " Engineer "}, "Federation  Engineer ", True, id="padded-engineer"),
        pytest.param({"government": "eNgInEeR"}, "Federation eNgInEeR", True, id="mixed-case-engineer"),
    ],
)
def test_format_stations_data_handles_optional_government(
    raw_format, government_fields, expected_government, engineer
):
    generator = PromptGenerator.__new__(PromptGenerator)
    station = {
        "name": "Test station",
        "type": "Coriolis Starport",
        "economy": "Industrial",
        "allegiance": "Federation",
        "controllingFaction": "Test faction",
        "materialTrader": "Raw",
        "technologyBroker": "Guardian",
        **government_fields,
    }
    if raw_format:
        station["haveMarket"] = True
        stations_data = {"stations": [station]}
        expected_services = ["market"]
    else:
        station["services"] = ["Market"]
        stations_data = [station]
        expected_services = ["Market"]
    if engineer:
        expected_services.append("Engineer")
    expected_services.extend(["Raw Material Trader", "Guardian Technology Broker"])

    assert generator.format_stations_data(stations_data) == {
        "In Orbit around Primary Star": {
            "Coriolis Starport": [
                {
                    "name": "Test station",
                    "economy": "Industrial",
                    "services": expected_services,
                    "government": expected_government,
                    "controllingFaction": "Test faction",
                }
            ]
        }
    }
