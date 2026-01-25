from datetime import datetime, timezone, timedelta
from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent
from ..EventModels import ShipyardTransferEvent, StoredShipsEvent
from ..EventManager import Projection


class ShipHereItem(BaseModel):
    """A ship stored at the current station."""
    ShipID: int = Field(description="Unique ship identifier")
    ShipType: str = Field(description="Ship type identifier")
    Name: str = Field(description="Custom ship name")
    Value: int = Field(description="Ship value in credits")
    Hot: bool = Field(description="Whether ship is marked as hot/stolen")


class ShipRemoteItem(BaseModel):
    """A ship stored at a remote location."""
    ShipID: int = Field(description="Unique ship identifier")
    ShipType: str = Field(description="Ship type identifier")
    ShipType_Localised: Optional[str] = Field(default=None, description="Human-readable ship type")
    Name: str = Field(description="Custom ship name")
    StarSystem: Optional[str] = Field(default=None, description="System where ship is stored")
    ShipMarketID: Optional[int] = Field(default=None, description="Market ID where ship is stored")
    TransferPrice: Optional[int] = Field(default=None, description="Cost to transfer ship in credits")
    TransferTime: Optional[int] = Field(default=None, description="Time to transfer ship in seconds")
    Value: int = Field(description="Ship value in credits")
    Hot: bool = Field(description="Whether ship is marked as hot/stolen")
    InTransit: Optional[bool] = Field(default=None, description="Whether ship is in transit")


class ShipInTransitItem(BaseModel):
    """A ship being transferred to current location."""
    ShipID: int = Field(description="Unique ship identifier")
    ShipType: str = Field(description="Ship type identifier")
    System: str = Field(description="Destination star system")
    ShipMarketID: int = Field(description="Destination market ID")
    TransferCompleteTime: str = Field(description="ISO timestamp when transfer completes")
    TransferPrice: int = Field(description="Transfer cost in credits")


class StoredShipsStateModel(BaseModel):
    """Current stored ships status."""
    StationName: str = Field(default="", description="Current station name")
    MarketID: int = Field(default=0, description="Current market ID")
    StarSystem: str = Field(default="", description="Current star system")
    ShipsHere: list[ShipHereItem] = Field(default_factory=list, description="Ships at current station")
    ShipsRemote: list[ShipRemoteItem] = Field(default_factory=list, description="Ships at remote locations")
    ShipsInTransit: list[ShipInTransitItem] = Field(default_factory=list, description="Ships in transit")


