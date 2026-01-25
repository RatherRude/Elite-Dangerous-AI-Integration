from datetime import datetime, timezone, timedelta
from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent
from ..EventModels import FetchRemoteModuleEvent, StoredModulesEvent
from ..EventManager import Projection


class StoredModuleItem(BaseModel):
    """A module stored at a station or in transit."""
    Name: str = Field(description="Module internal name")
    Name_Localised: str = Field(description="Human-readable module name")
    StorageSlot: int = Field(description="Storage slot identifier")
    BuyPrice: int = Field(description="Original purchase price in credits")
    Hot: bool = Field(description="Whether module is marked as hot/stolen")
    InTransit: Optional[bool] = Field(default=None, description="Whether module is in transit")
    StarSystem: Optional[str] = Field(default=None, description="System where module is stored")
    MarketID: Optional[int] = Field(default=None, description="Market ID where module is stored")
    TransferCost: Optional[int] = Field(default=None, description="Cost to transfer module in credits")
    TransferTime: Optional[int] = Field(default=None, description="Time to transfer module in seconds")
    EngineerModifications: Optional[str] = Field(default=None, description="Applied engineering modifications")
    Level: Optional[int] = Field(default=None, description="Engineering level")
    Quality: Optional[float] = Field(default=None, description="Engineering quality")


class FetchRemoteModuleItem(BaseModel):
    """A module being transferred to current location."""
    Name: str = Field(description="Name of the module")
    MarketID: int = Field(description="Destination market ID")
    StationName: str = Field(description="Destination station name")
    StarSystem: str = Field(description="Destination star system")
    StorageSlot: int = Field(description="Storage slot identifier")
    TransferCompleteTime: str = Field(description="ISO timestamp when transfer completes")
    TransferCost: int = Field(description="Transfer cost in credits")


class StoredModulesStateModel(BaseModel):
    """Current stored modules status."""
    MarketID: int = Field(default=0, description="Current market ID")
    StationName: str = Field(default="", description="Current station name")
    StarSystem: str = Field(default="", description="Current star system")
    Items: list[StoredModuleItem] = Field(default_factory=list, description="Stored modules")
    ItemsInTransit: list[FetchRemoteModuleItem] = Field(default_factory=list, description="Modules in transit")


class StoredModules(Projection[StoredModulesStateModel]):
    StateModel = StoredModulesStateModel

    def _get_event_time(self, event: Event | None) -> datetime:
        if isinstance(event, GameEvent) and "timestamp" in event.content:
            return datetime.fromisoformat(event.content.get("timestamp", "").replace("Z", "+00:00"))
        return datetime.now(timezone.utc)

    def _complete_transfers(self, current_time: datetime) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if self.state.ItemsInTransit:
            completed_items: list[FetchRemoteModuleItem] = []

            for transit_item in list(self.state.ItemsInTransit):
                completion_time = datetime.fromisoformat(transit_item.TransferCompleteTime)
                if current_time >= completion_time:
                    completed_items.append(transit_item)

            # Process completed transfers
            for completed in completed_items:
                # Find the item in Items with matching StorageSlot and update it
                for item in self.state.Items:
                    if item.StorageSlot == completed.StorageSlot:
                        # Add location information
                        item.StarSystem = completed.StarSystem
                        item.MarketID = completed.MarketID
                        item.TransferCost = completed.TransferCost
                        item.TransferTime = 0  # Transfer is complete
                        break

                # Remove from ItemsInTransit
                self.state.ItemsInTransit.remove(completed)
                projected_events.append(ProjectedEvent(content={
                    "event": "FetchRemoteModuleCompleted",
                    "StorageSlot": completed.StorageSlot,
                    "ModuleName": completed.Name,
                    "StationName": completed.StationName,
                    "StarSystem": completed.StarSystem,
                    "MarketID": completed.MarketID,
                }))

        return projected_events

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, GameEvent) and event.content.get("event") == "StoredModules":
            # Save the event as-is (all fields are required in the event)
            payload = cast(StoredModulesEvent, event.content)
            self.state.MarketID = payload.get("MarketID", 0)
            self.state.StationName = payload.get("StationName", "")
            self.state.StarSystem = payload.get("StarSystem", "")
            items: list[StoredModuleItem] = []
            for item in payload.get("Items", []):
                items.append(
                    StoredModuleItem(
                        Name=item.get("Name", "") if isinstance(item.get("Name"), str) else "",
                        Name_Localised=item.get("Name_Localised", "") if isinstance(item.get("Name_Localised"), str) else "",
                        StorageSlot=item.get("StorageSlot", 0) if isinstance(item.get("StorageSlot"), int) else 0,
                        BuyPrice=item.get("BuyPrice", 0) if isinstance(item.get("BuyPrice"), int) else 0,
                        Hot=item.get("Hot", False) if isinstance(item.get("Hot"), bool) else False,
                        InTransit=item.get("InTransit") if isinstance(item.get("InTransit"), bool) else None,
                        StarSystem=item.get("StarSystem") if isinstance(item.get("StarSystem"), str) else None,
                        MarketID=item.get("MarketID") if isinstance(item.get("MarketID"), int) else None,
                        TransferCost=item.get("TransferCost") if isinstance(item.get("TransferCost"), int) else None,
                        TransferTime=item.get("TransferTime") if isinstance(item.get("TransferTime"), int) else None,
                        EngineerModifications=item.get("EngineerModifications") if isinstance(item.get("EngineerModifications"), str) else None,
                        Level=item.get("Level") if isinstance(item.get("Level"), int) else None,
                        Quality=item.get("Quality") if isinstance(item.get("Quality"), (int, float)) else None,
                    )
                )
            self.state.Items = items

        if isinstance(event, GameEvent) and event.content.get("event") == "FetchRemoteModule":
            payload = cast(FetchRemoteModuleEvent, event.content)
            # Calculate completion timestamp using the event's timestamp
            transfer_time_seconds = payload.get("TransferTime", 0)
            if not isinstance(transfer_time_seconds, int):
                transfer_time_seconds = 0
            event_timestamp = datetime.fromisoformat(
                payload.get("timestamp", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
            )
            completion_time = event_timestamp + timedelta(seconds=transfer_time_seconds)
            now_utc = datetime.now(timezone.utc)
            is_due = completion_time <= now_utc

            # Create an item in transit using data from the event and current state
            transit_item = FetchRemoteModuleItem(
                Name=payload.get("StoredItem_Localised", "") if isinstance(payload.get("StoredItem_Localised"), str) else "",
                MarketID=self.state.MarketID,
                StationName=self.state.StationName,
                StarSystem=self.state.StarSystem,
                StorageSlot=payload.get("StorageSlot", 0) if isinstance(payload.get("StorageSlot"), int) else 0,
                TransferCompleteTime=completion_time.isoformat(),
                TransferCost=payload.get("TransferCost", 0) if isinstance(payload.get("TransferCost"), int) else 0,
            )

            if not any(i.StorageSlot == transit_item.StorageSlot for i in self.state.ItemsInTransit):
                self.state.ItemsInTransit.append(transit_item)
                if is_due:
                    projected_events.extend(self._complete_transfers(now_utc))

        # Check if any items in transit have completed
        # current_time = self._get_event_time(event)
        # projected_events.extend(self._complete_transfers(current_time))

        return projected_events

    @override
    def process_timer(self) -> list[ProjectedEvent]:
        current_time = datetime.now(timezone.utc)
        return self._complete_transfers(current_time)
