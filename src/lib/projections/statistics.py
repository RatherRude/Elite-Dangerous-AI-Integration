from typing import Any

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection


class StatisticsStateModel(BaseModel):
    """Commander statistics payload."""
    Data: dict[str, Any] = Field(default_factory=dict, description="Statistics data payload")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last statistics event")


class Statistics(Projection[StatisticsStateModel]):
    StateModel = StatisticsStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Statistics":
            self.state.Data = {
                key: value
                for key, value in event.content.items()
                if key not in ("event", "timestamp")
            }
            if "timestamp" in event.content:
                self.state.Timestamp = event.content["timestamp"]
