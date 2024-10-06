from dataclasses import dataclass
import json
import time
from datetime import datetime, timedelta
import queue
from sys import platform
import threading
from time import sleep
from typing import Literal, Optional, Union
from .Logger import log

@dataclass
class BaseFlags:
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

    def from_status_flag(value: int):
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

@dataclass
class OdysseyFlags():
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

    def from_status_flag(value: int):
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
    
@dataclass
class Pips:
    system: float
    engine: float
    weapons: float
    def from_status_flag(value: list[int]):
        return Pips(
            system=value[0] / 2,
            engine=value[1] / 2,
            weapons=value[2] / 2
        )

@dataclass
class Fuel:
    main: float
    reservoir: float

@dataclass
class Destination:
    System: str
    Body: str
    Name: str
    
@dataclass
class Status:
    flags: BaseFlags
    flags2: Optional[OdysseyFlags]
    Pips: Optional[Pips]
    Firegroup: Optional[int]
    GuiFocus: Optional[Literal[
        'NoFocus'
        'InternalPanel'
        'ExternalPanel'
        'CommsPanel'
        'RolePanel'
        'StationServices'
        'GalaxyMap'
        'SystemMap'
        'Orrery'
        'FSS'
        'SAA'
        'Codex'
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

    def from_status_file(value: dict[str, any]):
        """Converts the status file data to a Status object. All fields are optional."""
        return Status(
            flags=BaseFlags.from_status_flag(value.get('Flags', 0)),
            flags2=OdysseyFlags.from_status_flag(value.get('Flags2', 0)) if 'Flags2' in value else None,
            Pips=Pips.from_status_flag(value.get('Pips', [0,0,0])) if 'Pips' in value else None,
            Firegroup=value.get('Firegroup'),
            GuiFocus=[
                'NoFocus'
                'InternalPanel'
                'ExternalPanel'
                'CommsPanel'
                'RolePanel'
                'StationServices'
                'GalaxyMap'
                'SystemMap'
                'Orrery'
                'FSS'
                'SAA'
                'Codex'
            ][value.get('GuiFocus', 0)] if 'GuiFocus' in value else None,
            Fuel=Fuel(**value.get('Fuel', {})) if 'Fuel' in value else None,
            Cargo=value.get('Cargo'),
            LegalState=value.get('LegalState'),
            Latitude=value.get('Latitude'),
            Altitude=value.get('Altitude'),
            Longitude=value.get('Longitude'),
            Heading=value.get('Heading'),
            BodyName=value.get('BodyName'),
            PlanetRadius=value.get('PlanetRadius'),
            Balance=value.get('Balance'),
            Destination=Destination(**value.get('Destination', {})) if 'Destination' in value else None,

            Oxygen=value.get('Oxygen'),
            Health=value.get('Health'),
            Temperature=value.get('Temperature'),
            SelectedWeapon=value.get('SelectedWeapon'),
            Gravity=value.get('Gravity'),
        )


class StatusParser:
    def __init__(self, file_path=None):
        if platform != "win32":
            self.file_path = file_path if file_path else "./linux_ed/Status.json"
        else:
            from .WindowsKnownPaths import get_path, FOLDERID, UserHandle
            self.file_path = file_path if file_path else (get_path(FOLDERID.SavedGames, UserHandle.current) + "\Frontier Developments\Elite Dangerous\Status.json")

        self.current_status = self._read_status_file()
        self.watch_thread = threading.Thread(target=self._watch_file_thread, daemon=True)
        self.watch_thread.start()
        self.status_queue = queue.Queue()
        
    def _watch_file_thread(self):
        backoff = 1
        while True:
            try: 
                self._watch_file()
            except Exception as e:
                log('error', 'An error occurred when reading status file', e)
                sleep(backoff)
                log('info', 'Attempting to restart status file reader after failure')
                backoff *= 2

    def _watch_file(self):
        """Detects changes in the Status.json file."""
        while True:
            try:
                status = self._read_status_file()
            except Exception as e:
                # Sometimes the file is not fully written yet, so we retry
                log('error', 'An error occurred when reading status file', e)
                sleep(0.1)
                continue
        
            if status != self.current_status:
                log('debug', 'Status changed', status)
                #self.status_queue.put(status)
                events = self._create_delta_events(self.current_status, status)
                for event in events:
                    self.status_queue.put(event)
                self.current_status = status
            sleep(1)

    def _read_status_file(self) -> Status:
        """Loads data from the JSON file and returns a cleaned version"""
        with open(self.file_path, 'r') as file:
            data = json.load(file)

        status = Status.from_status_file(data)

        return status

    def _create_delta_events(self, old_status: Status, new_status: Status):
        """Creates events specific field that has changed."""
        events = []
        
        if old_status.flags.LandingGearDown and not new_status.flags.LandingGearDown:
            events.append({"event": "LandingGearUp"})
        if not old_status.flags.LandingGearDown and new_status.flags.LandingGearDown:
            events.append({"event": "LandingGearDown"})
        
        if old_status.flags.FlightAssistOff and not new_status.flags.FlightAssistOff:
            events.append({"event": "FlightAssistOn"})
        if not old_status.flags.FlightAssistOff and new_status.flags.FlightAssistOff:
            events.append({"event": "FlightAssistOff"})
        
        if old_status.flags.HardpointsDeployed and not new_status.flags.HardpointsDeployed:
            events.append({"event": "HardpointsRetracted"})
        if not old_status.flags.HardpointsDeployed and new_status.flags.HardpointsDeployed:
            events.append({"event": "HardpointsDeployed"})
        
        if old_status.flags.LightsOn and not new_status.flags.LightsOn:
            events.append({"event": "LightsOff"})
        if not old_status.flags.LightsOn and new_status.flags.LightsOn:
            events.append({"event": "LightsOn"})

        if old_status.flags.CargoScoopDeployed and not new_status.flags.CargoScoopDeployed:
            events.append({"event": "CargoScoopRetracted"})
        if not old_status.flags.CargoScoopDeployed and new_status.flags.CargoScoopDeployed:
            events.append({"event": "CargoScoopDeployed"})
        
        if old_status.flags.SilentRunning and not new_status.flags.SilentRunning:
            events.append({"event": "SilentRunningOff"})
        if not old_status.flags.SilentRunning and new_status.flags.SilentRunning:
            events.append({"event": "SilentRunningOn"})
        
        if old_status.flags.ScoopingFuel and not new_status.flags.ScoopingFuel:
            events.append({"event": "FuelScoopStarted"})
        if not old_status.flags.ScoopingFuel and new_status.flags.ScoopingFuel:
            events.append({"event": "FuelScoopEnded"})

        if old_status.flags.SrvHandbrake and not new_status.flags.SrvHandbrake:
            events.append({"event": "SrvHandbrakeOff"})
        if not old_status.flags.SrvHandbrake and new_status.flags.SrvHandbrake:
            events.append({"event": "SrvHandbrakeOn"})

        if old_status.flags.SrvUsingTurretView and not new_status.flags.SrvUsingTurretView:
            events.append({"event": "SrvTurretViewConnected"})
        if not old_status.flags.SrvUsingTurretView and new_status.flags.SrvUsingTurretView:
            events.append({"event": "SrvTurretViewDisconnected"})
        
        if old_status.flags.SrvDriveAssist and not new_status.flags.SrvDriveAssist:
            events.append({"event": "SrvDriveAssistOff"})
        if not old_status.flags.SrvDriveAssist and new_status.flags.SrvDriveAssist:
            events.append({"event": "SrvDriveAssistOn"})

        if old_status.flags.FsdMassLocked and not new_status.flags.FsdMassLocked:
            events.append({"event": "FsdMassLockEscaped"})
        if not old_status.flags.FsdMassLocked and new_status.flags.FsdMassLocked:
            events.append({"event": "FsdMassLocked"})
        
        if old_status.flags.LowFuel and not new_status.flags.LowFuel:
            events.append({"event": "LowFuelWarningCleared"})
        if not old_status.flags.LowFuel and new_status.flags.LowFuel:
            events.append({"event": "LowFuelWarning"})
        
        if old_status.flags.InDanger and not new_status.flags.InDanger:
            events.append({"event": "OutofDanger"})
        if not old_status.flags.InDanger and new_status.flags.InDanger:
            events.append({"event": "InDanger"})
        
        if old_status.flags.NightVision and not new_status.flags.NightVision:
            events.append({"event": "NightVisionOff"})
        if not old_status.flags.NightVision and new_status.flags.NightVision:
            events.append({"event": "NightVisionOn"})
        
        if old_status.flags2:
            if old_status.flags2.LowOxygen and not new_status.flags2.LowOxygen:
                events.append({"event": "LowOxygenWarningCleared"})
            if not old_status.flags2.LowOxygen and new_status.flags2.LowOxygen:
                events.append({"event": "LowOxygenWarning"})
            
            if old_status.flags2.LowHealth and not new_status.flags2.LowHealth:
                events.append({"event": "LowHealthWarningCleared"})
            if not old_status.flags2.LowHealth and new_status.flags2.LowHealth:
                events.append({"event": "LowHealthWarning"})
            
            if old_status.flags2.GlideMode and not new_status.flags2.GlideMode:
                events.append({"event": "GlideModeExited"})
            if not old_status.flags2.GlideMode and new_status.flags2.GlideMode:
                events.append({"event": "GlideModeEntered"})

            if old_status.flags2.BreathableAtmosphere and not new_status.flags2.BreathableAtmosphere:
                events.append({"event": "BreathableAtmosphereExited"})
            if not old_status.flags2.BreathableAtmosphere and new_status.flags2.BreathableAtmosphere:
                events.append({"event": "BreathableAtmosphereEntered"})
        
        if old_status.LegalState and old_status.LegalState != new_status.LegalState:
            events.append({"event": "LegalStateChanged", "LegalState": new_status.LegalState})
        
        if old_status.SelectedWeapon and old_status.SelectedWeapon != new_status.SelectedWeapon:
            events.append({"event": "WeaponSelected", "SelectedWeapon": new_status.SelectedWeapon})

        return events



# Usage Example
if __name__ == "__main__":
    while True:
        parser = StatusParser()
        cleaned_data = parser._read_status_file()
        print(json.dumps(cleaned_data, indent=4))
        time.sleep(1)
        print("\n"*10)