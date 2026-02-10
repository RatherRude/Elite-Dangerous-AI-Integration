from typing import cast

from typing_extensions import override

from ..Event import Event, GameEvent
from ..EventManager import Projection
from pydantic import BaseModel

from ..EventModels import ShipyardEvent


class ShipyardShip(BaseModel):

    ShipType: str | None = None
    ShipType_Localised: str | None = None
    ShipID: int | None = None
    Value: int | None = None
    Hot: bool | None = None
    ShipName: str | None = None
    HullValue: int | None = None
    ModulesValue: int | None = None
    Rebuy: int | None = None


class ShipyardState(BaseModel):
    MarketID: int | None = None
    StationName: str | None = None
    StarSystem: str | None = None
    Ships: list[ShipyardShip] | None = None
    event: str | None = None
    timestamp: str | None = None


class Shipyard(Projection[ShipyardState]):
    StateModel = ShipyardState

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Shipyard":
            payload = cast(ShipyardEvent, event.content)
            self.state.MarketID = payload.get("MarketID")
            self.state.StationName = payload.get("StationName")
            self.state.StarSystem = payload.get("StarSystem")
            self.state.event = payload.get("event")
            self.state.timestamp = payload.get("timestamp")
            raw = cast(dict[str, object], event.content)
            ships = raw.get("Ships")
            if isinstance(ships, list):
                self.state.Ships = [ShipyardShip(**ship) for ship in ships]
