from typing import Optional

from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import (
    ApproachBodyEvent,
    ApproachSettlementEvent,
    DockedEvent,
    FSDJumpEvent,
    LeaveBodyEvent,
    LiftoffEvent,
    LocationEvent,
    SupercruiseEntryEvent,
    SupercruiseExitEvent,
    TouchdownEvent,
    UndockedEvent,
)


class LocationState(BaseModel):
    """Current location of the commander in the galaxy."""
    StarSystem: str = Field(default="Unknown", description="Current star system name")
    SystemAddress: Optional[int] = Field(default=None, description="Unique system address for the current star system")
    Star: Optional[str] = Field(default=None, description="Current star body if near one")
    StarPos: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], description="Position in galactic coordinates [x, y, z]")
    Planet: Optional[str] = Field(default=None, description="Current planet body if near one")
    PlanetaryRing: Optional[str] = Field(default=None, description="Current planetary ring if near one")
    StellarRing: Optional[str] = Field(default=None, description="Current stellar ring if near one")
    Station: Optional[str] = Field(default=None, description="Current station if at one")
    AsteroidCluster: Optional[str] = Field(default=None, description="Current asteroid cluster if in one")
    Docked: Optional[bool] = Field(default=None, description="True if docked at a station")
    Landed: Optional[bool] = Field(default=None, description="True if landed on a surface")
    NearestDestination: Optional[str] = Field(default=None, description="Nearest point of interest when landed")


class Location(Projection[LocationState]):
    StateModel = LocationState

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get("event") == "Location":
            payload = cast(LocationEvent, event.content)
            star_system = payload.get("StarSystem", "Unknown")
            body_type = payload.get("BodyType", "Null")
            body = payload.get("Body", "Unknown")
            station = payload.get("StationName")
            docked = payload.get("Docked", False)
            star_pos = payload.get("StarPos", [0, 0, 0])

            # Reset state and set new values
            self.state.StarSystem = star_system
            self.state.StarPos = star_pos
            if "SystemAddress" in payload:
                self.state.SystemAddress = payload.get("SystemAddress", 0)
            if station:
                self.state.Station = station
                self.state.Docked = docked
            if body_type and body_type != "Null":
                setattr(self.state, str(body_type), body)

        if isinstance(event, GameEvent) and event.content.get("event") == "SupercruiseEntry":
            payload = cast(SupercruiseEntryEvent, event.content)
            star_system = payload.get("StarSystem", "Unknown")
            self.state.StarSystem = star_system

        if isinstance(event, GameEvent) and event.content.get("event") == "SupercruiseExit":
            payload = cast(SupercruiseExitEvent, event.content)
            star_system = payload.get("StarSystem", "Unknown")
            body_type = payload.get("BodyType", "Null")
            body = payload.get("Body", "Unknown")

            self.state.StarSystem = star_system
            if body_type and body_type != "Null":
                setattr(self.state, str(body_type), body)

        if isinstance(event, GameEvent) and event.content.get("event") == "FSDJump":
            payload = cast(FSDJumpEvent, event.content)
            star_system = payload.get("StarSystem", "Unknown")
            system_address = payload.get("SystemAddress")
            star_pos = payload.get("StarPos", [0, 0, 0])
            body_type = payload.get("BodyType", "Null")
            body = payload.get("Body", "Unknown")
            self.state.StarSystem = star_system
            self.state.StarPos = star_pos
            self.state.SystemAddress = cast(Optional[int], system_address)

            if body_type and body_type != "Null":
                setattr(self.state, str(body_type), body)

        if isinstance(event, GameEvent) and event.content.get("event") == "Docked":
            payload = cast(DockedEvent, event.content)
            self.state.Docked = True
            self.state.Station = payload.get("StationName", "Unknown")

        if isinstance(event, GameEvent) and event.content.get("event") == "Undocked":
            payload = cast(UndockedEvent, event.content)
            self.state.Docked = None

        if isinstance(event, GameEvent) and event.content.get("event") == "Touchdown":
            payload = cast(TouchdownEvent, event.content)
            self.state.Landed = True
            self.state.NearestDestination = payload.get("NearestDestination", "Unknown")

        if isinstance(event, GameEvent) and event.content.get("event") == "Liftoff":
            payload = cast(LiftoffEvent, event.content)
            self.state.Landed = None

        if isinstance(event, GameEvent) and event.content.get("event") == "ApproachSettlement":
            payload = cast(ApproachSettlementEvent, event.content)
            self.state.Station = cast(Optional[str], payload.get("Name", "Unknown"))
            self.state.Planet = cast(Optional[str], payload.get("BodyName", "Unknown"))

        if isinstance(event, GameEvent) and event.content.get("event") == "ApproachBody":
            payload = cast(ApproachBodyEvent, event.content)
            self.state.Station = cast(Optional[str], payload.get("Name", "Unknown"))
            self.state.Planet = cast(Optional[str], payload.get("BodyName", "Unknown"))

        if isinstance(event, GameEvent) and event.content.get("event") == "LeaveBody":
            payload = cast(LeaveBodyEvent, event.content)
            self.state.Station = None
            self.state.Planet = None
