from typing import Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent
from ..EventManager import Projection
from ..EventModels import (
    ApproachBodyEvent,
    ApproachSettlementEvent,
    CarrierJumpEvent,
    DockedEvent,
    FSDJumpEvent,
    LeaveBodyEvent,
    LiftoffEvent,
    LocationEvent,
    LocationEventFactionsItem,
    LocationEventSystemfaction,
    SquadronStartupEvent,
    SupercruiseEntryEvent,
    SupercruiseExitEvent,
    TouchdownEvent,
    UndockedEvent,
)


class LocationState(BaseModel):
    """Current location of the commander in the galaxy."""
    StarSystem: str = Field(default="Unknown", description="Current star system name")
    SystemAddress: Optional[int] = Field(default=None, description="Unique system address for the current star system")
    SquadronName: str = Field(default="Unknown", description="Player squadron name")
    SystemFaction: Optional[LocationEventSystemfaction] = Field(default=None, description="Controlling faction for the current system")
    Factions: Optional[list[LocationEventFactionsItem]] = Field(default=None, description="Known factions present in the current system")
    Powers: Optional[list[str]] = Field(default=None, description="Powers present in the current system")
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

    @staticmethod
    def _normalize_name(value: str) -> str:
        return value.strip().casefold()

    def _annotate_factions(self, factions: Optional[list[LocationEventFactionsItem]]) -> Optional[list[LocationEventFactionsItem]]:
        if factions is None:
            return None

        squadron_name = self._normalize_name(self.state.SquadronName)
        has_known_squadron = squadron_name not in {"", "unknown"}
        annotated: list[LocationEventFactionsItem] = []
        for faction in factions:
            faction_copy = dict(faction)
            faction_name = faction_copy.get("Name", "")
            is_own_faction = (
                has_known_squadron
                and isinstance(faction_name, str)
                and self._normalize_name(faction_name) == squadron_name
            )
            faction_copy["OwnFaction"] = is_own_faction
            annotated.append(cast(LocationEventFactionsItem, cast(object, faction_copy)))

        return annotated

    @override
    def process(self, event: Event) -> None:
        if not isinstance(event, GameEvent):
            return

        event_name = event.content.get("event")

        if event_name == "SquadronStartup":
            payload = cast(SquadronStartupEvent, cast(object, event.content))
            squadron_name = payload.get("SquadronName", "Unknown")
            if isinstance(squadron_name, str):
                self.state.SquadronName = squadron_name
                self.state.Factions = self._annotate_factions(self.state.Factions)

        if event_name == "Location":
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
            self.state.SystemFaction = payload.get("SystemFaction")
            self.state.Factions = self._annotate_factions(payload.get("Factions", []))
            self.state.Powers = payload.get("Powers")
            if station:
                self.state.Station = station
                self.state.Docked = docked
            if body_type and body_type != "Null":
                setattr(self.state, str(body_type), body)

        if event_name == "SupercruiseEntry":
            payload = cast(SupercruiseEntryEvent, event.content)
            star_system = payload.get("StarSystem", "Unknown")
            self.state.StarSystem = star_system

        if event_name == "SupercruiseExit":
            payload = cast(SupercruiseExitEvent, event.content)
            star_system = payload.get("StarSystem", "Unknown")
            body_type = payload.get("BodyType", "Null")
            body = payload.get("Body", "Unknown")

            self.state.StarSystem = star_system
            if body_type and body_type != "Null":
                setattr(self.state, str(body_type), body)

        if event_name == "FSDJump":
            payload = cast(FSDJumpEvent, event.content)
            star_system = payload.get("StarSystem", "Unknown")
            system_address = payload.get("SystemAddress")
            star_pos = payload.get("StarPos", [0, 0, 0])
            body_type = payload.get("BodyType", "Null")
            body = payload.get("Body", "Unknown")
            self.state.StarSystem = star_system
            self.state.StarPos = star_pos
            self.state.SystemAddress = cast(Optional[int], system_address)
            self.state.SystemFaction = payload.get("SystemFaction")
            self.state.Factions = self._annotate_factions(payload.get("Factions", []))
            self.state.Powers = payload.get("Powers")

            if body_type and body_type != "Null":
                setattr(self.state, str(body_type), body)

        if event_name == "CarrierJump":
            payload = cast(CarrierJumpEvent, event.content)
            star_system = payload.get("StarSystem", "Unknown")
            system_address = payload.get("SystemAddress")
            star_pos = payload.get("StarPos", [0, 0, 0])
            body_type = payload.get("BodyType", "Null")
            body = payload.get("Body", "Unknown")
            self.state.StarSystem = star_system
            self.state.StarPos = star_pos
            self.state.SystemAddress = cast(Optional[int], system_address)
            self.state.SystemFaction = payload.get("SystemFaction")
            self.state.Factions = self._annotate_factions(payload.get("Factions", []))
            self.state.Powers = payload.get("Powers")

            if body_type and body_type != "Null":
                setattr(self.state, str(body_type), body)

        if event_name == "Docked":
            payload = cast(DockedEvent, event.content)
            self.state.Docked = True
            self.state.Station = payload.get("StationName", "Unknown")

        if event_name == "Undocked":
            payload = cast(UndockedEvent, event.content)
            self.state.Docked = None

        if event_name == "Touchdown":
            payload = cast(TouchdownEvent, event.content)
            self.state.Landed = True
            self.state.NearestDestination = payload.get("NearestDestination", "Unknown")

        if event_name == "Liftoff":
            payload = cast(LiftoffEvent, event.content)
            self.state.Landed = None

        if event_name == "ApproachSettlement":
            payload = cast(ApproachSettlementEvent, event.content)
            self.state.Station = cast(Optional[str], payload.get("Name", "Unknown"))
            self.state.Planet = cast(Optional[str], payload.get("BodyName", "Unknown"))

        if event_name == "ApproachBody":
            payload = cast(ApproachBodyEvent, event.content)
            self.state.Station = cast(Optional[str], payload.get("Name", "Unknown"))
            self.state.Planet = cast(Optional[str], payload.get("BodyName", "Unknown"))

        if event_name == "LeaveBody":
            payload = cast(LeaveBodyEvent, event.content)
            self.state.Station = None
            self.state.Planet = None
