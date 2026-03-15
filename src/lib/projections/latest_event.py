from typing import Any, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection


class LatestEventState(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


def latest_event_projection_factory(projectionName: str, gameEvent: str):
    class LatestEvent(Projection[LatestEventState]):
        StateModel = LatestEventState

        @override
        def process(self, event: Event) -> None:
            if isinstance(event, GameEvent):
                if gameEvent and event.content.get("event", "") == gameEvent:
                    self.state.data = cast(dict[str, Any], event.content)

    LatestEvent.__name__ = projectionName

    return LatestEvent
