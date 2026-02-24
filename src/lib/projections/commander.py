from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import CommanderEvent


class CommanderStateModel(BaseModel):
    """Commander identity details."""
    FID: str = Field(default="Unknown", description="Frontier ID")
    Name: str = Field(default="Unknown", description="Commander name")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last commander event")


class Commander(Projection[CommanderStateModel]):
    StateModel = CommanderStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Commander":
            payload = cast(CommanderEvent, event.content)
            self.state.FID = payload.get("FID", "Unknown")
            self.state.Name = payload.get("Name", "Unknown")
            self.state.Timestamp = payload.get("timestamp", self.state.Timestamp)
