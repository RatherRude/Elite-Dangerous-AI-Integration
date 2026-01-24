import math
import re
import traceback
from typing import Any, Literal, final, List, cast, Optional
from datetime import datetime, timezone, timedelta
from webbrowser import get

from typing_extensions import override
from pydantic import BaseModel, Field

from .Event import Event, StatusEvent, GameEvent, ProjectedEvent, ExternalEvent, ConversationEvent, ToolEvent
from .EventModels import FSSSignalDiscoveredEvent, LocationEvent
from .EventManager import EventManager, Projection
from .Logger import log
from .EDFuelCalc import RATING_BY_CLASSNUM , FSD_OVERCHARGE_STATS , FSD_MKii ,FSD_OVERCHARGE_V2PRE_STATS, FSD_STATS ,FSD_GUARDIAN_BOOSTER
from .StatusParser import parse_status_flags, parse_status_json, Status
from .SystemDatabase import SystemDatabase

# Type alias for projected states dictionary
ProjectedStates = dict[str, BaseModel]

def get_state_dict(projected_states: ProjectedStates, key: str, default: dict | None = None) -> dict:
    """Helper to get a projection state as a dict for backward-compatible access patterns.

    Args:
        projected_states: The projected states dictionary
        key: The projection name (e.g., 'CurrentStatus', 'Location')
        default: Default value if key not found (defaults to empty dict)

    Returns:
        The state as a dict (via model_dump() if BaseModel, or as-is if already dict)
    """
    if default is None:
        default = {}
    state = projected_states.get(key)
    if state is None:
        return default
    if isinstance(state, LatestEventState):
        return state.data
    if hasattr(state, 'model_dump'):
        return state.model_dump()
    return state if isinstance(state, dict) else default

# Pydantic model for LatestEvent projection - stores arbitrary game event data
class LatestEventState(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)

def latest_event_projection_factory(projectionName: str, gameEvent: str):
    class LatestEvent(Projection[LatestEventState]):
        StateModel = LatestEventState

        @override
        def process(self, event: Event) -> None:
            if isinstance(event, GameEvent):
                if gameEvent and event.content.get('event', '') == gameEvent:
                    self.state.data = event.content

    LatestEvent.__name__ = projectionName

    return LatestEvent


class EventCounterState(BaseModel):
    count: int = 0


class EventCounter(Projection[EventCounterState]):
    StateModel = EventCounterState

    @override
    def process(self, event: Event) -> None:
        self.state.count += 1


# ===== Status State Models =====
# These models document the commander's current status from the Status.json file

class StatusBaseFlags(BaseModel):
    """Base status flags indicating ship/SRV state."""
    Docked: bool = False
    Landed: bool = False
    LandingGearDown: bool = False
    ShieldsUp: bool = False
    Supercruise: bool = False
    FlightAssistOff: bool = False
    HardpointsDeployed: bool = False
    InWing: bool = False
    LightsOn: bool = False
    CargoScoopDeployed: bool = False
    SilentRunning: bool = False
    ScoopingFuel: bool = False
    SrvHandbrake: bool = False
    SrvUsingTurretView: bool = False
    SrvTurretRetracted: bool = False
    SrvDriveAssist: bool = False
    FsdMassLocked: bool = False
    FsdCharging: bool = False
    FsdCooldown: bool = False
    LowFuel: bool = False
    OverHeating: bool = False
    HasLatLong: bool = False
    InDanger: bool = False
    BeingInterdicted: bool = False
    InMainShip: bool = False
    InFighter: bool = False
    InSRV: bool = False
    HudInAnalysisMode: bool = False
    NightVision: bool = False
    AltitudeFromAverageRadius: bool = False
    FsdJump: bool = False
    SrvHighBeam: bool = False


class StatusOdysseyFlags(BaseModel):
    """Odyssey-specific status flags for on-foot gameplay."""
    OnFoot: bool = False
    InTaxi: bool = False
    InMultiCrew: bool = False
    OnFootInStation: bool = False
    OnFootOnPlanet: bool = False
    AimDownSight: bool = False
    LowOxygen: bool = False
    LowHealth: bool = False
    Cold: bool = False
    Hot: bool = False
    VeryCold: bool = False
    VeryHot: bool = False
    GlideMode: bool = False
    OnFootInHangar: bool = False
    OnFootSocialSpace: bool = False
    OnFootExterior: bool = False
    BreathableAtmosphere: bool = False
    TelepresenceMulticrew: bool = False
    PhysicalMulticrew: bool = False
    FsdHyperdriveCharging: bool = False


class StatusPips(BaseModel):
    """Power distribution between ship systems."""
    system: float = Field(default=0.0, description="Power pips allocated to systems (shields)")
    engine: float = Field(default=0.0, description="Power pips allocated to engines")
    weapons: float = Field(default=0.0, description="Power pips allocated to weapons")


class StatusFuel(BaseModel):
    """Current fuel levels."""
    FuelMain: float = Field(default=0.0, description="Main fuel tank level in tons")
    FuelReservoir: float = Field(default=0.0, description="Reservoir fuel level in tons")


class StatusDestination(BaseModel):
    """Current navigation destination."""
    System: int = Field(default=0, description="System ID")
    Body: int = Field(default=0, description="Body ID")
    Name: str = Field(default="", description="Destination name")
    Name_Localised: Optional[str] = Field(default=None, description="Localized destination name")


GUI_FOCUS_LITERAL = Literal[
    'NoFocus',
    'InternalPanel',
    'ExternalPanel',
    'CommsPanel',
    'RolePanel',
    'StationServices',
    'GalaxyMap',
    'SystemMap',
    'Orrery',
    'FSS',
    'SAA',
    'Codex',
]

LEGAL_STATE_LITERAL = Literal[
    "Clean",
    "IllegalCargo",
    "Speeding",
    "Wanted",
    "Hostile",
    "PassengerWanted",
    "Warrant",
    "Thargoid",
    "Allied",
]


class CurrentStatusState(BaseModel):
    """Complete status of the commander from Status.json.

    This model represents the real-time status of the commander including
    ship state, on-foot state, location, and various gameplay indicators.
    """
    event: Literal["Status"] = "Status"
    flags: StatusBaseFlags = Field(default_factory=StatusBaseFlags, description="Base status flags for ship/SRV state")
    flags2: Optional[StatusOdysseyFlags] = Field(default=None, description="Odyssey-specific on-foot flags")
    Pips: Optional[StatusPips] = Field(default=None, description="Power distribution")
    FireGroup: Optional[int] = Field(default=None, description="Currently selected fire group (0-indexed)")
    GuiFocus: Optional[GUI_FOCUS_LITERAL] = Field(default=None, description="Currently focused UI panel")
    Fuel: Optional[StatusFuel] = Field(default=None, description="Current fuel levels")
    Cargo: Optional[float] = Field(default=None, description="Current cargo tonnage")
    LegalState: Optional[LEGAL_STATE_LITERAL] = Field(default=None, description="Commander's legal status")
    Latitude: Optional[float] = Field(default=None, description="Latitude on planetary body")
    Altitude: Optional[float] = Field(default=None, description="Altitude above surface in meters")
    Longitude: Optional[float] = Field(default=None, description="Longitude on planetary body")
    Heading: Optional[float] = Field(default=None, description="Heading in degrees")
    BodyName: Optional[str] = Field(default=None, description="Name of the planetary body")
    PlanetRadius: Optional[float] = Field(default=None, description="Radius of the planetary body in meters")
    Balance: Optional[float] = Field(default=None, description="Credit balance")
    Destination: Optional[StatusDestination] = Field(default=None, description="Current navigation destination")
    Oxygen: Optional[float] = Field(default=None, description="Oxygen level (0-1) when on foot")
    Health: Optional[float] = Field(default=None, description="Health level (0-1) when on foot")
    Temperature: Optional[float] = Field(default=None, description="Temperature when on foot")
    SelectedWeapon: Optional[str] = Field(default=None, description="Currently selected weapon when on foot")
    Gravity: Optional[float] = Field(default=None, description="Local gravity when on foot")


class CurrentStatus(Projection[CurrentStatusState]):
    StateModel = CurrentStatusState

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            status = event.status

            # Parse base flags
            flags_dict = status.get('flags', {})
            if isinstance(flags_dict, dict):
                self.state.flags = StatusBaseFlags(**flags_dict)

            # Parse Odyssey flags if present
            flags2_dict = status.get('flags2')
            if flags2_dict and isinstance(flags2_dict, dict):
                self.state.flags2 = StatusOdysseyFlags(**flags2_dict)
            else:
                self.state.flags2 = None

            # Parse Pips if present
            pips = status.get('Pips')
            if pips and isinstance(pips, dict):
                self.state.Pips = StatusPips(**pips)
            else:
                self.state.Pips = None

            # Parse Fuel if present
            fuel = status.get('Fuel')
            if fuel and isinstance(fuel, dict):
                self.state.Fuel = StatusFuel(**fuel)
            else:
                self.state.Fuel = None

            # Parse Destination if present
            dest = status.get('Destination')
            if dest and isinstance(dest, dict):
                self.state.Destination = StatusDestination(**dest)
            else:
                self.state.Destination = None

            # Set simple fields
            self.state.FireGroup = status.get('FireGroup')
            self.state.GuiFocus = status.get('GuiFocus')
            self.state.Cargo = status.get('Cargo')
            self.state.LegalState = status.get('LegalState')
            self.state.Latitude = status.get('Latitude')
            self.state.Altitude = status.get('Altitude')
            self.state.Longitude = status.get('Longitude')
            self.state.Heading = status.get('Heading')
            self.state.BodyName = status.get('BodyName')
            self.state.PlanetRadius = status.get('PlanetRadius')
            self.state.Balance = status.get('Balance')
            self.state.Oxygen = status.get('Oxygen')
            self.state.Health = status.get('Health')
            self.state.Temperature = status.get('Temperature')
            self.state.SelectedWeapon = status.get('SelectedWeapon')
            self.state.Gravity = status.get('Gravity')


class CargoItem(BaseModel):
    """An item in the ship's cargo hold."""
    Name: str = Field(description="Name of the cargo item")
    Count: int = Field(default=0, description="Quantity of this item")
    Stolen: bool = Field(default=False, description="Whether this cargo is stolen")


class CargoState(BaseModel):
    """Current state of the ship's cargo hold."""
    Inventory: list[CargoItem] = Field(default_factory=list, description="List of cargo items")
    TotalItems: int = Field(default=0, description="Total cargo items count")
    Capacity: int = Field(default=0, description="Maximum cargo capacity")


@final
class Cargo(Projection[CargoState]):
    StateModel = CargoState
    
    @override
    def process(self, event: Event) -> None:
        # Process Cargo event
        if isinstance(event, GameEvent) and event.content.get('event') == 'Cargo':
            if 'Inventory' in event.content:
                self.state.Inventory = []

                for item in event.content.get('Inventory', []):
                    self.state.Inventory.append(CargoItem(
                        Name=item.get('Name_Localised', item.get('Name', 'Unknown')),
                        Count=item.get('Count', 0),
                        Stolen=item.get('Stolen', 0) > 0
                    ))

            if 'Count' in event.content:
                self.state.TotalItems = int(event.content.get('Count', 0))

        # Get cargo capacity from Loadout event
        if isinstance(event, GameEvent) and event.content.get('event') == 'Loadout':
            self.state.Capacity = int(event.content.get('CargoCapacity', 0))
            
        # Update from Status event
        if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
            if 'Cargo' in event.status:
                self.state.TotalItems = int(event.status.get('Cargo', 0))


class LocationState(BaseModel):
    """Current location of the commander in the galaxy."""
    StarSystem: str = Field(default='Unknown', description="Current star system name")
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


@final
class Location(Projection[LocationState]):
    StateModel = LocationState
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'Location':
            star_system = event.content.get('StarSystem', 'Unknown')
            body_type = event.content.get('BodyType', 'Null')
            body = event.content.get('Body', 'Unknown')
            station = event.content.get('StationName')
            docked = event.content.get('Docked', False)
            star_pos = event.content.get('StarPos', [0,0,0])

            # Reset state and set new values
            self.state = LocationState(StarSystem=star_system, StarPos=star_pos, SystemAddress=self.state.SystemAddress)
            if 'SystemAddress' in event.content:
                self.state.SystemAddress = event.content.get('SystemAddress', 0)
            if station:
                self.state.Station = station
                self.state.Docked = docked
            if body_type and body_type != 'Null':
                setattr(self.state, body_type, body)

        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseEntry':
            star_system = event.content.get('StarSystem', 'Unknown')
            self.state = LocationState(StarSystem=star_system, StarPos=self.state.StarPos, SystemAddress=self.state.SystemAddress)
                
        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseExit':
            star_system = event.content.get('StarSystem', 'Unknown')
            body_type = event.content.get('BodyType', 'Null')
            body = event.content.get('Body', 'Unknown')

            self.state = LocationState(StarSystem=star_system, StarPos=self.state.StarPos, SystemAddress=self.state.SystemAddress)
            if body_type and body_type != 'Null':
                setattr(self.state, body_type, body)
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump':
            star_system = event.content.get('StarSystem', 'Unknown')
            system_address = event.content.get('SystemAddress')
            star_pos = event.content.get('StarPos', [0,0,0])
            body_type = event.content.get('BodyType', 'Null')
            body = event.content.get('Body', 'Unknown')
            self.state = LocationState(StarSystem=star_system, StarPos=star_pos, SystemAddress=system_address)
            
            if body_type and body_type != 'Null':
                setattr(self.state, body_type, body)

        if isinstance(event, GameEvent) and event.content.get('event') == 'Docked':
            self.state.Docked = True
            self.state.Station = event.content.get('StationName', 'Unknown')
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Undocked':
            self.state.Docked = None
                
        if isinstance(event, GameEvent) and event.content.get('event') == 'Touchdown':
            self.state.Landed = True
            self.state.NearestDestination = event.content.get('NearestDestination', 'Unknown')
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Liftoff':
            self.state.Landed = None
            
        if isinstance(event, GameEvent) and event.content.get('event') == 'ApproachSettlement':
            self.state.Station = event.content.get('Name', 'Unknown')
            self.state.Planet = event.content.get('BodyName', 'Unknown')
            
        if isinstance(event, GameEvent) and event.content.get('event') == 'ApproachBody':
            self.state.Station = event.content.get('Name', 'Unknown')
            self.state.Planet = event.content.get('BodyName', 'Unknown')
            
        if isinstance(event, GameEvent) and event.content.get('event') == 'LeaveBody':
            self.state = LocationState(StarSystem=self.state.StarSystem, StarPos=self.state.StarPos, SystemAddress=self.state.SystemAddress)


class MissionState(BaseModel):
    """An active mission the commander has accepted."""
    Faction: str = Field(description="The faction that issued the mission")
    Name: str = Field(description="Internal mission name/identifier")
    LocalisedName: str = Field(description="Human-readable mission name")
    Expiry: str = Field(description="Mission expiry timestamp in ISO format")
    Wing: bool = Field(description="Whether this is a wing mission")
    Influence: str = Field(description="Influence effect on completion (None/Low/Med/High)")
    Reputation: str = Field(description="Reputation effect on completion (None/Low/Med/High)")
    MissionID: int = Field(description="Unique mission identifier")
    OriginStation: Optional[str] = Field(default=None, description="Station where mission was accepted")
    Commodity: Optional[str] = Field(default=None, description="Commodity to deliver (for delivery missions)")
    Count: Optional[int] = Field(default=None, description="Amount to deliver/collect")
    Target: Optional[str] = Field(default=None, description="Target name (for assassination missions)")
    TargetType: Optional[str] = Field(default=None, description="Target type")
    TargetFaction: Optional[str] = Field(default=None, description="Target faction")
    DestinationSystem: Optional[str] = Field(default=None, description="Destination star system")
    DestinationSettlement: Optional[str] = Field(default=None, description="Destination settlement")
    DestinationStation: Optional[str] = Field(default=None, description="Destination station")
    PassengerCount: Optional[int] = Field(default=None, description="Number of passengers (for passenger missions)")
    PassengerVIPs: Optional[bool] = Field(default=None, description="Whether passengers are VIPs")
    PassengerWanted: Optional[bool] = Field(default=None, description="Whether passengers are wanted")
    PassengerType: Optional[str] = Field(default=None, description="Type of passengers")
    Donation: Optional[int] = Field(default=None, description="Donation amount for donation missions")
    Reward: Optional[int] = Field(default=None, description="Credit reward on completion")


