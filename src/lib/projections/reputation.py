from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import ReputationEvent


class ReputationStateModel(BaseModel):
    """Faction reputation values."""
    Empire: float = Field(default=0.0, description="Reputation with the Empire")
    Federation: float = Field(default=0.0, description="Reputation with the Federation")
    Alliance: float = Field(default=0.0, description="Reputation with the Alliance")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last reputation event")


class Reputation(Projection[ReputationStateModel]):
    StateModel = ReputationStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Reputation":
            payload = cast(ReputationEvent, event.content)
            # Always default missing values to 0.0
            self.state.Empire = payload.get("Empire", 0.0)
            self.state.Federation = payload.get("Federation", 0.0)
            self.state.Alliance = payload.get("Alliance", 0.0)
            self.state.Timestamp = payload.get("timestamp", self.state.Timestamp)
