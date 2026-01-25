from typing import cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import (
    ColonisationConstructionDepotEvent,
    DockedEvent,
    FSDJumpEvent,
    LocationEvent,
    SupercruiseEntryEvent,
    SupercruiseExitEvent,
)


class ColonisationResourceItem(BaseModel):
    """A resource required for colonisation construction."""
    Name: str = Field(description="Resource internal name")
    Name_Localised: str = Field(description="Human-readable resource name")
    RequiredAmount: int = Field(description="Total amount required")
    ProvidedAmount: int = Field(description="Amount already provided")
    Payment: int = Field(description="Payment per unit in credits")


class ColonisationConstructionStateModel(BaseModel):
    """Current colonisation construction project status."""
    ConstructionProgress: float = Field(default=0.0, description="Construction completion percentage")
    ConstructionComplete: bool = Field(default=False, description="Whether construction is complete")
    ConstructionFailed: bool = Field(default=False, description="Whether construction has failed")
    ResourcesRequired: list[ColonisationResourceItem] = Field(default_factory=list, description="Resources needed for construction")
    MarketID: int = Field(default=0, description="Market identifier for the construction depot")
    StarSystem: str = Field(default="Unknown", description="Star system of the construction")
    StarSystemRecall: str = Field(default="Unknown", description="Last known star system")


class ColonisationConstruction(Projection[ColonisationConstructionStateModel]):
    StateModel = ColonisationConstructionStateModel

    @override
    def process(self, event: Event) -> None:
        # Process ColonisationConstructionDepot events
        if isinstance(event, GameEvent) and event.content.get("event") == "ColonisationConstructionDepot":
            payload = cast(ColonisationConstructionDepotEvent, event.content)
            # Update construction status
            self.state.ConstructionProgress = payload.get("ConstructionProgress", 0.0)
            self.state.ConstructionComplete = payload.get("ConstructionComplete", False)
            self.state.ConstructionFailed = payload.get("ConstructionFailed", False)
            self.state.MarketID = payload.get("MarketID", 0)

            # Update resources required with proper ColonisationResourceItem parsing
            raw_resources = payload.get("ResourcesRequired", [])
            if raw_resources:
                self.state.ResourcesRequired = [
                    ColonisationResourceItem(
                        Name=r.get("Name", ""),
                        Name_Localised=r.get("Name_Localised", ""),
                        RequiredAmount=r.get("RequiredAmount", 0),
                        ProvidedAmount=r.get("ProvidedAmount", 0),
                        Payment=r.get("Payment", 0),
                    )
                    for r in raw_resources
                ]
            self.state.StarSystem = self.state.StarSystemRecall

        if isinstance(event, GameEvent) and event.content.get("event") == "Docked":
            payload = cast(DockedEvent, event.content)
            # If we have an active construction and dock at a non-construction station
            # with the same MarketID, the construction has concluded. Reset to defaults.
            if self.state.MarketID and not self.state.ConstructionComplete and not self.state.ConstructionFailed:
                docked_market_id = payload.get("MarketID", 0)
                station_type = payload.get("StationType", "")
                if docked_market_id == self.state.MarketID and "construction" not in station_type.lower():
                    self.state.ConstructionProgress = 0.0
                    self.state.ConstructionComplete = False
                    self.state.ConstructionFailed = False
                    self.state.ResourcesRequired = []
                    self.state.MarketID = 0

        if isinstance(event, GameEvent) and event.content.get("event") == "Location":
            payload = cast(LocationEvent, event.content)
            self.state.StarSystemRecall = payload.get("StarSystem", "Unknown")

        if isinstance(event, GameEvent) and event.content.get("event") == "SupercruiseEntry":
            payload = cast(SupercruiseEntryEvent, event.content)
            self.state.StarSystemRecall = payload.get("StarSystem", "Unknown")

        if isinstance(event, GameEvent) and event.content.get("event") == "SupercruiseExit":
            payload = cast(SupercruiseExitEvent, event.content)
            self.state.StarSystemRecall = payload.get("StarSystem", "Unknown")

        if isinstance(event, GameEvent) and event.content.get("event") == "FSDJump":
            payload = cast(FSDJumpEvent, event.content)
            self.state.StarSystemRecall = payload.get("StarSystem", "Unknown")
