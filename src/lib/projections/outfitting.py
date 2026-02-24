from typing import cast

from typing_extensions import override

from ..Event import Event, GameEvent
from ..EventManager import Projection
from pydantic import BaseModel

from ..EventModels import OutfittingEvent


class OutfittingItem(BaseModel):

    Name: str | None = None
    Name_Localised: str | None = None
    Slot: str | None = None
    Class: int | None = None
    Rating: str | None = None
    Price: int | None = None


class OutfittingState(BaseModel):
    MarketID: int | None = None
    StationName: str | None = None
    StarSystem: str | None = None
    Items: list[OutfittingItem] | None = None
    event: str | None = None
    timestamp: str | None = None


class Outfitting(Projection[OutfittingState]):
    StateModel = OutfittingState

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Outfitting":
            payload = cast(OutfittingEvent, event.content)
            self.state.MarketID = payload.get("MarketID")
            self.state.StationName = payload.get("StationName")
            self.state.StarSystem = payload.get("StarSystem")
            self.state.event = payload.get("event")
            self.state.timestamp = payload.get("timestamp")
            raw = cast(dict[str, object], event.content)
            items = raw.get("Items")
            if isinstance(items, list):
                self.state.Items = [OutfittingItem(**item) for item in items]