class StoredShips(Projection[StoredShipsStateModel]):
    StateModel = StoredShipsStateModel

    def _get_event_time(self, event: Event | None) -> datetime:
        if isinstance(event, GameEvent) and "timestamp" in event.content:
            return datetime.fromisoformat(event.content.get("timestamp", "").replace("Z", "+00:00"))
        return datetime.now(timezone.utc)

    def _complete_transfers(self, current_time: datetime) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if self.state.ShipsInTransit:
            completed_items: list[ShipInTransitItem] = []

            for transit_item in list(self.state.ShipsInTransit):
                completion_time = datetime.fromisoformat(transit_item.TransferCompleteTime)
                if current_time >= completion_time:
                    completed_items.append(transit_item)

            # Process completed transfers
            for completed in completed_items:
                ship_id = completed.ShipID

                # Find the ship in ShipsRemote with matching ShipID and update it
                ship_name: str | None = None
                ship_type: str | None = None
                for ship in self.state.ShipsRemote:
                    if ship.ShipID == ship_id:
                        ship_name = ship.Name
                        ship_type = ship.ShipType
                        # Remove in-transit flag if present
                        ship.InTransit = None

                        # Add location information
                        ship.StarSystem = completed.System
                        ship.ShipMarketID = completed.ShipMarketID
                        ship.TransferPrice = completed.TransferPrice
                        ship.TransferTime = 0  # Transfer is complete
                        break

                # Remove from ShipsInTransit
                self.state.ShipsInTransit.remove(completed)
                projected_events.append(ProjectedEvent(content={
                    "event": "ShipyardTransferCompleted",
                    "ShipID": ship_id,
                    "ShipType": ship_type or "",
                    "ShipName": ship_name or "",
                    "StarSystem": completed.System,
                    "ShipMarketID": completed.ShipMarketID,
                    "TransferPrice": completed.TransferPrice,
                }))

        return projected_events

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, GameEvent) and event.content.get("event") == "StoredShips":
            # Save the event as-is (all fields are required in the event)
            payload = cast(StoredShipsEvent, event.content)
            self.state.StationName = payload.get("StationName", "")
            self.state.MarketID = payload.get("MarketID", 0)
            self.state.StarSystem = payload.get("StarSystem", "")
            ships_here: list[ShipHereItem] = []
            for ship in payload.get("ShipsHere", []):
                ships_here.append(
                    ShipHereItem(
                    ShipID=ship.get("ShipID", 0) if isinstance(ship.get("ShipID"), int) else 0,
                    ShipType=ship.get("ShipType", "") if isinstance(ship.get("ShipType"), str) else "",
                    Name=ship.get("Name", "") if isinstance(ship.get("Name"), str) else "",
                    Value=ship.get("Value", 0) if isinstance(ship.get("Value"), int) else 0,
                        Hot=ship.get("Hot", False) if isinstance(ship.get("Hot"), bool) else False,
                    )
                )
            self.state.ShipsHere = ships_here

            ships_remote: list[ShipRemoteItem] = []
            for ship in payload.get("ShipsRemote", []):
                ships_remote.append(
                    ShipRemoteItem(
                    ShipID=ship.get("ShipID", 0) if isinstance(ship.get("ShipID"), int) else 0,
                    ShipType=ship.get("ShipType", "") if isinstance(ship.get("ShipType"), str) else "",
                    ShipType_Localised=ship.get("ShipType_Localised") if isinstance(ship.get("ShipType_Localised"), str) else None,
                    Name=ship.get("Name", "") if isinstance(ship.get("Name"), str) else "",
                        StarSystem=ship.get("StarSystem") if isinstance(ship.get("StarSystem"), str) else None,
                        ShipMarketID=ship.get("ShipMarketID") if isinstance(ship.get("ShipMarketID"), int) else None,
                        TransferPrice=ship.get("TransferPrice") if isinstance(ship.get("TransferPrice"), int) else None,
                        TransferTime=ship.get("TransferTime") if isinstance(ship.get("TransferTime"), int) else None,
                    Value=ship.get("Value", 0) if isinstance(ship.get("Value"), int) else 0,
                        Hot=ship.get("Hot", False) if isinstance(ship.get("Hot"), bool) else False,
                        InTransit=ship.get("InTransit") if isinstance(ship.get("InTransit"), bool) else None,
                    )
                )
            self.state.ShipsRemote = ships_remote

        if isinstance(event, GameEvent) and event.content.get("event") == "ShipyardTransfer":
            payload = cast(ShipyardTransferEvent, event.content)
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

            # Create a ship in transit using data from the event
            transit_item = ShipInTransitItem(
                ShipID=payload.get("ShipID", 0) if isinstance(payload.get("ShipID"), int) else 0,
                ShipType=payload.get("ShipType", "") if isinstance(payload.get("ShipType"), str) else "",
                System=self.state.StarSystem,
                ShipMarketID=self.state.MarketID,
                TransferCompleteTime=completion_time.isoformat(),
                TransferPrice=payload.get("TransferPrice", 0) if isinstance(payload.get("TransferPrice"), int) else 0,
            )

            if not any(s.ShipID == transit_item.ShipID for s in self.state.ShipsInTransit):
                self.state.ShipsInTransit.append(transit_item)
                if is_due:
                    projected_events.extend(self._complete_transfers(now_utc))

        # Check if any ships in transit have completed
        # current_time = self._get_event_time(event)
        # projected_events.extend(self._complete_transfers(current_time))

        return projected_events

    def process_timer(self) -> list[ProjectedEvent]:
        current_time = datetime.now(timezone.utc)
        return self._complete_transfers(current_time)
