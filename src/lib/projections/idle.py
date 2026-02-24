from datetime import datetime, timezone

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import ConversationEvent, Event, GameEvent, ProjectedEvent, StatusEvent
from ..EventManager import Projection


class IdleStateModel(BaseModel):
    """Commander's activity/idle status."""
    LastInteraction: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last user interaction")
    IsIdle: bool = Field(default=True, description="Whether the user is currently idle")


class Idle(Projection[IdleStateModel]):
    StateModel = IdleStateModel

    def __init__(self, idle_timeout: int):
        super().__init__()
        self.idle_timeout = idle_timeout

    def _check_idle_timeout(self, current_dt: datetime) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        last_interaction = self.state.LastInteraction
        last_dt = datetime.fromisoformat(last_interaction.replace("Z", "+00:00"))
        time_delta = (current_dt - last_dt).total_seconds()

        if time_delta > self.idle_timeout and self.state.IsIdle is False:
            self.state.IsIdle = True
            projected_events.append(ProjectedEvent(content={"event": "Idle"}))

        return projected_events

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, ConversationEvent):
            self.state.LastInteraction = event.timestamp
            self.state.IsIdle = False

        if isinstance(event, (StatusEvent, GameEvent)) and self.state.IsIdle is False:
            current_dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            projected_events.extend(self._check_idle_timeout(current_dt))

        return projected_events

    @override
    def process_timer(self) -> list[ProjectedEvent]:
        if self.state.IsIdle:
            return []

        current_dt = datetime.now(timezone.utc)
        return self._check_idle_timeout(current_dt)
