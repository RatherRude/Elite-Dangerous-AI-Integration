from typing import Any, Optional

from ..ActionManager import ActionManager
from ..Config import Config, get_active_characters
from ..EventManager import EventManager


event_manager: Optional[EventManager] = None
config: Optional[Config] = None


def crew_talk(args: dict[str, Any], projected_states: dict[str, Any]) -> str:
    del projected_states

    if event_manager is None or config is None:
        raise Exception("Crew talk is not initialized.")

    active_crew = get_active_characters(config)
    if len(active_crew) <= 1:
        raise Exception("Crew talk requires more than one active character.")

    utterances = args.get("utterances")
    if not isinstance(utterances, list) or not utterances:
        raise Exception("Crew talk requires at least one utterance.")

    crew_by_speaker_id = {
        f"character_{index}": character
        for index, character in active_crew
    }

    queued_count = 0
    for raw_utterance in utterances:
        if not isinstance(raw_utterance, dict):
            raise Exception("Each utterance must be an object.")

        speaker_id = raw_utterance.get("speaker_id")
        text = raw_utterance.get("text")
        if not isinstance(speaker_id, str) or not speaker_id:
            raise Exception("Each utterance must include a speaker_id.")
        if not isinstance(text, str) or not text.strip():
            raise Exception("Each utterance must include non-empty text.")

        character = crew_by_speaker_id.get(speaker_id)
        if character is None:
            available = ", ".join(sorted(crew_by_speaker_id.keys()))
            raise Exception(
                f"Unknown active speaker_id '{speaker_id}'. Available speakers: {available}",
            )

        payload: dict[str, Any] = {
            "event": "QuestEvent",
            "action": "crew_message",
            "speaker_id": speaker_id,
            "transcription": text.strip(),
            "actor_name": character.get("name") or speaker_id,
            "actor_name_color": character.get("color"),
            "avatar_url": character.get("avatar"),
            "voice": character.get("tts_voice"),
        }
        if isinstance(character.get("tts_postprocessing"), dict):
            payload["tts_postprocessing"] = character.get("tts_postprocessing")

        event_manager.add_quest_event(payload)
        queued_count += 1

    return f"Queued {queued_count} crew utterance(s)."


def register_crew_actions(
    action_manager: ActionManager,
    eventManager: EventManager,
    current_config: Config,
) -> None:
    active_crew = get_active_characters(current_config)
    if len(active_crew) <= 1:
        return

    available_speaker_ids = [f"character_{index}" for index, _ in active_crew]

    global event_manager, config
    event_manager = eventManager
    config = current_config

    action_manager.registerAction(
        "crewTalk",
        "Have active crew members speak out loud in sequence. Prefer one crewTalk call for the entire exchange, and reuse the same speaker_id across multiple utterances when a character speaks again later in the same back-and-forth.",
        {
            "type": "object",
            "properties": {
                "utterances": {
                    "type": "array",
                    "description": "Ordered crew utterances for the whole exchange. Put the full back-and-forth into this single list and repeat the same speaker_id whenever that crew member speaks again.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "speaker_id": {
                                "type": "string",
                                "description": "Speaker identifier from the active crew list. Reuse the same speaker_id each time that same crew member speaks again in this sequence.",
                                "enum": available_speaker_ids,
                            },
                            "text": {
                                "type": "string",
                                "description": "The spoken line for that crew member.",
                            },
                        },
                        "required": ["speaker_id", "text"],
                    },
                },
            },
            "required": ["utterances"],
        },
        crew_talk,
        "global",
    )