class UnknownMissionState(BaseModel):
    """A mission that was loaded from save but details are unknown."""
    MissionID: int = Field(description="Unique mission identifier")
    Name: str = Field(description="Mission name")


class MissionsStateModel(BaseModel):
    """Current mission state of the commander."""
    Active: list[MissionState] = Field(default_factory=list, description="List of active missions with full details")
    Unknown: Optional[list[UnknownMissionState]] = Field(default=None, description="Missions loaded from save with limited details")


@final
class Missions(Projection[MissionsStateModel]):
    StateModel = MissionsStateModel
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'Missions':
            active_ids = [mission["MissionID"] for mission in event.content.get('Active', [])]
            known_ids = [mission.MissionID for mission in self.state.Active]
            self.state.Active = [mission for mission in self.state.Active if mission.MissionID in active_ids]
            unknown_missions = [
                UnknownMissionState(MissionID=m["MissionID"], Name=m.get("Name", "Unknown"))
                for m in event.content.get('Active', [])
                if m["MissionID"] not in known_ids
            ]
            self.state.Unknown = unknown_missions if unknown_missions else None
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionAccepted':
            mission = MissionState(
                Faction=event.content.get('Faction', 'Unknown'),
                Name=event.content.get('Name', 'Unknown'),
                LocalisedName=event.content.get('LocalisedName', 'Unknown'),
                Expiry=event.content.get('Expiry', '1970-01-01T00:00:00Z'),
                Wing=event.content.get('Wing', False),
                Influence=event.content.get('Influence', 'Unknown'),
                Reputation=event.content.get('Reputation', 'Unknown'),
                MissionID=event.content.get('MissionID', 0),
                Donation=event.content.get('Donation'),
                Reward=event.content.get('Reward'),
                Commodity=event.content.get('Commodity'),
                Count=event.content.get('Count'),
                Target=event.content.get('Target'),
                TargetFaction=event.content.get('TargetFaction'),
                DestinationSystem=event.content.get('DestinationSystem'),
                DestinationSettlement=event.content.get('DestinationSettlement'),
                DestinationStation=event.content.get('DestinationStation'),
                PassengerCount=event.content.get('PassengerCount'),
                PassengerVIPs=event.content.get('PassengerVIPs'),
                PassengerWanted=event.content.get('PassengerWanted'),
                PassengerType=event.content.get('PassengerType'),
            )
            self.state.Active.append(mission)
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionCompleted':
            mission_id = event.content.get('MissionID', 0)
            self.state.Active = [mission for mission in self.state.Active if mission.MissionID != mission_id]
            if self.state.Unknown:
                self.state.Unknown = [mission for mission in self.state.Unknown if mission.MissionID != mission_id]
                if not self.state.Unknown:
                    self.state.Unknown = None
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionRedirected':
            existing_mission = next((mission for mission in self.state.Active if mission.MissionID == event.content.get('MissionID', 0)), None)
            new_destination_system = event.content.get('NewDestinationSystem', None)
            new_destination_station = event.content.get('NewDestinationStation', None)
            new_destination_settlement = event.content.get('NewDestinationSettlement', None)
            
            if existing_mission:
                if new_destination_system:
                    existing_mission.DestinationSystem = new_destination_system
                if new_destination_station:
                    existing_mission.DestinationStation = new_destination_station
                    if existing_mission.DestinationStation == existing_mission.OriginStation:
                        existing_mission.Name += " (Collect Reward)"
                if new_destination_settlement:
                    existing_mission.DestinationSettlement = new_destination_settlement
            
                self.state.Active = [mission for mission in self.state.Active if mission.MissionID != event.content.get('MissionID', 0)]
                self.state.Active.append(existing_mission)
                
        # If we Undock with a new mission, we probably accepted it at the station we undocked from
        if isinstance(event, GameEvent) and event.content.get('event') == 'Undocked':
            for mission in self.state.Active:
                if mission.OriginStation is None:
                    mission.OriginStation = event.content.get('StationName', 'Unknown')
        # If we Dock with a new mission, we probably accepted it somewhere in space, so we don't know the exact origin
        if isinstance(event, GameEvent) and event.content.get('event') == 'Docked':
            for mission in self.state.Active:
                if mission.OriginStation is None:
                    mission.OriginStation = 'Unknown'
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionAbandoned':
            mission_id = event.content.get('MissionID', 0)
            self.state.Active = [mission for mission in self.state.Active if mission.MissionID != mission_id]
            if self.state.Unknown:
                self.state.Unknown = [mission for mission in self.state.Unknown if mission.MissionID != mission_id]
                if not self.state.Unknown:
                    self.state.Unknown = None
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionFailed':
            mission_id = event.content.get('MissionID', 0)
            self.state.Active = [mission for mission in self.state.Active if mission.MissionID != mission_id]
            if self.state.Unknown:
                self.state.Unknown = [mission for mission in self.state.Unknown if mission.MissionID != mission_id]
                if not self.state.Unknown:
                    self.state.Unknown = None


ENGINEER_PROGRESS_LITERAL = Literal['Known', 'Invited', 'Acquainted', 'Unlocked', 'Barred']


class EngineerState(BaseModel):
    """Progress status with an engineer."""
    Engineer: str = Field(description="Engineer name")
    EngineerID: int = Field(description="Unique engineer identifier")
    Progress: Optional[ENGINEER_PROGRESS_LITERAL] = Field(default=None, description="Relationship status: Known/Invited/Acquainted/Unlocked/Barred")
    Rank: Optional[int] = Field(default=None, description="Current rank with this engineer (1-5)")
    RankProgress: Optional[int] = Field(default=None, description="Progress percentage to next rank")


class EngineerProgressStateModel(BaseModel):
    """Commander's progress with all engineers."""
    event: str = "EngineerProgress"
    timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Last update timestamp")
    Engineers: list[EngineerState] = Field(default_factory=list, description="List of engineer progress states")


@final
class EngineerProgress(Projection[EngineerProgressStateModel]):
    StateModel = EngineerProgressStateModel
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'EngineerProgress':
            # Handle startup form - save entire event
            if 'Engineers' in event.content:
                engineers = [
                    EngineerState(
                        Engineer=e.get('Engineer', 'Unknown'),
                        EngineerID=e.get('EngineerID', 0),
                        Progress=e.get('Progress'),
                        Rank=e.get('Rank'),
                        RankProgress=e.get('RankProgress'),
                    )
                    for e in event.content.get('Engineers', [])
                ]
                self.state = EngineerProgressStateModel(
                    event=event.content.get('event', 'EngineerProgress'),
                    timestamp=event.content.get('timestamp', '1970-01-01T00:00:00Z'),
                    Engineers=engineers,
                )
            
            # Handle update form - single engineer update
            elif 'Engineer' in event.content and 'EngineerID' in event.content:
                engineer_id = event.content.get('EngineerID', 0)

                # Find existing engineer or create new one
                existing_engineer = None
                for i, engineer in enumerate(self.state.Engineers):
                    if engineer.EngineerID == engineer_id:
                        existing_engineer = self.state.Engineers[i]
                        break
                
                if existing_engineer:
                    # Update existing engineer
                    if 'Engineer' in event.content:
                        existing_engineer.Engineer = event.content.get('Engineer', 'Unknown')
                    if 'Progress' in event.content:
                        existing_engineer.Progress = event.content.get('Progress', 'Unknown')
                    if 'Rank' in event.content:
                        existing_engineer.Rank = event.content.get('Rank', 0)
                    if 'RankProgress' in event.content:
                        existing_engineer.RankProgress = event.content.get('RankProgress', 0)
                else:
                    # Create new engineer entry
                    new_engineer = EngineerState(
                        Engineer=event.content.get('Engineer', 'Unknown'),
                        EngineerID=engineer_id,
                        Progress=event.content.get('Progress'),
                        Rank=event.content.get('Rank'),
                        RankProgress=event.content.get('RankProgress'),
                    )
                    self.state.Engineers.append(new_engineer)


class CommunityGoalTopTier(BaseModel):
    """Top tier reward for a community goal."""
    Name: str = Field(description="Name of the top tier reward")
    Bonus: str = Field(description="Bonus reward description")


class CommunityGoalItem(BaseModel):
    """An active community goal."""
    CGID: int = Field(description="Community goal unique identifier")
    Title: str = Field(description="Title of the community goal")
    SystemName: str = Field(description="Star system where the goal is located")
    MarketName: str = Field(description="Station/market name for the goal")
    Expiry: str = Field(description="Expiry timestamp in ISO format")
    IsComplete: bool = Field(description="Whether the goal has been completed")
    CurrentTotal: int = Field(description="Current total contributions")
    PlayerContribution: int = Field(description="Commander's contribution amount")
    NumContributors: int = Field(description="Total number of contributors")
    TopTier: Optional[CommunityGoalTopTier] = Field(default=None, description="Top tier reward info")
    TierReached: str = Field(description="Current tier reached")
    PlayerPercentileBand: int = Field(description="Commander's percentile band (top X%)")
    Bonus: int = Field(description="Bonus credits earned")
    TopRankSize: Optional[int] = Field(default=None, description="Size of top rank bracket")
    PlayerInTopRank: Optional[bool] = Field(default=None, description="Whether commander is in top rank")


class CommunityGoalStateModel(BaseModel):
    """Current community goals the commander is participating in."""
    event: Optional[str] = Field(default=None, description="Event type")
    timestamp: Optional[str] = Field(default=None, description="Last update timestamp")
    CurrentGoals: Optional[list[CommunityGoalItem]] = Field(default=None, description="List of active community goals")


@final
class CommunityGoal(Projection[CommunityGoalStateModel]):
    StateModel = CommunityGoalStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'CommunityGoal':
            # Parse goals from event content
            raw_goals = event.content.get('CurrentGoals', [])
            goals = [
                CommunityGoalItem(
                    CGID=g.get('CGID', 0),
                    Title=g.get('Title', ''),
                    SystemName=g.get('SystemName', ''),
                    MarketName=g.get('MarketName', ''),
                    Expiry=g.get('Expiry', ''),
                    IsComplete=g.get('IsComplete', False),
                    CurrentTotal=g.get('CurrentTotal', 0),
                    PlayerContribution=g.get('PlayerContribution', 0),
                    NumContributors=g.get('NumContributors', 0),
                    TopTier=CommunityGoalTopTier(**g['TopTier']) if g.get('TopTier') else None,
                    TierReached=g.get('TierReached', ''),
                    PlayerPercentileBand=g.get('PlayerPercentileBand', 0),
                    Bonus=g.get('Bonus', 0),
                    TopRankSize=g.get('TopRankSize'),
                    PlayerInTopRank=g.get('PlayerInTopRank'),
                )
                for g in raw_goals
            ] if raw_goals else None

            self.state = CommunityGoalStateModel(
                event=event.content.get('event'),
                timestamp=event.content.get('timestamp'),
                CurrentGoals=goals,
            )
        
        elif isinstance(event, GameEvent) and event.content.get('event') == 'LoadGame':
            # Check for expired goals and remove them
            from datetime import datetime
            current_time = event.timestamp
            current_dt = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
            
            # Filter out expired goals
            active_goals = []
            current_goals = self.state.CurrentGoals or []
            for goal in current_goals:
                expiry_time = goal.Expiry or "1970-01-01T00:00:00Z"
                expiry_dt = datetime.fromisoformat(expiry_time.replace('Z', '+00:00'))
                
                # Keep goal if it hasn't expired yet
                if current_dt < expiry_dt:
                    active_goals.append(goal)
            
            # Update state with only non-expired goals
            self.state.CurrentGoals = active_goals if active_goals else None

ship_sizes: dict[str, Literal['S', 'M', 'L', 'Unknown']] = {
    'adder':                         'S',
    'anaconda':                      'L',
    'asp':                           'M',
    'asp_scout':                     'M',
    'belugaliner':                   'L',
    'cobramkiii':                    'S',
    'cobramkiv':                     'S',
    'clipper':                       'Unknown',
    'cutter':                        'L',
    'corsair':                       'M',
    'diamondback':                   'S',
    'diamondbackxl':                 'S',
    'dolphin':                       'S',
    'eagle':                         'S',
    'empire_courier':                'S',
    'empire_eagle':                  'S',
    'empire_fighter':                'Unknown',
    'empire_trader':                 'L',
    'explorer_nx':                   'L',
    'federation_corvette':           'L',
    'federation_dropship':           'M',
    'federation_dropship_mkii':      'M',
    'federation_gunship':            'M',
    'federation_fighter':            'Unknown',
    'ferdelance':                    'M',
    'hauler':                        'S',
    'independant_trader':            'M',
    'independent_fighter':           'Unknown',
    'krait_mkii':                    'M',
    'krait_light':                   'M',
    'mamba':                         'M',
    'mandalay':                      'M',
    'orca':                          'L',
    'python':                        'M',
    'python_nx':                     'M',
    'panthermkii':                   'L',
    'scout':                         'Unknown',
    'sidewinder':                    'S',
    'testbuggy':                     'Unknown',
    'type6':                         'M',
    'type7':                         'L',
    'type8':                         'L',
    'type9':                         'L',
    'type9_military':                'L',
    'typex':                         'M',
    'typex_2':                       'M',
    'typex_3':                       'M',
    'type11':                        'M',
    'viper':                         'S',
    'viper_mkiv':                    'S',
    'vulture':                       'S',
}


FIGHTER_STATUS_LITERAL = Literal['Ready', 'Launched', 'BeingRebuilt', 'Abandoned']


class FighterState(BaseModel):
    """State of a ship-launched fighter."""
    Status: FIGHTER_STATUS_LITERAL = Field(description="Current fighter status")
    ID: Optional[int] = Field(default=None, description="Fighter identifier when launched")
    Pilot: Optional[str] = Field(default=None, description="Who is piloting: Commander, NPC Crew, or No pilot")
    RebuiltAt: Optional[str] = Field(default=None, description="Timestamp when fighter will be rebuilt")


LANDING_PAD_SIZE_LITERAL = Literal['S', 'M', 'L', 'Unknown']


