from typing import Literal, Optional, cast

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, StatusEvent
from ..EventManager import Projection
from ..StatusParser import Status


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
    "NoFocus",
    "InternalPanel",
    "ExternalPanel",
    "CommsPanel",
    "RolePanel",
    "StationServices",
    "GalaxyMap",
    "SystemMap",
    "Orrery",
    "FSS",
    "SAA",
    "Codex",
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
            status = cast(Status, event.status)

            # Parse base flags
            flags_dict = status.get("flags", {})
            if isinstance(flags_dict, dict):
                self.state.flags = StatusBaseFlags(**flags_dict)

            # Parse Odyssey flags if present
            flags2_dict = status.get("flags2")
            if flags2_dict and isinstance(flags2_dict, dict):
                self.state.flags2 = StatusOdysseyFlags(**flags2_dict)
            else:
                self.state.flags2 = None

            # Parse Pips if present
            pips = status.get("Pips")
            if pips and isinstance(pips, dict):
                self.state.Pips = StatusPips(**pips)
            else:
                self.state.Pips = None

            # Parse Fuel if present
            fuel = status.get("Fuel")
            if fuel and isinstance(fuel, dict):
                self.state.Fuel = StatusFuel(**fuel)
            else:
                self.state.Fuel = None

            # Parse Destination if present
            dest = status.get("Destination")
            if dest and isinstance(dest, dict):
                self.state.Destination = StatusDestination(**dest)
            else:
                self.state.Destination = None

            # Set simple fields
            self.state.FireGroup = cast(Optional[int], status.get("FireGroup"))
            self.state.GuiFocus = cast(Optional[GUI_FOCUS_LITERAL], status.get("GuiFocus"))
            self.state.Cargo = cast(Optional[float], status.get("Cargo"))
            self.state.LegalState = cast(Optional[LEGAL_STATE_LITERAL], status.get("LegalState"))
            self.state.Latitude = cast(Optional[float], status.get("Latitude"))
            self.state.Altitude = cast(Optional[float], status.get("Altitude"))
            self.state.Longitude = cast(Optional[float], status.get("Longitude"))
            self.state.Heading = cast(Optional[float], status.get("Heading"))
            self.state.BodyName = cast(Optional[str], status.get("BodyName"))
            self.state.PlanetRadius = cast(Optional[float], status.get("PlanetRadius"))
            self.state.Balance = cast(Optional[float], status.get("Balance"))
            self.state.Oxygen = cast(Optional[float], status.get("Oxygen"))
            self.state.Health = cast(Optional[float], status.get("Health"))
            self.state.Temperature = cast(Optional[float], status.get("Temperature"))
            self.state.SelectedWeapon = cast(Optional[str], status.get("SelectedWeapon"))
            self.state.Gravity = cast(Optional[float], status.get("Gravity"))
