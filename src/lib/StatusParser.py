import json
import os
import queue
import threading
import time
import traceback
from time import sleep
from typing import Any, Literal, Optional
from typing import TypedDict

from .Logger import log


class BaseFlags(TypedDict):
    Docked: bool
    Landed: bool
    LandingGearDown: bool
    ShieldsUp: bool
    Supercruise: bool
    FlightAssistOff: bool
    HardpointsDeployed: bool
    InWing: bool
    LightsOn: bool
    CargoScoopDeployed: bool
    SilentRunning: bool
    ScoopingFuel: bool
    SrvHandbrake: bool
    SrvUsingTurretView: bool
    SrvTurretRetracted: bool
    SrvDriveAssist: bool
    FsdMassLocked: bool
    FsdCharging: bool
    FsdCooldown: bool
    LowFuel: bool
    OverHeating: bool
    HasLatLong: bool
    InDanger: bool
    BeingInterdicted: bool
    InMainShip: bool
    InFighter: bool
    InSRV: bool
    HudInAnalysisMode: bool
    NightVision: bool
    AltitudeFromAverageRadius: bool
    FsdJump: bool
    SrvHighBeam: bool

def parse_status_flags(value: int) -> BaseFlags:
    return BaseFlags(
        Docked=bool(value & 1),
        Landed=bool(value & 2),
        LandingGearDown=bool(value & 4),
        ShieldsUp=bool(value & 8),
        Supercruise=bool(value & 16),
        FlightAssistOff=bool(value & 32),
        HardpointsDeployed=bool(value & 64),
        InWing=bool(value & 128),
        LightsOn=bool(value & 256),
        CargoScoopDeployed=bool(value & 512),
        SilentRunning=bool(value & 1024),
        ScoopingFuel=bool(value & 2048),
        SrvHandbrake=bool(value & 4096),
        SrvUsingTurretView=bool(value & 8192),
        SrvTurretRetracted=bool(value & 16384),
        SrvDriveAssist=bool(value & 32768),
        FsdMassLocked=bool(value & 65536),
        FsdCharging=bool(value & 131072),
        FsdCooldown=bool(value & 262144),
        LowFuel=bool(value & 524288),
        OverHeating=bool(value & 1048576),
        HasLatLong=bool(value & 2097152),
        InDanger=bool(value & 4194304),
        BeingInterdicted=bool(value & 8388608),
        InMainShip=bool(value & 16777216),
        InFighter=bool(value & 33554432),
        InSRV=bool(value & 67108864),
        HudInAnalysisMode=bool(value & 134217728),
        NightVision=bool(value & 268435456),
        AltitudeFromAverageRadius=bool(value & 536870912),
        FsdJump=bool(value & 1073741824),
        SrvHighBeam=bool(value & 2147483648),
    )


class OdysseyFlags(TypedDict):
    OnFoot: bool
    InTaxi: bool
    InMultiCrew: bool
    OnFootInStation: bool
    OnFootOnPlanet: bool
    AimDownSight: bool
    LowOxygen: bool
    LowHealth: bool
    Cold: bool
    Hot: bool
    VeryCold: bool
    VeryHot: bool
    GlideMode: bool
    OnFootInHangar: bool
    OnFootSocialSpace: bool
    OnFootExterior: bool
    BreathableAtmosphere: bool
    TelepresenceMulticrew: bool
    PhysicalMulticrew: bool
    FsdHyperdriveCharging: bool

def parse_odyssey_flags(value: int) -> OdysseyFlags:
    return OdysseyFlags(
        OnFoot=bool(value & 1),
        InTaxi=bool(value & 2),
        InMultiCrew=bool(value & 4),
        OnFootInStation=bool(value & 8),
        OnFootOnPlanet=bool(value & 16),
        AimDownSight=bool(value & 32),
        LowOxygen=bool(value & 64),
        LowHealth=bool(value & 128),
        Cold=bool(value & 256),
        Hot=bool(value & 512),
        VeryCold=bool(value & 1024),
        VeryHot=bool(value & 2048),
        GlideMode=bool(value & 4096),
        OnFootInHangar=bool(value & 8192),
        OnFootSocialSpace=bool(value & 16384),
        OnFootExterior=bool(value & 32768),
        BreathableAtmosphere=bool(value & 65536),
        TelepresenceMulticrew=bool(value & 131072),
        PhysicalMulticrew=bool(value & 262144),
        FsdHyperdriveCharging=bool(value & 524288),
    )


