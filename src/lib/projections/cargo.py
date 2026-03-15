from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, StatusEvent
from ..EventManager import Projection
from ..EventModels import CargoEvent, LoadoutEvent
from ..StatusParser import Status


class CargoItem(BaseModel):
    """An item in the ship's cargo hold."""
    Name_Localised: str | None = Field(default=None, description="Localized item name")
    Name: str = Field(description="Name of the cargo item")
    Count: int = Field(default=0, description="Quantity of this item")
    Stolen: bool = Field(default=False, description="Whether this cargo is stolen")


class CargoState(BaseModel):
    """Current state of the ship's cargo hold."""
    event: str | None = Field(default=None, description="Event type")
    timestamp: str | None = Field(default=None, description="Event timestamp")
    Inventory: list[CargoItem] = Field(default_factory=list, description="List of cargo items")
    TotalItems: int = Field(default=0, description="Total cargo items count")
    Capacity: int = Field(default=0, description="Maximum cargo capacity")
    Vessel: str | None = Field(default=None, description="Cargo vessel (Ship/SRV)")


class Cargo(Projection[CargoState]):
    StateModel = CargoState

    @override
    def process(self, event: Event) -> None:
        # Process Cargo event
        if isinstance(event, GameEvent) and event.content.get("event") == "Cargo":
            payload = cast(CargoEvent, event.content)
            self.state.event = payload.get("event")
            self.state.timestamp = payload.get("timestamp")
            self.state.Vessel = payload.get("Vessel")
            if "Inventory" in payload:
                self.state.Inventory = []
                inventory = payload["Inventory"]
                for item in inventory:
                    self.state.Inventory.append(
                        CargoItem(
                            Name=item.get("Name_Localised", item.get("Name", "Unknown")),
                            Count=item.get("Count", 0),
                            Stolen=item.get("Stolen", 0) > 0,
                        )
                    )

            if "Count" in payload:
                self.state.TotalItems = int(payload["Count"])

        # Get cargo capacity from Loadout event
        if isinstance(event, GameEvent) and event.content.get("event") == "Loadout":
            payload = cast(LoadoutEvent, event.content)
            self.state.Capacity = int(payload["CargoCapacity"])

        # Update from Status event
        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            status = cast(Status, event.status)
            cargo_value = status.get("Cargo")
            if cargo_value is not None:
                self.state.TotalItems = int(cargo_value)
