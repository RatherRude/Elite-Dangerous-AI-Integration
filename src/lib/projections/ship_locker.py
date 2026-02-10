from typing import cast

from typing_extensions import override

from ..Event import Event, GameEvent
from ..EventManager import Projection
from pydantic import BaseModel, Field

from ..EventModels import ShipLockerEvent


class ShipLockerConsumable(BaseModel):
    Count: int
    OwnerID: int
    Name_Localised: str
    Name: str
    MissionID: int | None = None


class ShipLockerComponent(BaseModel):
    Count: int
    OwnerID: int
    Name_Localised: str | None = None
    Name: str
    MissionID: int | None = None


class ShipLockerData(BaseModel):
    Count: int
    OwnerID: int
    Name_Localised: str | None = None
    Name: str
    MissionID: int | None = None


class ShipLockerItem(BaseModel):
    OwnerID: int
    MissionID: int | None = None
    Name_Localised: str | None = None
    Name: str
    Count: int


class ShipLockerState(BaseModel):
    Consumables: list[ShipLockerConsumable] | None = Field(default=None)
    Components: list[ShipLockerComponent] | None = Field(default=None)
    Data: list[ShipLockerData] | None = Field(default=None)
    Items: list[ShipLockerItem] | None = Field(default=None)
    event: str | None = None
    timestamp: str | None = None


class ShipLocker(Projection[ShipLockerState]):
    StateModel = ShipLockerState

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "ShipLocker":
            payload = cast(ShipLockerEvent, event.content)
            self.state.event = payload.get("event")
            self.state.timestamp = payload.get("timestamp")
            self.state.Consumables = [ShipLockerConsumable(**item) for item in payload.get("Consumables", [])]
            self.state.Components = [ShipLockerComponent(**item) for item in payload.get("Components", [])]
            self.state.Data = [ShipLockerData(**item) for item in payload.get("Data", [])]
            self.state.Items = [ShipLockerItem(**item) for item in payload.get("Items", [])]