class Pips(TypedDict):
    system: float
    engine: float
    weapons: float
    
def parse_pips_flags(value: list[int]) -> Pips:
    return Pips(
        system=value[0] / 2,
        engine=value[1] / 2,
        weapons=value[2] / 2
    )


class Fuel(TypedDict):
    FuelMain: float
    FuelReservoir: float


class Destination(TypedDict):
    System: int
    Body: int
    Name: str
    Name_Localised: Optional[str]


class Status(TypedDict):
    event: Literal["Status"]
    flags: BaseFlags
    flags2: Optional[OdysseyFlags]
    Pips: Optional[Pips]
    FireGroup: Optional[int]
    GuiFocus: Optional[Literal[
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
    ]]
    Fuel: Optional[Fuel]
    Cargo: Optional[float]
    LegalState: Optional[Literal[
        "Clean",
        "IllegalCargo",
        "Speeding",
        "Wanted",
        "Hostile",
        "PassengerWanted",
        "Warrant",
        "Thargoid",
        "Allied",
    ]]
    Latitude: Optional[float]
    Altitude: Optional[float]
    Longitude: Optional[float]
    Heading: Optional[float]
    BodyName: Optional[str]
    PlanetRadius: Optional[float]
    Balance: Optional[float]
    Destination: Optional[Destination]

    Oxygen: Optional[float]
    Health: Optional[float]
    Temperature: Optional[float]
    SelectedWeapon: Optional[str]
    Gravity: Optional[float]

