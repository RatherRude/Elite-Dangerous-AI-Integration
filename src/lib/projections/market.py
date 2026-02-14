from typing import cast

from typing_extensions import override

from ..Event import Event, GameEvent
from ..EventManager import Projection
from pydantic import BaseModel

from ..EventModels import MarketEvent


class MarketItem(BaseModel):

    Name_Localised: str | None = None
    Name: str | None = None
    Category_Localised: str | None = None
    Category: str | None = None
    BuyPrice: int | None = None
    SellPrice: int | None = None
    MeanPrice: int | None = None
    Stock: int | None = None
    Demand: int | None = None
    DemandBracket: int | None = None
    StockBracket: int | None = None


class MarketState(BaseModel):
    MarketID: int | None = None
    StationName: str | None = None
    StarSystem: str | None = None
    StationType: str | None = None
    CarrierDockingAccess: str | None = None
    Items: list[MarketItem] | None = None
    event: str | None = None
    timestamp: str | None = None


class Market(Projection[MarketState]):
    StateModel = MarketState

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Market":
            payload = cast(MarketEvent, event.content)
            self.state.MarketID = payload.get("MarketID")
            self.state.StationName = payload.get("StationName")
            self.state.StarSystem = payload.get("StarSystem")
            self.state.StationType = payload.get("StationType")
            self.state.CarrierDockingAccess = payload.get("CarrierDockingAccess")
            self.state.event = payload.get("event")
            self.state.timestamp = payload.get("timestamp")
            raw = cast(dict[str, object], event.content)
            items = raw.get("Items")
            if isinstance(items, list):
                self.state.Items = [MarketItem(**item) for item in items]
