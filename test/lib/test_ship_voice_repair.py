from unittest.mock import MagicMock, patch

import pytest

from src.lib.Assistant import Assistant
from src.lib.Config import TTS_ENVIRONMENT_EFFECTS_OVERHEATING, default_event_reactions
from src.lib.Event import GameEvent, ProjectedEvent
from src.lib.PromptGenerator import PromptGenerator
from src.lib.projections.current_status import CurrentStatusState
from src.lib.projections.loadout import Loadout, LoadoutState


def apply_event(loadout, name, **fields):
    event = GameEvent(content={"event": name, "timestamp": "", **fields}, historic=False)
    return [projected.content["event"] for projected in loadout.process(event)]


@pytest.mark.parametrize("repair_event", ["RepairDrone", "RebootRepair"])
def test_voice_damage_and_repair_leave_hull_independent(repair_event):
    loadout = Loadout()
    assert apply_event(loadout, "Loadout", HullHealth=0.9) == []
    assert apply_event(loadout, "HullDamage", Health=0.3, Fighter=True) == []
    assert loadout.state.HullHealth == loadout.state.VoiceHealth == 0.9
    assert apply_event(loadout, "HullDamage", Health=0.75) == ["VoiceDamaged"]
    assert apply_event(loadout, "HullDamage", Health=0.5) == []
    assert apply_event(loadout, repair_event) == ["VoiceRepaired"]
    assert loadout.state.HullHealth == 0.5
    assert loadout.state.VoiceHealth == 1.0
    assert apply_event(loadout, repair_event) == []
    assert apply_event(loadout, "HullDamage", Health=0.45) == ["VoiceDamaged"]


def test_missing_health_does_not_create_a_transition_or_erase_known_voice_health():
    loadout = Loadout()
    assert apply_event(loadout, "Loadout") == []
    assert apply_event(loadout, "HullDamage") == []
    assert loadout.state.VoiceHealth is None
    assert apply_event(loadout, "HullDamage", Health=0.5) == []
    assert apply_event(loadout, "HullDamage") == []
    assert loadout.state.VoiceHealth == 0.5
    assert apply_event(Loadout(), "RepairDrone") == []


@pytest.mark.parametrize("reset_event", ["RepairAll", "Died"])
def test_full_hull_reset_also_resets_voice(reset_event):
    loadout = Loadout()
    apply_event(loadout, "Loadout", HullHealth=0.5)
    assert apply_event(loadout, reset_event) == []
    assert loadout.state.HullHealth == loadout.state.VoiceHealth == 1.0


def test_voice_effects_and_prompt_status_use_voice_health_not_hull_health():
    assistant = Assistant.__new__(Assistant)
    assistant.config = {"characters": [{}]}
    with patch("src.lib.PromptGenerator.QuestDatabase"):
        prompt = PromptGenerator("Jameson", "", [], MagicMock())
    loadout = Loadout()
    loadout.state = LoadoutState.model_validate({"HullHealth": 0.75})
    states = {"Loadout": loadout.state, "CurrentStatus": CurrentStatusState()}

    assert len(assistant._get_environment_tts_postprocessing_layers(states)) == 1
    assert "Voice Module Damaged" in prompt.generate_status_message(states)
    assistant.config["characters"][0]["tts_environment_damage_effects_var"] = False
    assert assistant._get_environment_tts_postprocessing_layers(states) == []
    assistant.config["characters"][0]["tts_environment_damage_effects_var"] = True

    apply_event(loadout, "RebootRepair")
    assert assistant._get_environment_tts_postprocessing_layers(states) == []
    assert "Voice Module Damaged" not in prompt.generate_status_message(states)
    assert assistant._get_environment_tts_postprocessing_layers(
        {**states, "CurrentStatus": CurrentStatusState(flags={"OverHeating": True})}
    ) == [TTS_ENVIRONMENT_EFFECTS_OVERHEATING]


@pytest.mark.parametrize(("name", "change"), [("VoiceDamaged", "damaged"), ("VoiceRepaired", "repaired")])
def test_voice_events_are_enabled_and_name_the_commander(name, change):
    prompt = PromptGenerator.__new__(PromptGenerator)
    prompt.commander_name = "Jameson"
    event = ProjectedEvent(content={"event": name})
    assert default_event_reactions[name] == "on"
    assert prompt.get_event_template(event).startswith(f"Jameson's voice module has been {change};")