class ShipInfoStateModel(BaseModel):
    """Current ship information and capabilities."""
    Name: str = Field(default='Unknown', description="Custom ship name")
    Type: str = Field(default='Unknown', description="Ship type identifier")
    ShipIdent: str = Field(default='Unknown', description="Ship identification code")
    UnladenMass: float = Field(default=0, description="Ship mass without cargo or fuel (tons)")
    Cargo: float = Field(default=0, description="Current cargo weight (tons)")
    CargoCapacity: float = Field(default=0, description="Maximum cargo capacity (tons)")
    ShipCargo: float = Field(default=0, description="Ship cargo (not SRV) weight (tons)")
    FuelMain: float = Field(default=0, description="Current main fuel tank level (tons)")
    FuelMainCapacity: float = Field(default=0, description="Main fuel tank capacity (tons)")
    FuelReservoir: float = Field(default=0, description="Current reservoir fuel level (tons)")
    FuelReservoirCapacity: float = Field(default=0, description="Reservoir fuel capacity (tons)")
    FSDSynthesis: float = Field(default=0, description="FSD synthesis boost multiplier (0.25/0.5/1.0)")
    ReportedMaximumJumpRange: float = Field(default=0, description="Maximum jump range reported by game (ly)")
    DriveOptimalMass: float = Field(default=0, description="FSD optimal mass parameter")
    DriveLinearConst: float = Field(default=0, description="FSD linear constant")
    DrivePowerConst: float = Field(default=0, description="FSD power constant")
    GuardianfsdBooster: float = Field(default=0, description="Guardian FSD booster bonus (ly)")
    DriveMaxFuel: float = Field(default=0, description="Maximum fuel per jump (tons)")
    JetConeBoost: float = Field(default=1, description="Jet cone/neutron star boost multiplier")
    MinimumJumpRange: float = Field(default=0, description="Minimum jump range with full cargo (ly)")
    CurrentJumpRange: float = Field(default=0, description="Current jump range with current load (ly)")
    MaximumJumpRange: float = Field(default=0, description="Maximum jump range empty (ly)")
    LandingPadSize: LANDING_PAD_SIZE_LITERAL = Field(default='Unknown', description="Required landing pad size: S/M/L")
    IsMiningShip: bool = Field(default=False, description="Whether ship has mining equipment")
    hasLimpets: bool = Field(default=False, description="Whether ship has limpet controllers")
    hasDockingComputer: bool = Field(default=False, description="Whether ship has docking computer")
    Fighters: list[FighterState] = Field(default_factory=list, description="Ship-launched fighters status")


@final
class ShipInfo(Projection[ShipInfoStateModel]):
    StateModel = ShipInfoStateModel
    
    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
     
        if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
            status: Status = event.status  # pyright: ignore[reportAssignmentType]
            if 'Cargo' in event.status:
                self.state.Cargo = event.status.get('Cargo') or 0
                
            if 'Fuel' in status and status['Fuel']:
                self.state.FuelMain = status['Fuel'].get('FuelMain') or 0
                self.state.FuelReservoir = status['Fuel'].get('FuelReservoir') or 0
                
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Loadout':
            if 'ShipName' in event.content:
                self.state.Name = event.content.get('ShipName') or 'Unknown'
            if 'Ship' in event.content:
                self.state.Type = event.content.get('Ship') or 'Unknown'
            if 'ShipIdent' in event.content:
                self.state.ShipIdent = event.content.get('ShipIdent') or 'Unknown'
            if 'UnladenMass' in event.content:
                self.state.UnladenMass = event.content.get('UnladenMass') or 0.0
            if 'CargoCapacity' in event.content:
                self.state.CargoCapacity = event.content.get('CargoCapacity') or 0
            if 'FuelCapacity' in event.content:
                self.state.FuelMainCapacity = event.content['FuelCapacity'].get('Main') or 0
                self.state.FuelReservoirCapacity = event.content['FuelCapacity'].get('Reserve') or 0

            if 'MaxJumpRange' in event.content:
                self.state.ReportedMaximumJumpRange = event.content.get('MaxJumpRange') or 0

            if 'Modules' in event.content:
                has_refinery = any(module["Item"].startswith("int_refinery") for module in event.content["Modules"])
                if has_refinery:
                    self.state.IsMiningShip = True
                else:
                    self.state.IsMiningShip = False

                has_limpets = any(
                    module.get("Item", "").startswith("int_dronecontrol")
                    or module.get("Item", "").startswith("int_multidronecontrol_")
                    for module in event.content["Modules"]
                )
                if has_limpets:
                    self.state.hasLimpets = True
                else:
                    self.state.hasLimpets = False

                has_docking_computer = any(
                    module.get("Item", "").startswith("int_dockingcomputer")
                    for module in event.content["Modules"]
                )
                if has_docking_computer:
                    self.state.hasDockingComputer = True
                else:
                    self.state.hasDockingComputer = False

                # Check for fighter bay modules
                fighter_count = 0
                for module in event.content.get("Modules", []):  # type: ignore
                    module_item = module.get("Item", "")
                    if module_item == "int_fighterbay_size5_class1":
                        fighter_count = 1
                        break
                    elif module_item in ["int_fighterbay_size6_class1", "int_fighterbay_size7_class1"]:
                        fighter_count = 2
                        break

                if fighter_count > 0:
                    # Initialize fighters in Ready state without IDs
                    self.state.Fighters = [FighterState(Status="Ready") for _ in range(fighter_count)]
                else:
                    self.state.Fighters = []

                #Check for FSD Engine
                for module in event.content.get("Modules", []):
                    module_slot = module.get("Slot", "") 
                    if module_slot != "FrameShiftDrive":
                        continue
                    
                    module_item = module.get('Item')
                    over = "hyperdrive_overcharge" in module_item
                    mkii = "overchargebooster_mkii" in module_item
                    module_size_match = re.search(r"size(\d)", module_item)
                    module_class_match = re.search(r"class(\d)", module_item)
                    module_size = int(module_size_match.group(1)) if module_size_match else None
                    module_rating = RATING_BY_CLASSNUM.get(int(module_class_match.group(1))) if module_class_match else None

                    engineering_optimal_mass_override = None
                    engineering_max_fuel_override = None

                    for modifier in module.get("Engineering", {}).get("Modifiers", []) or []:
                        if modifier.get("Label") in ("FSDOptimalMass", "fsdoptimalmass"):
                            engineering_optimal_mass_override = float(modifier.get("Value"))
                            
                        if modifier.get("Label") in ("MaxFuelPerJump", "maxfuelperjump"):
                            engineering_max_fuel_override = float(modifier.get("Value"))
                    if mkii == True:
                        all_module_stats = FSD_MKii
                    else:
                        all_module_stats = FSD_OVERCHARGE_STATS if over else FSD_STATS

                    module_stat: dict = all_module_stats.get((module_size, module_rating))
                    self.state.DriveOptimalMass = engineering_optimal_mass_override if engineering_optimal_mass_override is not None else module_stat.get('opt_mass', 0.00)
                    self.state.DriveMaxFuel = engineering_max_fuel_override if engineering_max_fuel_override is not None else module_stat.get('max_fuel', 0.00)
                    self.state.DriveLinearConst = module_stat.get('linear_const', 0.0)
                    self.state.DrivePowerConst = module_stat.get('power_const', 0.0)

                    log('debug','mkii?: ',mkii,' Fsd type again :', module_item)

                # Check for GuardianfsdBooster
                self.state.GuardianfsdBooster = 0
                for module in event.content.get("Modules", []):
                    module_item = module.get('Item')
                    if "int_guardianfsdbooster" in module_item.lower():    
                        module_size_match = re.search(r"size(\d+)", module_item)
                        module_size = int(module_size_match.group(1))
                        guardian_booster_stats = FSD_GUARDIAN_BOOSTER.get((module_size,"H"))
                        
                        self.state.GuardianfsdBooster = guardian_booster_stats.get('jump_boost', 0.0)
                          
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'JetConeBoost':
            fsd_star_boost = event.content.get('BoostValue', 1)
            self.state.JetConeBoost = fsd_star_boost
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Synthesis':
            fsd_inject_boost_name = event.content.get('Name', "")

            if fsd_inject_boost_name == "FSD Basic":
                self.state.FSDSynthesis = 0.25

            elif fsd_inject_boost_name == "FSD Standard":
                self.state.FSDSynthesis = 0.5

            elif fsd_inject_boost_name == "FSD Premium":
                self.state.FSDSynthesis = 1

        if isinstance(event,GameEvent) and event.content.get('event') == 'FSDJump':
            self.state.JetConeBoost = 1
            self.state.FSDSynthesis = 0

        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Cargo':
            self.state.Cargo = event.content.get('Count') or 0
            if event.content.get('Vessel') == 'Ship': 
                self.state.ShipCargo = event.content.get('Count') or 0

        if isinstance(event, GameEvent) and event.content.get('event') in ['RefuelAll','RepairAll','BuyAmmo']:
            if self.state.hasLimpets and self.state.Cargo < self.state.CargoCapacity:
                projected_events.append(ProjectedEvent(content={"event": "RememberLimpets"}))

        if isinstance(event, GameEvent) and event.content.get('event') == 'SetUserShipName':
            if 'UserShipName' in event.content:
                self.state.Name = event.content.get('UserShipName') or 'Unknown'
            if 'UserShipId' in event.content:
                self.state.ShipIdent = event.content.get('UserShipId') or 'Unknown'

        # Fighter events
        # No events for crew fighter destroyed or docked...
        # if isinstance(event, GameEvent) and event.content.get('event') == 'CrewLaunchFighter':
        #     # Commander launches fighter for crew member
        #     crew_name = event.content.get('Crew', 'Unknown Crew')
        #
        #     # Find a ready fighter without ID to assign to crew
        #     for fighter in self.state.Fighters:
        #         if fighter['Status'] == 'Ready' and 'ID' not in fighter:
        #             fighter['Status'] = 'Launched'
        #             fighter['Pilot'] = crew_name
        #             break

        if isinstance(event, GameEvent) and event.content.get('event') == 'LaunchFighter':
            fighter_id = event.content.get('ID')
            player_controlled = event.content.get('PlayerControlled', False)
            
            if fighter_id is not None:
                # Determine pilot based on PlayerControlled flag
                pilot = "Commander" if player_controlled else "NPC Crew"
                
                # Find existing fighter with this ID or a ready fighter without ID
                fighter_found = False
                for fighter in self.state.Fighters:
                    if fighter.ID == fighter_id:
                        # Fighter with this ID already exists
                        fighter.Status = 'Launched'
                        fighter.Pilot = pilot
                        fighter_found = True
                        break
                
                if not fighter_found:
                    # Find a ready fighter without ID
                    for fighter in self.state.Fighters:
                        if fighter.Status == 'Ready' and fighter.ID is None:
                            fighter.ID = fighter_id
                            fighter.Status = 'Launched'
                            fighter.Pilot = pilot
                            break

        if isinstance(event, GameEvent) and event.content.get('event') == 'DockFighter':
            fighter_id = event.content.get('ID')
            
            # Find fighter by ID and set to ready, clear ID
            for fighter in self.state.Fighters:
                if fighter.ID == fighter_id:
                    fighter.Status = 'Ready'
                    fighter.ID = None
                    fighter.Pilot = None
                    break

        if isinstance(event, GameEvent) and event.content.get('event') == 'FighterDestroyed':
            fighter_id = event.content.get('ID')
            
            # Calculate rebuild completion time (80 seconds from now)
            current_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            rebuild_time = current_time + timedelta(seconds=90)
            rebuild_timestamp = rebuild_time.isoformat().replace('+00:00', 'Z')
            
            # Find fighter by ID and set to being rebuilt
            for fighter in self.state.Fighters:
                if fighter.ID == fighter_id:
                    fighter.Status = 'BeingRebuilt'
                    fighter.RebuiltAt = rebuild_timestamp
                    fighter.Pilot = None
                    break

        if isinstance(event, GameEvent) and event.content.get('event') == 'FighterRebuilt':
            fighter_id = event.content.get('ID')
            
            # Find fighter by ID and set to ready, clear ID
            for fighter in self.state.Fighters:
                if fighter.ID == fighter_id:
                    fighter.Status = 'Ready'
                    fighter.ID = None
                    fighter.Pilot = None
                    fighter.RebuiltAt = None
                    break

        if isinstance(event, GameEvent) and event.content.get('event') == 'VehicleSwitch':
            vehicle_to = event.content.get('To', '')
            
            if vehicle_to == 'Mothership':
                # Commander switched back to mothership, fighter becomes abandoned
                for fighter in self.state.Fighters:
                    if fighter.Pilot == 'Commander' and fighter.Status == 'Launched':
                        fighter.Status = 'Abandoned'
                        fighter.Pilot = 'No pilot'
                        break
            
            elif vehicle_to == 'Fighter':
                # Commander switched to fighter, set fighter back to launched
                for fighter in self.state.Fighters:
                    if fighter.Status == 'Abandoned' and fighter.Pilot == 'No pilot':
                        fighter.Status = 'Launched'
                        fighter.Pilot = 'Commander'
                        break

        if self.state.Type != 'Unknown':
            self.state.LandingPadSize = ship_sizes.get(self.state.Type, 'Unknown')
            
        # Recalculate jump ranges on weight, module or modifier changes
        if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
            try:
                min_jr,cur_jr,max_jr = self.calculate_jump_range()
                self.state.MinimumJumpRange = min_jr
                self.state.CurrentJumpRange = cur_jr
                self.state.MaximumJumpRange = max_jr
            except Exception as e:
                log('error', 'Error calculating jump ranges:', e, traceback.format_exc())
        
        return projected_events
    
    def calculate_jump_range(self) -> tuple[float, float, float]:

        unladen_mass   = self.state.UnladenMass
        cargo_capacity = self.state.CargoCapacity
        fuel_capacity  = self.state.FuelMainCapacity
        maximum_jump_range     = self.state.ReportedMaximumJumpRange
        drive_power_const   = self.state.DrivePowerConst
        drive_optimal_mass = self.state.DriveOptimalMass
        drive_linear_const  = self.state.DriveLinearConst
        drive_max_fuel  = self.state.DriveMaxFuel
        fsd_star_boost = self.state.JetConeBoost
        fsd_boost = self.state.GuardianfsdBooster
        fsd_inject = self.state.FSDSynthesis # +inject juice 25% , 50% ,100% but cant be with star_boost

        if not (unladen_mass > 0 and fuel_capacity > 0 and maximum_jump_range > 0 and drive_max_fuel):
            return 0, 0, 0

        current_cargo = self.state.ShipCargo
        current_fuel  = self.state.FuelMain
        current_fuel_reservoir = self.state.FuelReservoir

        minimal_mass = unladen_mass + drive_max_fuel  #max jump with just right anmount
        current_mass = unladen_mass + current_cargo + current_fuel + current_fuel_reservoir  #current mass
        maximal_mass = unladen_mass + cargo_capacity + fuel_capacity  # minimal jump with min mass
        #log('info', 'minimal_mass', minimal_mass)
        #log('info', 'current_mass', current_mass)
        #log('info', 'maximal_mass', maximal_mass)
        
        base = lambda M, F: (drive_optimal_mass / M) * ((10**3 * F) / drive_linear_const )**(1/drive_power_const)
        # adding stuff here for more future fsd boost stuff 
        min_ly = (base(maximal_mass, drive_max_fuel) + fsd_boost) * (fsd_star_boost +fsd_inject)
        cur_ly = (base(current_mass, min(drive_max_fuel,current_fuel)) + fsd_boost) * (fsd_star_boost +fsd_inject)
        max_ly = (base(minimal_mass, drive_max_fuel) + fsd_boost) * (fsd_star_boost +fsd_inject)
        
        return min_ly, cur_ly, max_ly


class TargetStateModel(BaseModel):
    """Information about the currently targeted ship or entity."""
    EventID: Optional[str] = Field(default=None, description="Event identifier")
    Ship: Optional[str] = Field(default=None, description="Target ship type")
    ScanStage: Optional[int] = Field(default=None, description="Scan completion stage (0-3)")
    PilotName: Optional[str] = Field(default=None, description="Target pilot name")
    PilotRank: Optional[str] = Field(default=None, description="Target pilot combat rank")
    Faction: Optional[str] = Field(default=None, description="Target's faction")
    LegalStatus: Optional[str] = Field(default=None, description="Target's legal status")
    Bounty: Optional[int] = Field(default=None, description="Bounty on target in credits")
    ShieldHealth: Optional[float] = Field(default=None, description="Target shield health percentage")
    HullHealth: Optional[float] = Field(default=None, description="Target hull health percentage")
    SubsystemHealth: Optional[float] = Field(default=None, description="Targeted subsystem health percentage")
    Subsystem: Optional[str] = Field(default=None, description="Currently targeted subsystem name")