def parse_status_json(value: dict[str, Any]) -> Status:
    """Converts the status file data to a Status object. All fields are optional."""
    GuiPanels = [
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
    return Status(
        event='Status',
        flags=parse_status_flags(value.get('Flags', 0)),
        flags2=parse_odyssey_flags(value.get('Flags2', 0)) if 'Flags2' in value else None,
        Pips=parse_pips_flags(value.get('Pips', [0,0,0])) if 'Pips' in value else None,
        FireGroup=value.get('FireGroup') if 'FireGroup' in value else None,
        GuiFocus=GuiPanels[value.get('GuiFocus', 0)] if 'GuiFocus' in value else None,
        Fuel=Fuel(**value.get('Fuel', {})) if 'Fuel' in value else None,
        Cargo=value.get('Cargo', None),
        LegalState=value.get('LegalState', None),
        Latitude=value.get('Latitude', None),
        Altitude=value.get('Altitude', None),
        Longitude=value.get('Longitude', None),
        Heading=value.get('Heading', None),
        BodyName=value.get('BodyName', None),
        PlanetRadius=value.get('PlanetRadius', None),
        Balance=value.get('Balance', None),
        Destination=Destination(**value.get('Destination', {})) if 'Destination' in value else None,

        Oxygen=value.get('Oxygen', None),
        Health=value.get('Health', None),
        Temperature=value.get('Temperature', None),
        SelectedWeapon=value.get('SelectedWeapon', None),
        Gravity=value.get('Gravity', None),
    )


class StatusParser:
    def __init__(self, journals_path: str):
        self.file_path = os.path.join(journals_path, "Status.json")

        current_status_raw = self._read_status_file()
        self.current_status = parse_status_json(current_status_raw)
        self.watch_thread = threading.Thread(target=self._watch_file_thread, daemon=True)
        self.watch_thread.start()
        self.status_queue = queue.Queue()
        
    def _watch_file_thread(self):
        backoff = 1
        while True:
            try: 
                self._watch_file()
            except Exception as e:
                log('error', 'An error occurred when reading status file', e, traceback.format_exc())
                sleep(backoff)
                log('info', 'Attempting to restart status file reader after failure')
                backoff *= 2

    def _watch_file(self):
        """Detects changes in the Status.json file."""
        while True:
            status_raw = self._read_status_file()
            status = parse_status_json(status_raw)
        
            if status != self.current_status:
                log('debug', 'Status changed', status)
                self.status_queue.put({"event": "Status", **status})
                events = self._create_delta_events(self.current_status, status)
                for event in events:
                    self.status_queue.put(event)
                self.current_status = status
            sleep(1)

    def _read_status_file(self) -> dict:
        """Loads data from the JSON file and returns a cleaned version"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except json.JSONDecodeError:
            sleep(0.1)
            with open(self.file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)

        return data

    def _create_delta_events(self, old_status: Status, new_status: Status):
        """Creates events specific field that has changed."""
        events = []

        gui_event = ""
        if old_status["GuiFocus"] != new_status["GuiFocus"]:
            if old_status["GuiFocus"] in ["GalaxyMap", "SystemMap"]:
                gui_event = old_status["GuiFocus"]+"Closed"
            if new_status["GuiFocus"] in ["GalaxyMap", "SystemMap"]:
                gui_event += new_status["GuiFocus"]+"Opened"
            if gui_event != "":
                events.append({"event": gui_event})

        # Only in mainship
        if new_status["flags"]["InMainShip"]:
            if old_status["flags"]["LandingGearDown"] and not new_status["flags"]["LandingGearDown"]:
                events.append({"event": "LandingGearUp"})
            if not old_status["flags"]["LandingGearDown"] and new_status["flags"]["LandingGearDown"]:
                events.append({"event": "LandingGearDown"})

            if old_status["flags"]["FlightAssistOff"] and not new_status["flags"]["FlightAssistOff"]:
                events.append({"event": "FlightAssistOn"})
            if not old_status["flags"]["FlightAssistOff"] and new_status["flags"]["FlightAssistOff"]:
                events.append({"event": "FlightAssistOff"})

            if old_status["flags"]["HardpointsDeployed"] and not new_status["flags"]["HardpointsDeployed"]:
                events.append({"event": "HardpointsRetracted"})
            if not old_status["flags"]["HardpointsDeployed"] and new_status["flags"]["HardpointsDeployed"]:
                events.append({"event": "HardpointsDeployed"})

            if old_status["flags"]["SilentRunning"] and not new_status["flags"]["SilentRunning"]:
                events.append({"event": "SilentRunningOff"})
            if not old_status["flags"]["SilentRunning"] and new_status["flags"]["SilentRunning"]:
                events.append({"event": "SilentRunningOn"})

            if old_status["flags"]["ScoopingFuel"] and not new_status["flags"]["ScoopingFuel"]:
                events.append({"event": "FuelScoopEnded"})
            if not old_status["flags"]["ScoopingFuel"] and new_status["flags"]["ScoopingFuel"]:
                events.append({"event": "FuelScoopStarted"})

            if old_status["flags"]["LightsOn"] and not new_status["flags"]["LightsOn"]:
                events.append({"event": "LightsOff"})
            if not old_status["flags"]["LightsOn"] and new_status["flags"]["LightsOn"]:
                events.append({"event": "LightsOn"})

            if old_status["flags"]["CargoScoopDeployed"] and not new_status["flags"]["CargoScoopDeployed"]:
                events.append({"event": "CargoScoopRetracted"})
            if not old_status["flags"]["CargoScoopDeployed"] and new_status["flags"]["CargoScoopDeployed"]:
                events.append({"event": "CargoScoopDeployed"})

            if old_status["flags"]["FsdMassLocked"] and not new_status["flags"]["FsdMassLocked"]:
                events.append({"event": "FsdMassLockEscaped"})
            if not old_status["flags"]["FsdMassLocked"] and new_status["flags"]["FsdMassLocked"]:
                events.append({"event": "FsdMassLocked"})

            if old_status["flags2"] and new_status["flags2"]:
                if old_status.get("flags2", {}).get("GlideMode") and not new_status.get("flags2", {}).get("GlideMode"):
                    events.append({"event": "GlideModeExited"})
                if not old_status.get("flags2", {}).get("GlideMode") and new_status.get("flags2", {}).get("GlideMode"):
                    events.append({"event": "GlideModeEntered"})

            if old_status["flags"]["LowFuel"] and not new_status["flags"]["LowFuel"]:
                events.append({"event": "LowFuelWarningCleared"})
            if not old_status["flags"]["LowFuel"] and new_status["flags"]["LowFuel"]:
                events.append({"event": "LowFuelWarning"})

            if not old_status["flags"]["FsdCharging"] and new_status["flags"]["FsdCharging"]:
                events.append({"event": "FsdCharging"})

            if not old_status["flags"]["BeingInterdicted"] and new_status["flags"]["BeingInterdicted"]:
                events.append({"event": "BeingInterdicted"})

        # Only SRV
        if new_status["flags"]["InSRV"]:
            if old_status["flags"]["SrvHandbrake"] and not new_status["flags"]["SrvHandbrake"]:
                events.append({"event": "SrvHandbrakeOff"})
            if not old_status["flags"]["SrvHandbrake"] and new_status["flags"]["SrvHandbrake"]:
                events.append({"event": "SrvHandbrakeOn"})

            if old_status["flags"]["SrvUsingTurretView"] and not new_status["flags"]["SrvUsingTurretView"]:
                events.append({"event": "SrvTurretViewDisconnected"})
            if not old_status["flags"]["SrvUsingTurretView"] and new_status["flags"]["SrvUsingTurretView"]:
                events.append({"event": "SrvTurretViewConnected"})

            if old_status["flags"]["SrvDriveAssist"] and not new_status["flags"]["SrvDriveAssist"]:
                events.append({"event": "SrvDriveAssistOff"})
            if not old_status["flags"]["SrvDriveAssist"] and new_status["flags"]["SrvDriveAssist"]:
                events.append({"event": "SrvDriveAssistOn"})

        # Only Suit
        if old_status["flags2"] and new_status["flags2"] and new_status["flags2"]["OnFoot"]:
            if old_status["flags2"]["LowOxygen"] and not new_status["flags2"]["LowOxygen"]:
                events.append({"event": "LowOxygenWarningCleared"})
            if not old_status["flags2"]["LowOxygen"] and new_status["flags2"]["LowOxygen"]:
                events.append({"event": "LowOxygenWarning"})

            if old_status["flags2"]["LowHealth"] and not new_status["flags2"]["LowHealth"]:
                events.append({"event": "LowHealthWarningCleared"})
            if not old_status["flags2"]["LowHealth"] and new_status["flags2"]["LowHealth"]:
                events.append({"event": "LowHealthWarning"})

            if old_status["flags2"]["BreathableAtmosphere"] and not new_status["flags2"]["BreathableAtmosphere"]:
                events.append({"event": "BreathableAtmosphereExited"})
            if not old_status["flags2"]["BreathableAtmosphere"] and new_status["flags2"]["BreathableAtmosphere"]:
                events.append({"event": "BreathableAtmosphereEntered"})

            if old_status["SelectedWeapon"] and old_status["SelectedWeapon"] != new_status["SelectedWeapon"]:
                events.append({"event": "WeaponSelected", "SelectedWeapon": new_status["SelectedWeapon"]})

        # Always
        if old_status["flags"]["InDanger"] and not new_status["flags"]["InDanger"]:
            events.append({"event": "OutofDanger"})
        if not old_status["flags"]["InDanger"] and new_status["flags"]["InDanger"]:
            events.append({"event": "InDanger"})

        if old_status["flags"]["NightVision"] and not new_status["flags"]["NightVision"]:
            events.append({"event": "NightVisionOff"})
        if not old_status["flags"]["NightVision"] and new_status["flags"]["NightVision"]:
            events.append({"event": "NightVisionOn"})

        if old_status["flags"]["HudInAnalysisMode"] and not new_status["flags"]["HudInAnalysisMode"]:
            events.append({"event": "HudSwitchedToCombatMode"})
        if not old_status["flags"]["HudInAnalysisMode"] and new_status["flags"]["HudInAnalysisMode"]:
            events.append({"event": "HudSwitchedToAnalysisMode"})

        if (
            old_status["LegalState"] and new_status["LegalState"]
            and old_status["LegalState"] != new_status["LegalState"]
            and (
                old_status["LegalState"] not in ["Clean", "Speeding", "Allied"]
                or new_status["LegalState"] not in ["Clean", "Speeding", "Allied"]
            )
        ):
            events.append({"event": "LegalStateChanged", "LegalState": new_status["LegalState"]})
        


        return events



# Usage Example
if __name__ == "__main__":
    while True:
        parser = StatusParser()
        cleaned_data_raw = parser._read_status_file()
        cleaned_data = parse_status_json(cleaned_data_raw)
        print(json.dumps(cleaned_data, indent=4))
        time.sleep(1)
        print("\n"*10)