from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent
from ..EventModels import MusicEvent
from ..EventManager import Projection


class InCombatStateModel(BaseModel):
    """Combat status of the commander."""
    InCombat: bool = Field(default=False, description="Whether commander is currently in combat")


class InCombat(Projection[InCombatStateModel]):
    StateModel = InCombatStateModel

    @override
    def process(self, event: Event) -> list[ProjectedEvent] | None:
        projected_events: list[ProjectedEvent] = []

        # Process Music events
        if isinstance(event, GameEvent) and event.content.get("event") == "Music":
            payload = cast(MusicEvent, event.content)
            music_track = payload.get("MusicTrack", "")
            if not isinstance(music_track, str):
                music_track = ""

            # Skip if missing music track information
            if not music_track:
                return None

            # Determine if this is a combat music track (starts with "combat")
            is_combat_music = music_track.lower().startswith("combat")

            # Check for transition from combat to non-combat
            if self.state.InCombat and not is_combat_music:
                # Generate a projected event for leaving combat
                projected_events.append(ProjectedEvent(content={"event": "CombatExited"}))
                self.state.InCombat = False
            # Check for transition from non-combat to combat
            elif not self.state.InCombat and is_combat_music:
                # Generate a projected event for entering combat
                projected_events.append(ProjectedEvent(content={"event": "CombatEntered"}))
                self.state.InCombat = True

        return projected_events