@final
class Target(Projection[TargetStateModel]):
    StateModel = TargetStateModel

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        global keys
        if isinstance(event, GameEvent) and event.content.get('event') in ['LoadGame', 'Shutdown']:
            self.state = TargetStateModel()
        if isinstance(event, GameEvent) and event.content.get('event') == 'ShipTargeted':
            if not event.content.get('TargetLocked', False):
                self.state = TargetStateModel()
            else:
                self.state = TargetStateModel()
                self.state.Ship = event.content.get('Ship_Localised', event.content.get('Ship', ''))
                self.state.ScanStage = int(event.content.get('ScanStage', 0) or 0)

                pilot_name_value = event.content.get('PilotName_Localised') or event.content.get('PilotName')
                if pilot_name_value:
                    self.state.PilotName = pilot_name_value

                if 'PilotRank' in event.content:
                    self.state.PilotRank = event.content.get('PilotRank', '')

                if 'Faction' in event.content:
                    self.state.Faction = event.content.get('Faction', '')

                if 'LegalStatus' in event.content:
                    self.state.LegalStatus = event.content.get('LegalStatus', '')

                if 'Bounty' in event.content:
                    self.state.Bounty = int(event.content.get('Bounty', 0) or 0)
                    if event.content.get('Bounty', 0) > 1 and not event.content.get('Subsystem', False):
                        projected_events.append(ProjectedEvent(content={"event": "BountyScanned"}))

                if 'ShieldHealth' in event.content:
                    self.state.ShieldHealth = float(event.content.get('ShieldHealth', 0.0) or 0.0)

                if 'HullHealth' in event.content:
                    self.state.HullHealth = float(event.content.get('HullHealth', 0.0) or 0.0)

                if 'SubsystemHealth' in event.content:
                    self.state.SubsystemHealth = float(event.content.get('SubsystemHealth', 0.0) or 0.0)

                subsystem_value = event.content.get('Subsystem_Localised', event.content.get('Subsystem', ''))
                if subsystem_value:
                    self.state.Subsystem = subsystem_value
            self.state.EventID = event.content.get('id')
        return projected_events


class NavRouteItem(BaseModel):
    """A waypoint in the navigation route."""
    StarSystem: str = Field(description="Star system name")
    Scoopable: bool = Field(description="Whether the star is fuel-scoopable (K/G/B/F/O/A/M class)")

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


@final
class StoredModules(Projection[StoredModulesStateModel]):
    StateModel = StoredModulesStateModel

    def _get_event_time(self, event: Event | None) -> datetime:
        if isinstance(event, GameEvent) and 'timestamp' in event.content:
            return datetime.fromisoformat(event.content.get('timestamp', '').replace('Z', '+00:00'))
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

        if isinstance(event, GameEvent) and event.content.get('event') == 'StoredModules':
            # Save the event as-is (all fields are required in the event)
            self.state.MarketID = event.content.get('MarketID', 0)
            self.state.StationName = event.content.get('StationName', '')
            self.state.StarSystem = event.content.get('StarSystem', '')
            self.state.Items = [StoredModuleItem(**item) for item in event.content.get('Items', [])]

        if isinstance(event, GameEvent) and event.content.get('event') == 'FetchRemoteModule':
            # Calculate completion timestamp using the event's timestamp
            transfer_time_seconds = event.content.get('TransferTime', 0)
            event_timestamp = datetime.fromisoformat(event.content.get('timestamp', datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00'))
            completion_time = event_timestamp + timedelta(seconds=transfer_time_seconds)
            now_utc = datetime.now(timezone.utc)
            is_due = completion_time <= now_utc

            # Create an item in transit using data from the event and current state
            transit_item = FetchRemoteModuleItem(
                Name=event.content.get('StoredItem_Localised', ""),
                MarketID=self.state.MarketID,
                StationName=self.state.StationName,
                StarSystem=self.state.StarSystem,
                StorageSlot=event.content.get('StorageSlot', 0),
                TransferCompleteTime=completion_time.isoformat(),
                TransferCost=event.content.get('TransferCost', 0),
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


@final
class StoredShips(Projection[StoredShipsStateModel]):
    StateModel = StoredShipsStateModel

    def _get_event_time(self, event: Event | None) -> datetime:
        if isinstance(event, GameEvent) and 'timestamp' in event.content:
            return datetime.fromisoformat(event.content.get('timestamp', '').replace('Z', '+00:00'))
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

        if isinstance(event, GameEvent) and event.content.get('event') == 'StoredShips':
            # Save the event as-is (all fields are required in the event)
            self.state.StationName = event.content.get('StationName', '')
            self.state.MarketID = event.content.get('MarketID', 0)
            self.state.StarSystem = event.content.get('StarSystem', '')
            self.state.ShipsHere = [ShipHereItem(**ship) for ship in event.content.get('ShipsHere', [])]
            self.state.ShipsRemote = [ShipRemoteItem(**ship) for ship in event.content.get('ShipsRemote', [])]

        if isinstance(event, GameEvent) and event.content.get('event') == 'ShipyardTransfer':
            # Calculate completion timestamp using the event's timestamp
            transfer_time_seconds = event.content.get('TransferTime', 0)
            event_timestamp = datetime.fromisoformat(event.content.get('timestamp', datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00'))
            completion_time = event_timestamp + timedelta(seconds=transfer_time_seconds)
            now_utc = datetime.now(timezone.utc)
            is_due = completion_time <= now_utc

            # Create a ship in transit using data from the event
            transit_item = ShipInTransitItem(
                ShipID=event.content.get('ShipID', 0),
                ShipType=event.content.get('ShipType', ''),
                System=self.state.StarSystem,
                ShipMarketID=self.state.MarketID,
                TransferCompleteTime=completion_time.isoformat(),
                TransferPrice=event.content.get('TransferPrice', 0),
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


class NavInfoStateModel(BaseModel):
    """Current navigation and route information."""
    NextJumpTarget: Optional[str] = Field(default='Unknown', description="Next FSD target system")
    NavRoute: list[NavRouteItem] = Field(default_factory=list, description="Remaining systems in plotted route")


@final
class NavInfo(Projection[NavInfoStateModel]):
    StateModel = NavInfoStateModel

    def __init__(self, system_db: SystemDatabase):
        super().__init__()
        self.system_db = system_db

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        # Process NavRoute event
        if isinstance(event, GameEvent) and event.content.get('event') == 'NavRoute':
            if event.content.get('Route', []):
                self.state.NavRoute = []
                systems_to_lookup = []
                
                # Process all systems in a single loop
                is_first_system = True
                for entry in event.content.get('Route', []):
                    star_system = entry.get("StarSystem", "Unknown")
                    star_class = entry.get("StarClass", "")
                    is_scoopable = star_class in ['K','G','B','F','O','A','M']
                    
                    # Add all systems to the lookup list
                    systems_to_lookup.append(star_system)
                    
                    # Add to projection state (skip the first one)
                    if not is_first_system:
                        self.state.NavRoute.append(NavRouteItem(
                            StarSystem=star_system,
                            Scoopable=is_scoopable
                        ))
                    else:
                        # No longer the first system after the first iteration
                        is_first_system = False
                
                # Fetch system data for systems in the route asynchronously
                if len(systems_to_lookup) > 1:
                    systems_to_lookup.pop(0)
                    self.system_db.fetch_multiple_systems_nonblocking(systems_to_lookup)

        # Process NavRouteClear
        if isinstance(event, GameEvent) and event.content.get('event') == 'NavRouteClear':
            self.state.NavRoute = []
            
        # Process FSDJump - remove visited systems from route
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump':
            for index, entry in enumerate(self.state.NavRoute):
                if entry.StarSystem == event.content.get('StarSystem'):
                    self.state.NavRoute = self.state.NavRoute[index+1:]
                    break

            if len(self.state.NavRoute) == 0 and self.state.NextJumpTarget is not None:
                self.state.NextJumpTarget = None

            # Calculate remaining jumps based on fuel
            fuel_level = event.content.get('FuelLevel', 0)
            fuel_used = event.content.get('FuelUsed', 0)
            remaining_jumps = int(fuel_level / fuel_used)

            # Check if we have enough scoopable stars between current and destination system)
            if not len(self.state.NavRoute) == 0 and remaining_jumps < len(self.state.NavRoute) - 1:
                # Count scoopable stars in the remaining jumps
                scoopable_stars = sum(
                    1 for entry in self.state.NavRoute[:remaining_jumps]
                    if entry.Scoopable
                )

                # Only warn if we can't reach any scoopable stars
                if scoopable_stars == 0:
                    projected_events.append(ProjectedEvent(content={"event": "NoScoopableStars"}))

        # Process FSDTarget
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDTarget':
            if 'Name' in event.content:
                system_name = event.content.get('Name', 'Unknown')
                self.state.NextJumpTarget = system_name

        if isinstance(event, GameEvent) and event.content.get('event') == 'Scan':
            auto_scan = event.content.get('ScanType')
            distancefromarrival = event.content.get('DistanceFromArrivalLS', 1)

            if auto_scan == 'AutoScan' and distancefromarrival < 0.2:  # pyright: ignore[reportOptionalOperand]
                was_discovered = event.content.get('WasDiscovered', True)  # system mapped

                if was_discovered == False:
                    projected_events.append(ProjectedEvent(content={"event": "FirstPlayerSystemDiscovered"}))

        return projected_events


class BackpackItem(BaseModel):
    """An item in the commander's backpack (on-foot inventory)."""
    Name: str = Field(description="Item internal name")
    OwnerID: int = Field(description="Owner identifier")
    Count: int = Field(description="Quantity of this item")
    Name_Localised: Optional[str] = Field(default=None, description="Human-readable item name")


class BackpackStateModel(BaseModel):
    """Commander's on-foot backpack inventory."""
    Items: list[BackpackItem] = Field(default_factory=list, description="General items")
    Components: list[BackpackItem] = Field(default_factory=list, description="Crafting components")
    Consumables: list[BackpackItem] = Field(default_factory=list, description="Consumable items (medkits, batteries, etc.)")
    Data: list[BackpackItem] = Field(default_factory=list, description="Data items")


@final
class Backpack(Projection[BackpackStateModel]):
    StateModel = BackpackStateModel
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent):
            # Full backpack update
            if event.content.get('event') == 'Backpack':
                # Reset and update all categories with proper BackpackItem parsing
                self.state.Items = [
                    BackpackItem(Name=i.get("Name", ""), OwnerID=i.get("OwnerID", 0),
                                Count=i.get("Count", 0), Name_Localised=i.get("Name_Localised"))
                    for i in event.content.get("Items", [])
                ]
                self.state.Components = [
                    BackpackItem(Name=i.get("Name", ""), OwnerID=i.get("OwnerID", 0),
                                Count=i.get("Count", 0), Name_Localised=i.get("Name_Localised"))
                    for i in event.content.get("Components", [])
                ]
                self.state.Consumables = [
                    BackpackItem(Name=i.get("Name", ""), OwnerID=i.get("OwnerID", 0),
                                Count=i.get("Count", 0), Name_Localised=i.get("Name_Localised"))
                    for i in event.content.get("Consumables", [])
                ]
                self.state.Data = [
                    BackpackItem(Name=i.get("Name", ""), OwnerID=i.get("OwnerID", 0),
                                Count=i.get("Count", 0), Name_Localised=i.get("Name_Localised"))
                    for i in event.content.get("Data", [])
                ]
            
            # Backpack additions
            elif event.content.get('event') == 'BackpackChange' and 'Added' in event.content:
                for item in event.content.get('Added', []):
                    item_type = item.get('Type', '')
                    new_item = BackpackItem(
                        Name=item.get('Name', ''),
                        OwnerID=item.get('OwnerID', 0),
                        Count=item.get('Count', 0),
                        Name_Localised=item.get('Name_Localised'),
                    )
                    
                    if item_type == 'Item':
                        self._add_or_update_item("Items", new_item)
                    elif item_type == 'Component':
                        self._add_or_update_item("Components", new_item)
                    elif item_type == 'Consumable':
                        self._add_or_update_item("Consumables", new_item)
                    elif item_type == 'Data':
                        self._add_or_update_item("Data", new_item)
            
            # Backpack removals
            elif event.content.get('event') == 'BackpackChange' and 'Removed' in event.content:
                for item in event.content.get('Removed', []):
                    item_type = item.get('Type', '')
                    item_name = item.get('Name', '')
                    item_count = item.get('Count', 0)
                    
                    if item_type == 'Item':
                        self._remove_item("Items", item_name, item_count)
                    elif item_type == 'Component':
                        self._remove_item("Components", item_name, item_count)
                    elif item_type == 'Consumable':
                        self._remove_item("Consumables", item_name, item_count)
                    elif item_type == 'Data':
                        self._remove_item("Data", item_name, item_count)
    
    def _add_or_update_item(self, category: str, new_item: BackpackItem) -> None:
        """Add a new item or update the count of an existing item in the specified category."""
        category_list: list[BackpackItem] = getattr(self.state, category)
        for item in category_list:
            if item.Name == new_item.Name:
                # Item exists, update count
                item.Count += new_item.Count
                return
        
        # Item doesn't exist, add it
        category_list.append(new_item)
    
    def _remove_item(self, category: str, item_name: str, count: int) -> None:
        """Remove an item or reduce its count in the specified category."""
        category_list: list[BackpackItem] = getattr(self.state, category)
        for i, item in enumerate(category_list):
            if item.Name == item_name:
                # Reduce count
                item.Count -= count
                
                # Remove item if count is zero or less
                if item.Count <= 0:
                    category_list.pop(i)
                
                break


class ExobiologyScanStateScan(BaseModel):
    """Location of an exobiology scan sample."""
    lat: float = Field(description="Latitude of the scan location")
    long: float = Field(description="Longitude of the scan location")


class ExobiologyScanStateModel(BaseModel):
    """Current exobiology scanning state."""
    within_scan_radius: Optional[bool] = Field(default=True, description="Whether commander is within minimum sample distance")
    scan_radius: Optional[int] = Field(default=None, description="Required distance between samples in meters")
    scans: list[ExobiologyScanStateScan] = Field(default_factory=list, description="Locations of completed scans")
    lat: Optional[float] = Field(default=None, description="Commander's current latitude")
    long: Optional[float] = Field(default=None, description="Commander's current longitude")
    life_form: Optional[str] = Field(default=None, description="Currently scanned life form species")


@final
class ExobiologyScan(Projection[ExobiologyScanStateModel]):
    StateModel = ExobiologyScanStateModel

    colony_size = {
        "Aleoids_Genus_Name": 150,      # Aleoida
        "Vents_Genus_Name": 100,        # Amphora Plant
        "Sphere_Genus_Name": 100,       # Anemone
        "Bacterial_Genus_Name": 500,    # Bacterium
        "Cone_Genus_Name": 100,         # Bark Mound
        "Brancae_Name": 100,            # Brain Tree
        "Cactoid_Genus_Name": 300,      # Cactoida
        "Clypeus_Genus_Name": 150,      # Clypeus
        "Conchas_Genus_Name": 150,      # Concha
        "Shards_Genus_Name": 100,       # Crystalline Shard
        "Electricae_Genus_Name": 1000,  # Electricae
        "Fonticulus_Genus_Name": 500,   # Fonticulua
        "Shrubs_Genus_Name": 150,       # Frutexa
        "Fumerolas_Genus_Name": 100,    # Fumerola
        "Fungoids_Genus_Name": 300,     # Fungoida
        "Osseus_Genus_Name": 800,       # Osseus
        "Recepta_Genus_Name": 150,      # Recepta
        "Tube_Genus_Name": 100,         # Sinuous Tuber
        "Stratum_Genus_Name": 500,      # Stratum
        "Tubus_Genus_Name": 800,        # Tubus
        "Tussocks_Genus_Name": 200      # Tussock
    }

    def haversine_distance(self, new_value: ExobiologyScanStateScan, old_value: ExobiologyScanStateScan, radius: int):
        lat1, lon1 = math.radians(new_value.lat), math.radians(new_value.long)
        lat2, lon2 = math.radians(old_value.lat), math.radians(old_value.long)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Haversine formula
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = radius * c
        return distance

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            self.state.lat = event.status.get("Latitude", 0)
            self.state.long = event.status.get("Longitude", 0)

            if self.state.scans and self.state.scan_radius:
                in_scan_radius = False
                if (self.state.lat != 0 and self.state.long != 0 and
                    event.status.get('PlanetRadius', False)):
                    distance_obj = ExobiologyScanStateScan(lat=self.state.lat, long=self.state.long)
                    for scan in self.state.scans:
                        distance = self.haversine_distance(scan, distance_obj, event.status['PlanetRadius'])
                        # self.state.distance = distance
                        # log('info', 'distance', distance)
                        if distance < self.state.scan_radius:
                            in_scan_radius = True
                            break
                    if in_scan_radius:
                        if not self.state.within_scan_radius:
                            projected_events.append(ProjectedEvent(content={"event": "ScanOrganicTooClose"}))
                            self.state.within_scan_radius = in_scan_radius
                    else:
                        if self.state.within_scan_radius:
                            projected_events.append(ProjectedEvent(content={"event": "ScanOrganicFarEnough"}))
                            self.state.within_scan_radius = in_scan_radius
                else:
                    # log('info', 'status missing')
                    if self.state.scans:
                        self.state.scans.clear()
                        self.state.scan_radius = None


        if isinstance(event, GameEvent) and event.content.get('event') == 'ScanOrganic':
            content = event.content
            if content["ScanType"] == "Log":
                self.state.scans.clear()
                self.state.scans.append(ExobiologyScanStateScan(lat=self.state.lat or 0, long=self.state.long or 0))
                self.state.scan_radius = self.colony_size[content['Genus'][11:-1]]
                species = event.content.get('Species_Localised', event.content.get('Species', 'unknown species'))
                variant = event.content.get('Variant_Localised', event.content.get('Variant', ''))
                if variant and variant != species:
                    life_form = f"{variant} ({species})"
                else:
                    life_form = f"{species}"
                self.state.life_form = life_form
                self.state.within_scan_radius = True
                projected_events.append(ProjectedEvent(content={**content, "event": "ScanOrganicFirst", "NewSampleDistance":self.state.scan_radius}))

            elif content["ScanType"] == "Sample":
                if len(self.state.scans) == 1:
                    self.state.scans.append(ExobiologyScanStateScan(lat=self.state.lat or 0, long=self.state.long or 0))
                    self.state.within_scan_radius = True
                    projected_events.append(ProjectedEvent(content={**content, "event": "ScanOrganicSecond"}))
                elif len(self.state.scans) == 2:
                    projected_events.append(ProjectedEvent(content={**content, "event": "ScanOrganicThird"}))
                    if self.state.scans:
                        self.state.scans.clear()
                        self.state.scan_radius = None
                else:
                    projected_events.append(ProjectedEvent(content={**content, "event": "ScanOrganic"}))

            elif content["ScanType"] == "Analyse":
                pass

        if isinstance(event, GameEvent) and event.content.get('event') in ['SupercruiseEntry','FSDJump','Died','Shutdown','JoinACrew']:
            self.state.scans.clear()
            self.state.scan_radius = None

        return projected_events


class SuitWeaponModule(BaseModel):
    """A weapon or tool equipped in the suit loadout."""
    SlotName: str = Field(description="Equipment slot name")
    SuitModuleID: int = Field(description="Module unique identifier")
    ModuleName: str = Field(description="Module internal name")
    ModuleName_Localised: str = Field(description="Human-readable module name")
    Class: int = Field(description="Module class/grade (1-5)")
    WeaponMods: list[str] = Field(default_factory=list, description="Applied weapon modifications")


class SuitLoadoutStateModel(BaseModel):
    """Commander's current on-foot suit loadout."""
    SuitID: int = Field(default=0, description="Suit unique identifier")
    SuitName: str = Field(default="Unknown", description="Suit internal name")
    SuitName_Localised: str = Field(default="Unknown", description="Human-readable suit name")
    SuitMods: list[str] = Field(default_factory=list, description="Applied suit modifications")
    LoadoutID: int = Field(default=0, description="Loadout unique identifier")
    LoadoutName: str = Field(default="Unknown", description="Custom loadout name")
    Modules: list[SuitWeaponModule] = Field(default_factory=list, description="Equipped weapons and tools")


@final
class SuitLoadout(Projection[SuitLoadoutStateModel]):
    StateModel = SuitLoadoutStateModel
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'SuitLoadout':
            # Update the entire state with the new loadout information
            self.state.SuitID = event.content.get('SuitID', 0)
            self.state.SuitName = event.content.get('SuitName', 'Unknown')
            self.state.SuitName_Localised = event.content.get('SuitName_Localised', 'Unknown')
            self.state.SuitMods = event.content.get('SuitMods', [])
            self.state.LoadoutID = event.content.get('LoadoutID', 0)
            self.state.LoadoutName = event.content.get('LoadoutName', 'Unknown')
            
            # Process weapon modules with proper SuitWeaponModule instantiation
            self.state.Modules = [
                SuitWeaponModule(
                    SlotName=module.get('SlotName', 'Unknown'),
                    SuitModuleID=module.get('SuitModuleID', 0),
                    ModuleName=module.get('ModuleName', 'Unknown'),
                    ModuleName_Localised=module.get('ModuleName_Localised', 'Unknown'),
                    Class=module.get('Class', 0),
                    WeaponMods=module.get('WeaponMods', []),
                )
                for module in event.content.get('Modules', [])
            ]


class OnlineFriendsStateModel(BaseModel):
    """Commander's friends list status."""
    Online: list[str] = Field(default_factory=list, description="Names of currently online friends")
    Pending: list[str] = Field(default_factory=list, description="Names of pending friend requests")


@final
class Friends(Projection[OnlineFriendsStateModel]):
    StateModel = OnlineFriendsStateModel

    @override
    def process(self, event: Event) -> None:
        # Clear the list on Fileheader event (new game session)
        if isinstance(event, GameEvent) and event.content.get('event') == 'Fileheader':
            self.state.Online = []
            self.state.Pending = []

        # Process Friends events
        if isinstance(event, GameEvent) and event.content.get('event') == 'Friends':
            friend_name = event.content.get('Name', '')
            friend_status = event.content.get('Status', '')

            # Skip if missing crucial information
            if not friend_name or not friend_status:
                return

            # If the friend is coming online, add them to the list
            if friend_status in ["Online", "Added"]:
                if friend_name not in self.state.Online:
                    self.state.Online.append(friend_name)
                if friend_name in self.state.Pending:
                    self.state.Pending.remove(friend_name)

            elif friend_status == "Requested":
                if friend_name not in self.state.Pending:
                    self.state.Pending.append(friend_name)

            # If the friend was previously online but now has a different status, remove them
            elif friend_name in self.state.Online and friend_status in ["Offline", "Lost"]:
                self.state.Online.remove(friend_name)

            elif friend_status == "Declined":
                if friend_name in self.state.Pending:
                    self.state.Pending.remove(friend_name)


MaterialsCategory = Literal['Raw', 'Manufactured', 'Encoded']


class MaterialEntry(BaseModel):
    """A material in the commander's inventory."""
    Name: str = Field(description="Material internal name")
    Count: int = Field(default=0, description="Quantity of this material")
    Name_Localised: Optional[str] = Field(default=None, description="Human-readable material name")


MATERIAL_TEMPLATE: dict[MaterialsCategory, list[dict]] = {
    "Raw": [
        {"Name": "carbon", "Count": 0},
        {"Name": "phosphorus", "Count": 0},
        {"Name": "sulphur", "Count": 0},
        {"Name": "iron", "Count": 0},
        {"Name": "polonium", "Count": 0},
        {"Name": "manganese", "Count": 0},
        {"Name": "molybdenum", "Count": 0},
        {"Name": "arsenic", "Count": 0},
        {"Name": "nickel", "Count": 0},
        {"Name": "vanadium", "Count": 0},
        {"Name": "mercury", "Count": 0},
        {"Name": "ruthenium", "Count": 0},
        {"Name": "tellurium", "Count": 0},
        {"Name": "tungsten", "Count": 0},
        {"Name": "zinc", "Count": 0},
        {"Name": "technetium", "Count": 0},
        {"Name": "yttrium", "Count": 0},
        {"Name": "antimony", "Count": 0},
        {"Name": "selenium", "Count": 0},
        {"Name": "boron", "Count": 0},
        {"Name": "zirconium", "Count": 0},
        {"Name": "lead", "Count": 0},
        {"Name": "rhenium", "Count": 0},
        {"Name": "germanium", "Count": 0},
        {"Name": "tin", "Count": 0},
        {"Name": "chromium", "Count": 0},
        {"Name": "niobium", "Count": 0},
        {"Name": "cadmium", "Count": 0},
    ],
    "Manufactured": [
        {"Name": "conductiveceramics", "Name_Localised": "Conductive Ceramics", "Count": 0},
        {"Name": "heatdispersionplate", "Name_Localised": "Heat Dispersion Plate", "Count": 0},
        {"Name": "mechanicalcomponents", "Name_Localised": "Mechanical Components", "Count": 0},
        {"Name": "chemicalprocessors", "Name_Localised": "Chemical Processors", "Count": 0},
        {"Name": "conductivecomponents", "Name_Localised": "Conductive Components", "Count": 0},
        {"Name": "heatexchangers", "Name_Localised": "Heat Exchangers", "Count": 0},
        {"Name": "shieldemitters", "Name_Localised": "Shield Emitters", "Count": 0},
        {"Name": "phasealloys", "Name_Localised": "Phase Alloys", "Count": 0},
        {"Name": "precipitatedalloys", "Name_Localised": "Precipitated Alloys", "Count": 0},
        {"Name": "focuscrystals", "Name_Localised": "Focus Crystals", "Count": 0},
        {"Name": "mechanicalequipment", "Name_Localised": "Mechanical Equipment", "Count": 0},
        {"Name": "heatconductionwiring", "Name_Localised": "Heat Conduction Wiring", "Count": 0},
        {"Name": "basicconductors", "Name_Localised": "Basic Conductors", "Count": 0},
        {"Name": "shieldingsensors", "Name_Localised": "Shielding Sensors", "Count": 0},
        {"Name": "heatvanes", "Name_Localised": "Heat Vanes", "Count": 0},
        {"Name": "filamentcomposites", "Name_Localised": "Filament Composites", "Count": 0},
        {"Name": "chemicaldistillery", "Name_Localised": "Chemical Distillery", "Count": 0},
        {"Name": "salvagedalloys", "Name_Localised": "Salvaged Alloys", "Count": 0},
        {"Name": "configurablecomponents", "Name_Localised": "Configurable Components", "Count": 0},
        {"Name": "highdensitycomposites", "Name_Localised": "High Density Composites", "Count": 0},
        {"Name": "refinedfocuscrystals", "Name_Localised": "Refined Focus Crystals", "Count": 0},
        {"Name": "crystalshards", "Name_Localised": "Crystal Shards", "Count": 0},
        {"Name": "compoundshielding", "Name_Localised": "Compound Shielding", "Count": 0},
        {"Name": "conductivepolymers", "Name_Localised": "Conductive Polymers", "Count": 0},
        {"Name": "wornshieldemitters", "Name_Localised": "Worn Shield Emitters", "Count": 0},
        {"Name": "uncutfocuscrystals", "Name_Localised": "Flawed Focus Crystals", "Count": 0},
        {"Name": "mechanicalscrap", "Name_Localised": "Mechanical Scrap", "Count": 0},
        {"Name": "galvanisingalloys", "Name_Localised": "Galvanising Alloys", "Count": 0},
        {"Name": "hybridcapacitors", "Name_Localised": "Hybrid Capacitors", "Count": 0},
        {"Name": "polymercapacitors", "Name_Localised": "Polymer Capacitors", "Count": 0},
        {"Name": "electrochemicalarrays", "Name_Localised": "Electrochemical Arrays", "Count": 0},
        {"Name": "chemicalmanipulators", "Name_Localised": "Chemical Manipulators", "Count": 0},
        {"Name": "heatresistantceramics", "Name_Localised": "Heat Resistant Ceramics", "Count": 0},
        {"Name": "chemicalstorageunits", "Name_Localised": "Chemical Storage Units", "Count": 0},
        {"Name": "compactcomposites", "Name_Localised": "Compact Composites", "Count": 0},
        {"Name": "exquisitefocuscrystals", "Name_Localised": "Exquisite Focus Crystals", "Count": 0},
        {"Name": "biotechconductors", "Name_Localised": "Biotech Conductors", "Count": 0},
        {"Name": "gridresistors", "Name_Localised": "Grid Resistors", "Count": 0},
        {"Name": "guardian_sentinel_wreckagecomponents", "Name_Localised": "Guardian Wreckage Components", "Count": 0},
        {"Name": "guardian_powerconduit", "Name_Localised": "Guardian Power Conduit", "Count": 0},
        {"Name": "guardian_sentinel_weaponparts", "Name_Localised": "Guardian Sentinel Weapon Parts", "Count": 0},
        {"Name": "guardian_techcomponent", "Name_Localised": "Guardian Technology Component", "Count": 0},
        {"Name": "guardian_powercell", "Name_Localised": "Guardian Power Cell", "Count": 0},
        {"Name": "imperialshielding", "Name_Localised": "Imperial Shielding", "Count": 0},
        {"Name": "fedcorecomposites", "Name_Localised": "Core Dynamics Composites", "Count": 0},
        {"Name": "fedproprietarycomposites", "Name_Localised": "Proprietary Composites", "Count": 0},
        {"Name": "protoradiolicalloys", "Name_Localised": "Proto Radiolic Alloys", "Count": 0},
        {"Name": "protolightalloys", "Name_Localised": "Proto Light Alloys", "Count": 0},
        {"Name": "temperedalloys", "Name_Localised": "Tempered Alloys", "Count": 0},
        {"Name": "unknownenergysource", "Name_Localised": "Sensor Fragment", "Count": 0},
        {"Name": "pharmaceuticalisolators", "Name_Localised": "Pharmaceutical Isolators", "Count": 0},
        {"Name": "tg_wreckagecomponents", "Name_Localised": "Wreckage Components", "Count": 0},
        {"Name": "tg_biomechanicalconduits", "Name_Localised": "Bio-Mechanical Conduits", "Count": 0},
        {"Name": "tg_weaponparts", "Name_Localised": "Weapon Parts", "Count": 0},
        {"Name": "tg_propulsionelement", "Name_Localised": "Propulsion Elements", "Count": 0},
        {"Name": "militarygradealloys", "Name_Localised": "Military Grade Alloys", "Count": 0},
        {"Name": "thermicalloys", "Name_Localised": "Thermic Alloys", "Count": 0},
        {"Name": "improvisedcomponents", "Name_Localised": "Improvised Components", "Count": 0},
        {"Name": "protoheatradiators", "Name_Localised": "Proto Heat Radiators", "Count": 0},
        {"Name": "militarysupercapacitors", "Name_Localised": "Military Supercapacitors", "Count": 0},
        {"Name": "tg_causticgeneratorparts", "Name_Localised": "Corrosive Mechanisms", "Count": 0},
        {"Name": "tg_causticcrystal", "Name_Localised": "Caustic Crystal", "Count": 0},
        {"Name": "tg_causticshard", "Name_Localised": "Caustic Shard", "Count": 0},
        {"Name": "unknowncarapace", "Name_Localised": "Thargoid Carapace", "Count": 0},
        {"Name": "tg_abrasion02", "Name_Localised": "Phasing Membrane Residue", "Count": 0},
        {"Name": "tg_abrasion03", "Name_Localised": "Hardened Surface Fragments", "Count": 0},
        {"Name": "unknownenergycell", "Name_Localised": "Thargoid Energy Cell", "Count": 0},
        {"Name": "unknowncorechip", "Name_Localised": "Tactical Core Chip", "Count": 0},
        {"Name": "unknowntechnologycomponents", "Name_Localised": "Thargoid Technological Components", "Count": 0},
    ],
    "Encoded": [
        {"Name": "archivedemissiondata", "Name_Localised": "Irregular Emission Data", "Count": 0},
        {"Name": "shieldpatternanalysis", "Name_Localised": "Aberrant Shield Pattern Analysis", "Count": 0},
        {"Name": "scanarchives", "Name_Localised": "Unidentified Scan Archives", "Count": 0},
        {"Name": "bulkscandata", "Name_Localised": "Anomalous Bulk Scan Data", "Count": 0},
        {"Name": "shielddensityreports", "Name_Localised": "Untypical Shield Scans", "Count": 0},
        {"Name": "adaptiveencryptors", "Name_Localised": "Adaptive Encryptors Capture", "Count": 0},
        {"Name": "encryptionarchives", "Name_Localised": "Atypical Encryption Archives", "Count": 0},
        {"Name": "consumerfirmware", "Name_Localised": "Modified Consumer Firmware", "Count": 0},
        {"Name": "industrialfirmware", "Name_Localised": "Cracked Industrial Firmware", "Count": 0},
        {"Name": "disruptedwakeechoes", "Name_Localised": "Atypical Disrupted Wake Echoes", "Count": 0},
        {"Name": "wakesolutions", "Name_Localised": "Strange Wake Solutions", "Count": 0},
        {"Name": "hyperspacetrajectories", "Name_Localised": "Eccentric Hyperspace Trajectories", "Count": 0},
        {"Name": "dataminedwake", "Name_Localised": "Datamined Wake Exceptions", "Count": 0},
        {"Name": "legacyfirmware", "Name_Localised": "Specialised Legacy Firmware", "Count": 0},
        {"Name": "emissiondata", "Name_Localised": "Unexpected Emission Data", "Count": 0},
        {"Name": "scandatabanks", "Name_Localised": "Classified Scan Databanks", "Count": 0},
        {"Name": "encryptedfiles", "Name_Localised": "Unusual Encrypted Files", "Count": 0},
        {"Name": "securityfirmware", "Name_Localised": "Security Firmware Patch", "Count": 0},
        {"Name": "fsdtelemetry", "Name_Localised": "Anomalous FSD Telemetry", "Count": 0},
        {"Name": "embeddedfirmware", "Name_Localised": "Modified Embedded Firmware", "Count": 0},
        {"Name": "shieldsoakanalysis", "Name_Localised": "Inconsistent Shield Soak Analysis", "Count": 0},
        {"Name": "encryptioncodes", "Name_Localised": "Tagged Encryption Codes", "Count": 0},
        {"Name": "tg_interdictiondata", "Name_Localised": "Thargoid Interdiction Telemetry", "Count": 0},
        {"Name": "shieldcyclerecordings", "Name_Localised": "Distorted Shield Cycle Recordings", "Count": 0},
        {"Name": "ancientculturaldata", "Name_Localised": "Pattern Beta Obelisk Data", "Count": 0},
        {"Name": "ancientlanguagedata", "Name_Localised": "Pattern Delta Obelisk Data", "Count": 0},
        {"Name": "ancienthistoricaldata", "Name_Localised": "Pattern Gamma Obelisk Data", "Count": 0},
        {"Name": "ancientbiologicaldata", "Name_Localised": "Pattern Alpha Obelisk Data", "Count": 0},
        {"Name": "ancienttechnologicaldata", "Name_Localised": "Pattern Epsilon Obelisk Data", "Count": 0},
        {"Name": "symmetrickeys", "Name_Localised": "Open Symmetric Keys", "Count": 0},
        {"Name": "encodedscandata", "Name_Localised": "Divergent Scan Data", "Count": 0},
        {"Name": "decodedemissiondata", "Name_Localised": "Decoded Emission Data", "Count": 0},
        {"Name": "scrambledemissiondata", "Name_Localised": "Exceptional Scrambled Emission Data", "Count": 0},
        {"Name": "guardian_vesselblueprint", "Name_Localised": "Guardian Vessel Blueprint Fragment", "Count": 0},
        {"Name": "shieldfrequencydata", "Name_Localised": "Peculiar Shield Frequency Data", "Count": 0},
        {"Name": "tg_shutdowndata", "Name_Localised": "Massive Energy Surge Analytics", "Count": 0},
        {"Name": "classifiedscandata", "Name_Localised": "Classified Scan Fragment", "Count": 0},
        {"Name": "tg_shipflightdata", "Name_Localised": "Ship Flight Data", "Count": 0},
        {"Name": "unknownshipsignature", "Name_Localised": "Thargoid Ship Signature", "Count": 0},
        {"Name": "compactemissionsdata", "Name_Localised": "Abnormal Compact Emissions Data", "Count": 0},
        {"Name": "tg_shipsystemsdata", "Name_Localised": "Ship Systems Data", "Count": 0},
    ]
}

MATERIAL_NAME_LOOKUP: dict[str, MaterialsCategory] = {
    entry['Name'].lower(): category
    for category, items in MATERIAL_TEMPLATE.items()
    for entry in items
}


class MaterialsStateModel(BaseModel):
    """Commander's materials inventory for engineering and synthesis."""
    Raw: list[MaterialEntry] = Field(default_factory=lambda: [MaterialEntry(**entry) for entry in MATERIAL_TEMPLATE["Raw"]], description="Raw materials from mining and surface prospecting")
    Manufactured: list[MaterialEntry] = Field(default_factory=lambda: [MaterialEntry(**entry) for entry in MATERIAL_TEMPLATE["Manufactured"]], description="Manufactured materials from salvage and combat")
    Encoded: list[MaterialEntry] = Field(default_factory=lambda: [MaterialEntry(**entry) for entry in MATERIAL_TEMPLATE["Encoded"]], description="Encoded data from scanning")
    LastUpdated: str = Field(default="", description="Timestamp of last materials update")


@final
class Materials(Projection[MaterialsStateModel]):
    StateModel = MaterialsStateModel
    MATERIAL_CATEGORIES: tuple[MaterialsCategory, ...] = ('Raw', 'Manufactured', 'Encoded')
    TEMPLATE = MATERIAL_TEMPLATE
    LOOKUP = MATERIAL_NAME_LOOKUP

    def _get_bucket(self, category: MaterialsCategory) -> list[MaterialEntry]:
        return getattr(self.state, category)

    @override
    def process(self, event: Event) -> None:
        if not isinstance(event, GameEvent):
            return

        content = event.content
        event_name = content.get('event')

        # Update the stored timestamp when new data arrives.
        def update_timestamp():
            timestamp = content.get('timestamp')
            if isinstance(timestamp, str) and timestamp:
                self.state.LastUpdated = timestamp

        # Apply a delta to the appropriate material entry, creating it if needed.
        def update_material(name: str | None, delta: int, category: str | None = None, localized: str | None = None):
            if not name or delta == 0:
                return
            name_key = name.lower()
            bucket_name: MaterialsCategory | None = None
            if category:
                normalized = category.strip().lower()
                for option in self.MATERIAL_CATEGORIES:
                    if option.lower() == normalized:
                        bucket_name = option
                        break
            if not bucket_name:
                bucket_name = self.LOOKUP.get(name_key)
            if not bucket_name:
                return
            bucket = self._get_bucket(bucket_name)
            for entry in bucket:
                if entry.Name.lower() == name_key:
                    entry.Count = max(0, entry.Count + delta)
                    if localized:
                        entry.Name_Localised = localized
                    return
            if delta > 0:
                new_entry = MaterialEntry(Name=name, Count=delta, Name_Localised=localized)
                bucket.append(new_entry)

        if event_name == 'Materials':
            for category in self.MATERIAL_CATEGORIES:
                items = content.get(category, [])
                incoming = {}
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get('Name'):
                            incoming[item['Name']] = item
                bucket = self._get_bucket(category)
                for entry in bucket:
                    payload = incoming.pop(entry.Name, None)
                    if payload:
                        entry.Count = payload.get('Count', 0) or 0
                        if payload.get('Name_Localised'):
                            entry.Name_Localised = payload['Name_Localised']
                    else:
                        entry.Count = 0
                for payload in incoming.values():
                    new_entry = MaterialEntry(
                        Name=payload['Name'],
                        Count=payload.get('Count', 0) or 0,
                        Name_Localised=payload.get('Name_Localised'),
                    )
                    bucket.append(new_entry)
            update_timestamp()
            return

        if event_name == 'MaterialTrade':
            paid = content.get('Paid')
            if isinstance(paid, dict):
                quantity = paid.get('Quantity', 0)
                if isinstance(quantity, int):
                    update_material(paid.get('Material'), -quantity, paid.get('Category'), paid.get('Material_Localised'))
            received = content.get('Received')
            if isinstance(received, dict):
                quantity = received.get('Quantity', 0)
                if isinstance(quantity, int):
                    update_material(received.get('Material'), quantity, received.get('Category'), received.get('Material_Localised'))
            update_timestamp()
            return

        if event_name == 'MaterialCollected':
            count_value = content.get('Count', 0)
            if isinstance(count_value, int):
                update_material(content.get('Name'), count_value, content.get('Category'), content.get('Name_Localised'))
                update_timestamp()
            return

        if event_name == 'TechnologyBroker':
            materials = content.get('Materials')
            if isinstance(materials, list):
                for material in materials:
                    if isinstance(material, dict):
                        count_value = material.get('Count', 0)
                        if isinstance(count_value, int):
                            update_material(material.get('Name'), -count_value, material.get('Category'), material.get('Name_Localised'))
            update_timestamp()
            return

        if event_name == 'EngineerCraft':
            ingredients = content.get('Ingredients')
            if isinstance(ingredients, list):
                for ingredient in ingredients:
                    if isinstance(ingredient, dict):
                        count_value = ingredient.get('Count', 0)
                        if isinstance(count_value, int):
                            update_material(ingredient.get('Name'), -count_value, None, ingredient.get('Name_Localised'))
            update_timestamp()
            return

        if event_name == 'Synthesis':
            materials = content.get('Materials')
            if isinstance(materials, list):
                for material in materials:
                    if isinstance(material, dict):
                        count_value = material.get('Count', 0)
                        if isinstance(count_value, int):
                            update_material(material.get('Name'), -count_value)
            update_timestamp()


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


@final
class ColonisationConstruction(Projection[ColonisationConstructionStateModel]):
    StateModel = ColonisationConstructionStateModel

    @override
    def process(self, event: Event) -> None:
        # Process ColonisationConstructionDepot events
        if isinstance(event, GameEvent) and event.content.get('event') == 'ColonisationConstructionDepot':
            # Update construction status
            self.state.ConstructionProgress = event.content.get('ConstructionProgress', 0.0)
            self.state.ConstructionComplete = event.content.get('ConstructionComplete', False)
            self.state.ConstructionFailed = event.content.get('ConstructionFailed', False)
            self.state.MarketID = event.content.get('MarketID', 0)

            # Update resources required with proper ColonisationResourceItem parsing
            raw_resources = event.content.get('ResourcesRequired', [])
            if raw_resources:
                self.state.ResourcesRequired = [
                    ColonisationResourceItem(
                        Name=r.get('Name', ''),
                        Name_Localised=r.get('Name_Localised', ''),
                        RequiredAmount=r.get('RequiredAmount', 0),
                        ProvidedAmount=r.get('ProvidedAmount', 0),
                        Payment=r.get('Payment', 0),
                    )
                    for r in raw_resources
                ]
            self.state.StarSystem = self.state.StarSystemRecall

        if isinstance(event, GameEvent) and event.content.get('event') == 'Docked':
            # If we have an active construction and dock at a non-construction station
            # with the same MarketID, the construction has concluded. Reset to defaults.
            if self.state.MarketID and not self.state.ConstructionComplete and not self.state.ConstructionFailed:
                docked_market_id = event.content.get('MarketID', 0)
                station_type = event.content.get('StationType', '')
                if docked_market_id == self.state.MarketID and 'construction' not in station_type.lower():
                    self.state = ColonisationConstructionStateModel()

        if isinstance(event, GameEvent) and event.content.get('event') == 'Location':
            self.state.StarSystemRecall = event.content.get('StarSystem', 'Unknown')

        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseEntry':
            self.state.StarSystemRecall = event.content.get('StarSystem', 'Unknown')

        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseExit':
            self.state.StarSystemRecall = event.content.get('StarSystem', 'Unknown')

        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump':
            self.state.StarSystemRecall = event.content.get('StarSystem', 'Unknown')


class DockingEventsStateModel(BaseModel):
    """Current docking status and events."""
    StationType: str = Field(default='Unknown', description="Type of station (Coriolis/Orbis/Ocellus/Outpost/etc.)")
    LastEventType: str = Field(default='Unknown', description="Last docking-related event type")
    DockingComputerState: str = Field(default='deactivated', description="Docking computer state: deactivated/activated/auto-docking")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last docking event")


@final
class DockingEvents(Projection[DockingEventsStateModel]):
    StateModel = DockingEventsStateModel

    @override
    def process(self, event: Event) -> list[ProjectedEvent] | None:
        projected_events: list[ProjectedEvent] = []
        
        if isinstance(event, GameEvent) and event.content.get('event') in ['Docked', 'Undocked', 'DockingGranted', 'DockingRequested', 'DockingCanceled', 'DockingDenied', 'DockingTimeout']:
            self.state.DockingComputerState = "deactivated"
            self.state.StationType = event.content.get("StationType", "Unknown")
            self.state.LastEventType = event.content.get("event", "Unknown")
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if isinstance(event, GameEvent) and event.content.get('event') == 'Music':
            if event.content.get('MusicTrack', "Unknown") == "DockingComputer":
                self.state.DockingComputerState = 'activated'
                if self.state.LastEventType == "DockingGranted":
                    self.state.DockingComputerState = "auto-docking"
                    projected_events.append(ProjectedEvent(content={"event": "DockingComputerDocking"}))

                elif self.state.LastEventType == "Undocked" and self.state.StationType in ['Coriolis', 'Orbis', 'Ocellus']:
                    self.state.DockingComputerState = "auto-docking"
                    projected_events.append(ProjectedEvent(content={"event": "DockingComputerUndocking"}))

            elif self.state.DockingComputerState == "auto-docking":
                self.state.DockingComputerState = "deactivated"
                projected_events.append(ProjectedEvent(content={"event": "DockingComputerDeactivated"}))

        return projected_events

# Define types for Powerplay Projection
class PowerplayStateModel(BaseModel):
    """Powerplay status of the commander."""
    Power: str = Field(default="Unknown", description="Power name")
    Rank: int = Field(default=0, description="Powerplay rank")
    Merits: int = Field(default=0, description="Current merits")
    TimePledged: int = Field(default=0, description="Seconds pledged to the power")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last Powerplay event")


@final
class Powerplay(Projection[PowerplayStateModel]):
    StateModel = PowerplayStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent):
            event_name = event.content.get('event')

            if event_name == 'Powerplay':
                self.state.Power = event.content.get('Power', 'Unknown')
                self.state.Rank = event.content.get('Rank', 0)
                self.state.Merits = event.content.get('Merits', 0)
                self.state.TimePledged = event.content.get('TimePledged', 0)
                if 'timestamp' in event.content:
                    self.state.Timestamp = event.content['timestamp']

            if event_name == 'PowerplayMerits':
                self.state.Merits = event.content.get('TotalMerits', self.state.Merits)
                if 'timestamp' in event.content:
                    self.state.Timestamp = event.content['timestamp']

            if event_name == 'PowerplayRank':
                self.state.Rank = event.content.get('Rank', self.state.Rank)
                if 'timestamp' in event.content:
                    self.state.Timestamp = event.content['timestamp']

            if event_name == 'PowerplayJoin':
                self.state.Power = event.content.get('Power', 'Unknown')
                self.state.Rank = 0
                self.state.Merits = 0
                self.state.TimePledged = 0
                if 'timestamp' in event.content:
                    self.state.Timestamp = event.content['timestamp']

            if event_name == 'PowerplayDefect':
                self.state.Power = event.content.get('ToPower', 'Unknown')
                self.state.Rank = 0
                self.state.Merits = 0
                self.state.TimePledged = 0
                if 'timestamp' in event.content:
                    self.state.Timestamp = event.content['timestamp']

            if event_name == 'PowerplayLeave':
                self.state = PowerplayStateModel()

# Define types for Rank/Progress Projection
class RankProgressEntry(BaseModel):
    """Rank and progress for a single category."""
    Rank: int = Field(default=0, description="Rank value")
    RankName: str = Field(default="Unknown", description="Human-readable rank name")
    Progress: int = Field(default=0, description="Progress to next rank (0-100)")


class RankProgressStateModel(BaseModel):
    """Commander rank and progress per category."""
    Combat: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Combat rank/progress")
    Trade: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Trade rank/progress")
    Explore: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Exploration rank/progress")
    Empire: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Empire rank/progress")
    Federation: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Federation rank/progress")
    CQC: RankProgressEntry = Field(default_factory=RankProgressEntry, description="CQC rank/progress")
    Soldier: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Soldier rank/progress")
    Exobiologist: RankProgressEntry = Field(default_factory=RankProgressEntry, description="Exobiologist rank/progress")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last rank/progress event")


@final
class RankProgress(Projection[RankProgressStateModel]):
    StateModel = RankProgressStateModel

    _category_keys = [
        "Combat",
        "Trade",
        "Explore",
        "Empire",
        "Federation",
        "CQC",
        "Soldier",
        "Exobiologist",
    ]
    _rank_names: dict[str, list[str]] = {
        "Combat": [
            "Harmless",
            "Mostly Harmless",
            "Novice",
            "Competent",
            "Expert",
            "Master",
            "Dangerous",
            "Deadly",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Trade": [
            "Penniless",
            "Mostly Pennliess",
            "Peddler",
            "Dealer",
            "Merchant",
            "Broker",
            "Entrepreneur",
            "Tycoon",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Explore": [
            "Aimless",
            "Mostly Aimless",
            "Scout",
            "Surveyor",
            "Explorer",
            "Pathfinder",
            "Ranger",
            "Pioneer",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Federation": [
            "None",
            "Recruit",
            "Cadet",
            "Midshipman",
            "Petty Officer",
            "Chief Petty Officer",
            "Warrant Officer",
            "Ensign",
            "Lieutenant",
            "Lt. Commander",
            "Post Commander",
            "Post Captain",
            "Rear Admiral",
            "Vice Admiral",
            "Admiral",
        ],
        "Empire": [
            "None",
            "Outsider",
            "Serf",
            "Master",
            "Squire",
            "Knight",
            "Lord",
            "Baron",
            "Viscount",
            "Count",
            "Earl",
            "Marquis",
            "Duke",
            "Prince",
            "King",
        ],
        "CQC": [
            "Helpless",
            "Mostly Helpless",
            "Amateur",
            "Semi Professional",
            "Professional",
            "Champion",
            "Hero",
            "Legend",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Soldier": [
            "Defenceless",
            "Mostly Defenceless",
            "Rookie",
            "Soldier",
            "Gunslinger",
            "Warrior",
            "Gladiator",
            "Deadeye",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Exobiologist": [
            "Directionless",
            "Mostly Directionless",
            "Compiler",
            "Collector",
            "Cataloguer",
            "Taxonomist",
            "Ecologist",
            "Geneticist",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
    }

    def _rank_name_for(self, category: str, rank_value: int) -> str:
        names = self._rank_names.get(category, [])
        if 0 <= rank_value < len(names):
            return names[rank_value]
        return "Unknown"

    @override
    def process(self, event: Event) -> None:
        if not isinstance(event, GameEvent):
            return

        event_name = event.content.get('event')
        if event_name == 'Rank':
            for key in self._category_keys:
                if key in event.content:
                    rank_value = event.content.get(key, 0)
                    category = getattr(self.state, key)
                    category.Rank = rank_value
                    category.RankName = self._rank_name_for(key, rank_value)
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name == 'Progress':
            for key in self._category_keys:
                if key in event.content:
                    getattr(self.state, key).Progress = event.content.get(key, 0)
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name == 'Promotion':
            for key in self._category_keys:
                if key in event.content:
                    category = getattr(self.state, key)
                    rank_value = event.content.get(key, 0)
                    category.Rank = rank_value
                    category.RankName = self._rank_name_for(key, rank_value)
                    category.Progress = 0
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

# Define types for Squadron Projection
class SquadronStateModel(BaseModel):
    """Current squadron membership state."""
    SquadronID: int = Field(default=0, description="Squadron identifier")
    SquadronName: str = Field(default="Unknown", description="Squadron name")
    CurrentRank: int = Field(default=0, description="Current squadron rank")
    CurrentRankName: str = Field(default="Unknown", description="Current squadron rank name")
    Status: str = Field(default="None", description="Membership status")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last squadron event")


@final
class Squadron(Projection[SquadronStateModel]):
    StateModel = SquadronStateModel

    @override
    def process(self, event: Event) -> None:
        if not isinstance(event, GameEvent):
            return

        event_name = event.content.get('event')

        if event_name == 'SquadronStartup':
            self.state.SquadronID = event.content.get('SquadronID', 0)
            self.state.SquadronName = event.content.get('SquadronName', 'Unknown')
            self.state.CurrentRank = event.content.get('CurrentRank', 0)
            self.state.CurrentRankName = event.content.get('CurrentRankName', 'Unknown')
            self.state.Status = "Member"
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name == 'AppliedToSquadron':
            self.state.SquadronName = event.content.get('SquadronName', self.state.SquadronName)
            self.state.Status = "Applied"
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name == 'InvitedToSquadron':
            self.state.SquadronName = event.content.get('SquadronName', self.state.SquadronName)
            self.state.Status = "Invited"
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name == 'JoinedSquadron':
            self.state.SquadronName = event.content.get('SquadronName', self.state.SquadronName)
            self.state.Status = "Member"
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name == 'SquadronCreated':
            self.state.SquadronName = event.content.get('SquadronName', self.state.SquadronName)
            self.state.Status = "Member"
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name == 'SquadronPromotion':
            self.state.SquadronID = event.content.get('SquadronID', self.state.SquadronID)
            self.state.SquadronName = event.content.get('SquadronName', self.state.SquadronName)
            self.state.CurrentRank = event.content.get('NewRank', self.state.CurrentRank)
            self.state.CurrentRankName = event.content.get('NewRankName', self.state.CurrentRankName)
            self.state.Status = "Member"
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name == 'SquadronDemotion':
            self.state.SquadronID = event.content.get('SquadronID', self.state.SquadronID)
            self.state.SquadronName = event.content.get('SquadronName', self.state.SquadronName)
            self.state.CurrentRank = event.content.get('NewRank', self.state.CurrentRank)
            self.state.CurrentRankName = event.content.get('NewRankName', self.state.CurrentRankName)
            self.state.Status = "Member"
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

        if event_name in ['LeftSquadron', 'KickedFromSquadron', 'DisbandedSquadron']:
            self.state = SquadronStateModel()

# Define types for Reputation Projection
class ReputationStateModel(BaseModel):
    """Faction reputation values."""
    Empire: float = Field(default=0.0, description="Reputation with the Empire")
    Federation: float = Field(default=0.0, description="Reputation with the Federation")
    Alliance: float = Field(default=0.0, description="Reputation with the Alliance")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last reputation event")


@final
class Reputation(Projection[ReputationStateModel]):
    StateModel = ReputationStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'Reputation':
            # Always default missing values to 0.0
            self.state.Empire = event.content.get('Empire', 0.0)
            self.state.Federation = event.content.get('Federation', 0.0)
            self.state.Alliance = event.content.get('Alliance', 0.0)
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

# Define types for Commander Projection
class CommanderStateModel(BaseModel):
    """Commander identity details."""
    FID: str = Field(default="Unknown", description="Frontier ID")
    Name: str = Field(default="Unknown", description="Commander name")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last commander event")


@final
class Commander(Projection[CommanderStateModel]):
    StateModel = CommanderStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'Commander':
            self.state.FID = event.content.get('FID', 'Unknown')
            self.state.Name = event.content.get('Name', 'Unknown')
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

# Define types for Statistics Projection
class StatisticsStateModel(BaseModel):
    """Commander statistics payload."""
    Data: dict[str, Any] = Field(default_factory=dict, description="Statistics data payload")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last statistics event")


@final
class Statistics(Projection[StatisticsStateModel]):
    StateModel = StatisticsStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'Statistics':
            self.state.Data = {
                key: value
                for key, value in event.content.items()
                if key not in ('event', 'timestamp')
            }
            if 'timestamp' in event.content:
                self.state.Timestamp = event.content['timestamp']

# Define types for FleetCarriers Projection
class FleetCarrierEntry(BaseModel):
    """Fleet carrier details and last known location."""
    CarrierType: str = Field(default="Unknown", description="Carrier type (FleetCarrier/SquadronCarrier)")
    CarrierID: int = Field(default=0, description="Carrier identifier")
    Callsign: str = Field(default="Unknown", description="Carrier callsign")
    Name: str = Field(default="Unknown", description="Carrier name")
    DockingAccess: str = Field(default="Unknown", description="Docking access mode")
    AllowNotorious: bool = Field(default=False, description="Whether notorious pilots are allowed")
    FuelLevel: int = Field(default=0, description="Carrier fuel level")
    JumpRangeCurr: float = Field(default=0.0, description="Current jump range")
    JumpRangeMax: float = Field(default=0.0, description="Maximum jump range")
    PendingDecommission: bool = Field(default=False, description="Whether decommission is pending")
    SpaceUsage: dict[str, Any] = Field(default_factory=dict, description="Carrier space usage data")
    Finance: dict[str, Any] = Field(default_factory=dict, description="Carrier finance data")
    Crew: list[dict[str, Any]] = Field(default_factory=list, description="Carrier crew data")
    ShipPacks: list[dict[str, Any]] = Field(default_factory=list, description="Carrier ship packs")
    ModulePacks: list[dict[str, Any]] = Field(default_factory=list, description="Carrier module packs")
    TradeOrders: dict[str, dict[str, Any]] = Field(default_factory=dict, description="Carrier trade orders keyed by commodity")
    StarSystem: str = Field(default="Unknown", description="Last known star system")
    SystemAddress: int = Field(default=0, description="Last known system address")
    BodyID: int = Field(default=0, description="Last known body ID")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last carrier update")


class CarrierJumpRequestItem(BaseModel):
    """Pending carrier jump request."""
    CarrierType: str = Field(default="Unknown", description="Carrier type (FleetCarrier/SquadronCarrier)")
    CarrierID: int = Field(default=0, description="Carrier identifier")
    SystemName: str = Field(default="Unknown", description="Destination system name")
    Body: str = Field(default="Unknown", description="Destination body name")
    SystemAddress: int = Field(default=0, description="Destination system address")
    BodyID: int = Field(default=0, description="Destination body ID")
    DepartureTime: str = Field(default="1970-01-01T00:00:00Z", description="Scheduled departure time (UTC)")
    WarningSent: bool = Field(default=False, description="Whether a jump warning has been sent")


class CarrierCooldownItem(BaseModel):
    """Carrier jump cooldown tracking."""
    CarrierType: str = Field(default="Unknown", description="Carrier type (FleetCarrier/SquadronCarrier)")
    CarrierID: int = Field(default=0, description="Carrier identifier")
    CooldownUntil: str = Field(default="1970-01-01T00:00:00Z", description="Carrier jump cooldown end time (UTC)")
    ReadySent: bool = Field(default=False, description="Whether cooldown ready event has been sent")


class FleetCarriersStateModel(BaseModel):
    """Fleet carriers keyed by carrier ID."""
    Carriers: dict[int, FleetCarrierEntry] = Field(default_factory=dict, description="Carriers keyed by CarrierID")
    PendingJumps: dict[int, CarrierJumpRequestItem] = Field(default_factory=dict, description="Pending carrier jumps keyed by CarrierID")
    Cooldowns: dict[int, CarrierCooldownItem] = Field(default_factory=dict, description="Carrier cooldowns keyed by CarrierID")


@final
class FleetCarriers(Projection[FleetCarriersStateModel]):
    StateModel = FleetCarriersStateModel

    def _process_jump_timers(self, current_time: datetime) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        completed_ids: list[int] = []
        cooldown_completed_ids: list[int] = []

        for carrier_id, pending in self.state.PendingJumps.items():
            try:
                departure_time = datetime.fromisoformat(pending.DepartureTime.replace('Z', '+00:00'))
            except ValueError:
                continue

            warning_time = departure_time - timedelta(minutes=10)
            if current_time >= warning_time and not pending.WarningSent:
                projected_events.append(ProjectedEvent(content={
                    "event": "CarrierJumpWarning",
                    "CarrierType": pending.CarrierType,
                    "CarrierID": carrier_id,
                    "SystemName": pending.SystemName,
                    "Body": pending.Body,
                    "SystemAddress": pending.SystemAddress,
                    "BodyID": pending.BodyID,
                    "DepartureTime": pending.DepartureTime,
                }))
                pending.WarningSent = True

            if current_time >= departure_time:
                entry = self.state.Carriers.get(carrier_id)
                if entry is None:
                    entry = FleetCarrierEntry(CarrierID=carrier_id, CarrierType=pending.CarrierType)
                    self.state.Carriers[carrier_id] = entry

                entry.CarrierType = pending.CarrierType
                entry.StarSystem = pending.SystemName
                entry.SystemAddress = pending.SystemAddress
                entry.BodyID = pending.BodyID
                entry.Timestamp = pending.DepartureTime
                cooldown_until = departure_time + timedelta(minutes=15)
                self.state.Cooldowns[carrier_id] = CarrierCooldownItem(
                    CarrierType=pending.CarrierType,
                    CarrierID=carrier_id,
                    CooldownUntil=cooldown_until.isoformat(),
                    ReadySent=False,
                )

                projected_events.append(ProjectedEvent(content={
                    "event": "CarrierJumpArrived",
                    "CarrierType": pending.CarrierType,
                    "CarrierID": carrier_id,
                    "SystemName": pending.SystemName,
                    "Body": pending.Body,
                    "SystemAddress": pending.SystemAddress,
                    "BodyID": pending.BodyID,
                    "DepartureTime": pending.DepartureTime,
                }))
                completed_ids.append(carrier_id)

        for carrier_id in completed_ids:
            self.state.PendingJumps.pop(carrier_id, None)

        for carrier_id, cooldown in self.state.Cooldowns.items():
            if cooldown.ReadySent:
                continue
            try:
                cooldown_until = datetime.fromisoformat(cooldown.CooldownUntil.replace('Z', '+00:00'))
            except ValueError:
                continue
            if current_time >= cooldown_until:
                projected_events.append(ProjectedEvent(content={
                    "event": "CarrierJumpCooldownComplete",
                    "CarrierType": cooldown.CarrierType,
                    "CarrierID": carrier_id,
                    "CooldownUntil": cooldown.CooldownUntil,
                }))
                cooldown.ReadySent = True
                cooldown_completed_ids.append(carrier_id)

        for carrier_id in cooldown_completed_ids:
            self.state.Cooldowns.pop(carrier_id, None)

        return projected_events

    @override
    def process(self, event: Event) -> list[ProjectedEvent] | None:
        if not isinstance(event, GameEvent):
            return None

        event_name = event.content.get('event')
        if event_name not in [
            'CarrierLocation',
            'CarrierStats',
            'CarrierJumpRequest',
            'CarrierJumpCancelled',
            'CarrierNameChanged',
            'CarrierDecommission',
            'CarrierCancelDecommission',
            'CarrierBankTransfer',
            'CarrierDepositFuel',
            'CarrierCrewServices',
            'CarrierFinance',
            'CarrierTradeOrder',
        ]:
            return None

        carrier_id = event.content.get('CarrierID', 0)
        if not carrier_id:
            return None

        carrier_type = event.content.get('CarrierType', 'Unknown')
        entry = self.state.Carriers.get(carrier_id)
        if entry is None:
            entry = FleetCarrierEntry(CarrierID=carrier_id, CarrierType=carrier_type)
            self.state.Carriers[carrier_id] = entry

        entry.CarrierType = carrier_type
        entry.CarrierID = carrier_id
        if 'timestamp' in event.content:
            entry.Timestamp = event.content['timestamp']

        if event_name == 'CarrierLocation':
            entry.StarSystem = event.content.get('StarSystem', entry.StarSystem)
            entry.SystemAddress = event.content.get('SystemAddress', entry.SystemAddress)
            entry.BodyID = event.content.get('BodyID', entry.BodyID)

        if event_name == 'CarrierStats':
            entry.Callsign = event.content.get('Callsign', entry.Callsign)
            entry.Name = event.content.get('Name', entry.Name)
            entry.DockingAccess = event.content.get('DockingAccess', entry.DockingAccess)
            entry.AllowNotorious = event.content.get('AllowNotorious', entry.AllowNotorious)
            entry.FuelLevel = event.content.get('FuelLevel', entry.FuelLevel)
            entry.JumpRangeCurr = event.content.get('JumpRangeCurr', entry.JumpRangeCurr)
            entry.JumpRangeMax = event.content.get('JumpRangeMax', entry.JumpRangeMax)
            entry.PendingDecommission = event.content.get('PendingDecommission', entry.PendingDecommission)
            entry.SpaceUsage = event.content.get('SpaceUsage', entry.SpaceUsage)
            entry.Finance = event.content.get('Finance', entry.Finance)
            entry.Crew = event.content.get('Crew', entry.Crew)
            entry.ShipPacks = event.content.get('ShipPacks', entry.ShipPacks)
            entry.ModulePacks = event.content.get('ModulePacks', entry.ModulePacks)

        if event_name == 'CarrierNameChanged':
            entry.Callsign = event.content.get('Callsign', entry.Callsign)
            entry.Name = event.content.get('Name', entry.Name)

        if event_name == 'CarrierDecommission':
            entry.PendingDecommission = True

        if event_name == 'CarrierCancelDecommission':
            entry.PendingDecommission = False

        if event_name == 'CarrierBankTransfer':
            entry.Finance = {
                **entry.Finance,
                "CarrierBalance": event.content.get('CarrierBalance', entry.Finance.get("CarrierBalance", 0)),
                "PlayerBalance": event.content.get('PlayerBalance', entry.Finance.get("PlayerBalance", 0)),
                "Deposit": event.content.get('Deposit', entry.Finance.get("Deposit", 0)),
                "Withdraw": event.content.get('Withdraw', entry.Finance.get("Withdraw", 0)),
            }

        if event_name == 'CarrierDepositFuel':
            entry.FuelLevel = event.content.get('Total', entry.FuelLevel)

        if event_name == 'CarrierCrewServices':
            crew_role = event.content.get('CrewRole')
            if crew_role:
                crew = next((c for c in entry.Crew if c.get('CrewRole') == crew_role), None)
                if crew is None:
                    crew = {"CrewRole": crew_role}
                    entry.Crew.append(crew)
                crew["Operation"] = event.content.get('Operation', '')
                if 'CrewName' in event.content:
                    crew["CrewName"] = event.content.get('CrewName', '')

        if event_name == 'CarrierFinance':
            entry.Finance = {
                **entry.Finance,
                "CarrierBalance": event.content.get('CarrierBalance', entry.Finance.get("CarrierBalance", 0)),
                "ReserveBalance": event.content.get('ReserveBalance', entry.Finance.get("ReserveBalance", 0)),
                "AvailableBalance": event.content.get('AvailableBalance', entry.Finance.get("AvailableBalance", 0)),
                "ReservePercent": event.content.get('ReservePercent', entry.Finance.get("ReservePercent", 0)),
                "TaxRate_repair": event.content.get('TaxRate_repair', entry.Finance.get("TaxRate_repair", 0)),
                "TaxRate_refuel": event.content.get('TaxRate_refuel', entry.Finance.get("TaxRate_refuel", 0)),
                "TaxRate_rearm": event.content.get('TaxRate_rearm', entry.Finance.get("TaxRate_rearm", 0)),
            }

        if event_name == 'CarrierTradeOrder':
            commodity = event.content.get('Commodity', 'Unknown')
            black_market = event.content.get('BlackMarket', False)
            order_key = f"{commodity}:{'black' if black_market else 'legal'}"
            if event.content.get('CancelTrade'):
                entry.TradeOrders.pop(order_key, None)
            else:
                order_type = None
                order_amount = None
                if 'PurchaseOrder' in event.content:
                    order_type = 'Purchase'
                    order_amount = event.content.get('PurchaseOrder')
                elif 'SaleOrder' in event.content:
                    order_type = 'Sale'
                    order_amount = event.content.get('SaleOrder')
                entry.TradeOrders[order_key] = {
                    "Commodity": commodity,
                    "BlackMarket": black_market,
                    "OrderType": order_type,
                    "OrderAmount": order_amount,
                    "Price": event.content.get('Price'),
                    "Timestamp": event.content.get('timestamp', entry.Timestamp),
                }

        if event_name == 'CarrierJumpRequest':
            pending = CarrierJumpRequestItem(
                CarrierType=carrier_type,
                CarrierID=carrier_id,
                SystemName=event.content.get('SystemName', 'Unknown'),
                Body=event.content.get('Body', 'Unknown'),
                SystemAddress=event.content.get('SystemAddress', 0),
                BodyID=event.content.get('BodyID', 0),
                DepartureTime=event.content.get('DepartureTime', '1970-01-01T00:00:00Z'),
            )
            self.state.PendingJumps[carrier_id] = pending

            now_utc = datetime.now(timezone.utc)
            projected_events = self._process_jump_timers(now_utc)
            return projected_events if projected_events else None

        if event_name == 'CarrierJumpCancelled':
            self.state.PendingJumps.pop(carrier_id, None)

        return None

    def process_timer(self) -> list[ProjectedEvent]:
        current_time = datetime.now(timezone.utc)
        return self._process_jump_timers(current_time)

# Define types for InCombat Projection
class InCombatStateModel(BaseModel):
    """Combat status of the commander."""
    InCombat: bool = Field(default=False, description="Whether commander is currently in combat")


@final
class InCombat(Projection[InCombatStateModel]):
    StateModel = InCombatStateModel

    @override
    def process(self, event: Event) -> list[ProjectedEvent] | None:
        projected_events: list[ProjectedEvent] = []

        # Process Music events
        if isinstance(event, GameEvent) and event.content.get('event') == 'Music':
            music_track = event.content.get('MusicTrack', '')

            # Skip if missing music track information
            if not music_track:
                return None

            # Determine if this is a combat music track (starts with "combat")
            is_combat_music = music_track.lower().startswith('combat')

            # Check for transition from combat to non-combat
            if self.state.InCombat and not is_combat_music:
                # Generate a projected event for leaving combat
                projected_events.append(ProjectedEvent(content={"event": "CombatExited"}))
                self.state.InCombat = False
            # Check for transition from non-combat to combat
            elif not self.state.InCombat and is_combat_music:
                # Generate a projected event for entering combat
                projected_events.append(ProjectedEvent(content={"event": "CombatEntered"}))
                self.state.InCombat = True

        return projected_events


class WingStateModel(BaseModel):
    """Current wing membership status."""
    Members: list[str] = Field(default_factory=list, description="Names of wing members")


@final
class Wing(Projection[WingStateModel]):
    StateModel = WingStateModel

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'WingJoin':
            # Initialize with existing members if any
            others = event.content.get('Others', [])
            if others:
                self.state.Members = [member.get('Name', 'Unknown') for member in others]  # type: ignore
            else:
                self.state.Members = []
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'WingAdd':
            name = event.content.get('Name', 'Unknown')
            if name and name not in self.state.Members:
                self.state.Members.append(name)
        
        if isinstance(event, GameEvent) and event.content.get('event') in ['WingLeave', 'LoadGame']:
            self.state.Members = []

class FSSSignalsStateModel(BaseModel):
    """Current FSS signal discoveries in the system."""
    SystemAddress: int = Field(default=0, description="Unique system identifier")
    FleetCarrier: list[str] = Field(default_factory=list, description="Fleet carrier signals")
    ResourceExtraction: list[str] = Field(default_factory=list, description="Resource extraction site signals")
    Installation: list[str] = Field(default_factory=list, description="Installation signals")
    NavBeacon: list[str] = Field(default_factory=list, description="Navigation beacon signals")
    TouristBeacon: list[str] = Field(default_factory=list, description="Tourist beacon signals")
    Megaship: list[str] = Field(default_factory=list, description="Megaship signals")
    Generic: list[str] = Field(default_factory=list, description="Generic signals")
    Outpost: list[str] = Field(default_factory=list, description="Outpost signals")
    Combat: list[str] = Field(default_factory=list, description="Combat zone signals")
    Station: list[str] = Field(default_factory=list, description="Station signals")
    UnknownSignal: list[str] = Field(default_factory=list, description="Unknown signal types")


@final
class FSSSignals(Projection[FSSSignalsStateModel]):
    StateModel = FSSSignalsStateModel

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        if isinstance(event, GameEvent) and event.content.get('event') == 'Location':
            location = cast(LocationEvent, event.content)
            self.state = FSSSignalsStateModel(SystemAddress=location.get("SystemAddress", 0))
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSSSignalDiscovered':
            signal = cast(FSSSignalDiscoveredEvent, event.content)
            signal_type = signal.get("SignalType", "Unknown")
            signal_name = signal.get("SignalName", "Unknown")
            system_address = signal.get("SystemAddress", 0)
            if system_address != self.state.SystemAddress:
                # New system, clear previous signals
                self.state = FSSSignalsStateModel(SystemAddress=system_address)

            if hasattr(self.state, signal_type):
                getattr(self.state, signal_type).append(signal_name)
            else:
                if signal.get("IsStation"):
                    self.state.Station.append(signal_name)
                    signal_type = "Station"
                else:
                    self.state.UnknownSignal.append(signal_name)
                    signal_type = "UnknownSignal"

            projected_events.append(ProjectedEvent(content={"event": f"{signal_type}Discovered", "SignalName": signal_name}))

        if isinstance(event, GameEvent) and event.content.get('event') in ['FSDJump', 'SupercruiseExit', 'FSSDiscoveryScan']:
            # These indicate that no more signals are discovered immediately, so we could batch on those
            pass

        return projected_events

class IdleStateModel(BaseModel):
    """Commander's activity/idle status."""
    LastInteraction: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last user interaction")
    IsIdle: bool = Field(default=True, description="Whether the user is currently idle")

@final
class Idle(Projection[IdleStateModel]):
    StateModel = IdleStateModel

    def __init__(self, idle_timeout: int):
        super().__init__()
        self.idle_timeout = idle_timeout

    def _check_idle_timeout(self, current_dt: datetime) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        last_interaction = self.state.LastInteraction
        last_dt = datetime.fromisoformat(last_interaction.replace('Z', '+00:00'))
        time_delta = (current_dt - last_dt).total_seconds()

        if time_delta > self.idle_timeout and self.state.IsIdle is False:
            self.state.IsIdle = True
            projected_events.append(ProjectedEvent(content={"event": "Idle"}))

        return projected_events

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, ConversationEvent):
            self.state.LastInteraction = event.timestamp
            self.state.IsIdle = False

        if isinstance(event, (StatusEvent, GameEvent)) and self.state.IsIdle is False:
            current_dt = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            projected_events.extend(self._check_idle_timeout(current_dt))

        return projected_events

    @override
    def process_timer(self) -> list[ProjectedEvent]:
        if self.state.IsIdle:
            return []

        current_dt = datetime.now(timezone.utc)
        return self._check_idle_timeout(current_dt)

def registerProjections(
    event_manager: EventManager,
    system_db: SystemDatabase,
    idle_timeout: int,
):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())
    event_manager.register_projection(Location())
    event_manager.register_projection(Missions())
    event_manager.register_projection(EngineerProgress())
    event_manager.register_projection(RankProgress())
    event_manager.register_projection(CommunityGoal())
    event_manager.register_projection(Squadron())
    event_manager.register_projection(Reputation())
    event_manager.register_projection(Commander())
    event_manager.register_projection(Statistics())
    event_manager.register_projection(FleetCarriers())
    event_manager.register_projection(ShipInfo())
    event_manager.register_projection(Target())
    event_manager.register_projection(NavInfo(system_db))
    event_manager.register_projection(ExobiologyScan())
    event_manager.register_projection(Cargo())
    event_manager.register_projection(Backpack())
    event_manager.register_projection(SuitLoadout())
    event_manager.register_projection(Materials())
    event_manager.register_projection(Friends())
    event_manager.register_projection(Powerplay())
    event_manager.register_projection(ColonisationConstruction())
    event_manager.register_projection(DockingEvents())
    event_manager.register_projection(InCombat())
    event_manager.register_projection(Wing())
    event_manager.register_projection(FSSSignals())
    event_manager.register_projection(Idle(idle_timeout))
    event_manager.register_projection(StoredModules())
    event_manager.register_projection(StoredShips())

    # ToDo: SLF, SRV,
    for proj in [
        'ModuleInfo',
        'ShipLocker',
        'Loadout',
        'Shipyard',
        'Market',
        'Outfitting',
    ]:
        p = latest_event_projection_factory(proj, proj)
        event_manager.register_projection(p())


# Type alias for the dictionary of projected states
# Keys are projection class names, values are the corresponding state models
ProjectedStates = dict[str, BaseModel]

# Type aliases for backward compatibility with existing imports
MissionsState = MissionsStateModel
ShipInfoState = ShipInfoStateModel
TargetState = TargetStateModel
