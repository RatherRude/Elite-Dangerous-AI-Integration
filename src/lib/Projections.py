import math
import re
import traceback
from typing import Any, Literal, TypedDict, final, List, cast
from datetime import datetime, timezone, timedelta
from webbrowser import get

from typing_extensions import NotRequired, override

from .Event import Event, StatusEvent, GameEvent, ProjectedEvent, ExternalEvent, ConversationEvent, ToolEvent
from .EventModels import FSSSignalDiscoveredEvent
from .EventManager import EventManager, Projection
from .Logger import log
from .EDFuelCalc import RATING_BY_CLASSNUM , FSD_OVERCHARGE_STATS , FSD_MKii ,FSD_OVERCHARGE_V2PRE_STATS, FSD_STATS ,FSD_GUARDIAN_BOOSTER
from .StatusParser import parse_status_flags, parse_status_json, Status
from .SystemDatabase import SystemDatabase

DOCKING_PROMPT_COOLDOWN_SECONDS = 360

def latest_event_projection_factory(projectionName: str, gameEvent: str):
    class LatestEvent(Projection[dict[str, Any]]):
        @override
        def get_default_state(self) -> dict[str, Any]:
            return {}

        @override
        def process(self, event: Event) -> None:
            if isinstance(event, GameEvent):
                if gameEvent and event.content.get('event', '') == gameEvent:
                    self.state = event.content

    LatestEvent.__name__ = projectionName

    return LatestEvent


class EventCounter(Projection):
    @override
    def get_default_state(self) -> dict[str, Any]:
        return {"count": 0}

    @override
    def process(self, event: Event) -> None:
        self.state["count"] += 1


class CurrentStatus(Projection[Status]):
    @override
    def get_default_state(self) -> Status:
        return parse_status_json({"flags": parse_status_flags(0)})  # type: ignore

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            self.state = event.status

CargoState = TypedDict('CargoState', {
    "Inventory": list[dict],
    "TotalItems": int,
    "Capacity": int
})

@final
class Cargo(Projection[CargoState]):
    @override
    def get_default_state(self) -> CargoState:
        return {
            "Inventory": [],
            "TotalItems": 0,
            "Capacity": 0
        }
    
    @override
    def process(self, event: Event) -> None:
        # Process Cargo event
        if isinstance(event, GameEvent) and event.content.get('event') == 'Cargo':
            if 'Inventory' in event.content:
                self.state['Inventory'] = []

                for item in event.content.get('Inventory', []):
                    self.state['Inventory'].append({
                        "Name": item.get('Name_Localised', item.get('Name', 'Unknown')),
                        "Count": item.get('Count', 0),
                        "Stolen": item.get('Stolen', 0) > 0
                    })

            if 'Count' in event.content:
                self.state['TotalItems'] = event.content.get('Count', 0)

        # Get cargo capacity from Loadout event
        if isinstance(event, GameEvent) and event.content.get('event') == 'Loadout':
            self.state['Capacity'] = event.content.get('CargoCapacity', 0)
            
        # Update from Status event
        if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
            if 'Cargo' in event.status:
                self.state['TotalItems'] = event.status.get('Cargo', 0)

LocationState = TypedDict('LocationState', {
    "StarSystem": str,
    "Star": NotRequired[str],
    "StarPos": list[float],
    "Planet": NotRequired[str],
    "PlanetaryRing": NotRequired[str],
    "StellarRing": NotRequired[str],
    "Station": NotRequired[str],
    "AsteroidCluster": NotRequired[str],
    "Docked": NotRequired[Literal[True]],
    "Landed": NotRequired[Literal[True]], # only set when true
    "NearestDestination": NotRequired[str], # only when landed on a planet
})

@final
class Location(Projection[LocationState]):
    @override
    def get_default_state(self) -> LocationState:
        return {
            "StarSystem": 'Unknown',
        }
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'Location':
            star_system = event.content.get('StarSystem', 'Unknown')
            body_type = event.content.get('BodyType', 'Null')
            body = event.content.get('Body', 'Unknown')
            station = event.content.get('StationName')
            docked = event.content.get('Docked', False)
            star_pos = event.content.get('StarPos', [0,0,0])

            self.state = {
                "StarSystem": star_system,
                "StarPos": star_pos,
            }
            if station:
                self.state["Station"] = station
                self.state["Docked"] = docked
            if body_type and body_type != 'Null':
                self.state[body_type] = body

        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseEntry':
            star_system = event.content.get('StarSystem', 'Unknown')
            
            self.state = {
                "StarSystem": star_system,
                "StarPos": self.state.get('StarPos', [0,0,0]),
            }
                
        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseExit':
            star_system = event.content.get('StarSystem', 'Unknown')
            body_type = event.content.get('BodyType', 'Null')
            body = event.content.get('Body', 'Unknown')
            
            self.state = {
                "StarSystem": star_system,
                "StarPos": self.state.get('StarPos', [0,0,0]),
            }
            if body_type and body_type != 'Null':
                self.state[body_type] = body
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump':
            star_system = event.content.get('StarSystem', 'Unknown')
            star_pos = event.content.get('StarPos', [0,0,0])
            body_type = event.content.get('BodyType', 'Null')
            body = event.content.get('Body', 'Unknown')
            self.state = {
                "StarSystem": star_system,
                "StarPos": star_pos,
            }
            
            if body_type and body_type != 'Null':
                self.state[body_type] = body

        if isinstance(event, GameEvent) and event.content.get('event') == 'Docked':
            self.state['Docked'] = True
            self.state['Station'] = event.content.get('StationName', 'Unknown')
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Undocked':
            self.state.pop('Docked', None)
                
        if isinstance(event, GameEvent) and event.content.get('event') == 'Touchdown':
            self.state['Landed'] = True
            self.state['NearestDestination'] = event.content.get('NearestDestination', 'Unknown')
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Liftoff':
            self.state.pop('Landed', None)
            
        if isinstance(event, GameEvent) and event.content.get('event') == 'ApproachSettlement':
            self.state['Station'] = event.content.get('Name', 'Unknown')
            self.state['Planet'] = event.content.get('BodyName', 'Unknown')
            
        if isinstance(event, GameEvent) and event.content.get('event') == 'ApproachBody':
            self.state['Station'] = event.content.get('Name', 'Unknown')
            self.state['Planet'] = event.content.get('BodyName', 'Unknown')
            
        if isinstance(event, GameEvent) and event.content.get('event') == 'LeaveBody':
            self.state = {
                "StarSystem": self.state.get('StarSystem', 'Unknown'),
                "StarPos": self.state.get('StarPos', [0,0,0]),
            }

MissionState = TypedDict('MissionState', {
    "Faction": str,
    "Name": str,
    "LocalisedName": str,
    "OriginStation": NotRequired[str | Literal['Unknown']],
    
    # TODO: Are there more fields?
    "Commodity": NotRequired[str], # commodity type
    "Count": NotRequired[int], # number to deliver
    "Target": NotRequired[str], 
    "TargetType": NotRequired[str],
    "TargetFaction": NotRequired[str],
    "DestinationSystem": NotRequired[str],
    "DestinationSettlement": NotRequired[str],
    "DestinationStation": NotRequired[str],
    "PassengerCount": NotRequired[int],
    "PassengerVIPs": NotRequired[bool],
    "PassengerWanted": NotRequired[bool],
    "PassengerType": NotRequired[str], # eg Tourist, Soldier, Explorer,..
    
    "Donation": NotRequired[int],
    "Reward": NotRequired[int],

    "Expiry": str,
    "Wing": bool,
    "Influence": str,
    "Reputation": str,
    "MissionID": int,
})

UnknownMissionState = TypedDict('UnknownMissionState', {
    "MissionID": int,
    "Name": str,
})

MissionsState = TypedDict('MissionsState', {
    "Active":list[MissionState], 
    "Unknown": NotRequired[list[UnknownMissionState]],
})

@final
class Missions(Projection[MissionsState]):
    @override
    def get_default_state(self) -> MissionsState:
        return {
            "Active": [],
        }
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'Missions':
            active_ids = [mission["MissionID"] for mission in event.content.get('Active', [])]
            known_ids = [mission["MissionID"] for mission in self.state["Active"]]
            self.state["Active"] = [mission for mission in self.state["Active"] if mission["MissionID"] in active_ids]
            self.state["Unknown"] = [mission for mission in event.content.get('Active', []) if mission["MissionID"] not in known_ids]
            if not self.state["Unknown"]:
                self.state.pop("Unknown", None)
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionAccepted':
            mission: MissionState = {
                "Faction": event.content.get('Faction', 'Unknown'),
                "Name": event.content.get('Name', 'Unknown'),
                "LocalisedName": event.content.get('LocalisedName', 'Unknown'),
                "Expiry": event.content.get('Expiry', '1970-01-01T00:00:00Z'),
                "Wing": event.content.get('Wing', False),
                "Influence": event.content.get('Influence', 'Unknown'),
                "Reputation": event.content.get('Reputation', 'Unknown'),
                "MissionID": event.content.get('MissionID', 0),
            }
            if 'Donation' in event.content:
                mission["Donation"] = event.content.get('Donation', 0)
            if 'Reward' in event.content:
                mission["Reward"] = event.content.get('Reward', 0)
            
            if 'Commodity' in event.content:
                mission["Commodity"] = event.content.get('Commodity', 'Unknown')
            if 'Count' in event.content:
                mission["Count"] = event.content.get('Count', 0)
            if 'Target' in event.content:
                mission["Target"] = event.content.get('Target', 'Unknown')
            if 'TargetFaction' in event.content:
                mission["TargetFaction"] = event.content.get('TargetFaction', 'Unknown')
            if 'DestinationSystem' in event.content:
                mission["DestinationSystem"] = event.content.get('DestinationSystem', 'Unknown')
            if 'DestinationSettlement' in event.content:
                mission["DestinationSettlement"] = event.content.get('DestinationSettlement', 'Unknown')
            if 'DestinationStation' in event.content:
                mission["DestinationStation"] = event.content.get('DestinationStation', 'Unknown')
            if 'PassengerCount' in event.content:
                mission["PassengerCount"] = event.content.get('PassengerCount', 0)
            if 'PassengerVIPs' in event.content:
                mission["PassengerVIPs"] = event.content.get('PassengerVIPs', False)
            if 'PassengerWanted' in event.content:
                mission["PassengerWanted"] = event.content.get('PassengerWanted', False)
            if 'PassengerType' in event.content:
                mission["PassengerType"] = event.content.get('PassengerType', 'Unknown')
                
            self.state["Active"].append(mission)
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionCompleted':
            mission_id = event.content.get('MissionID', 0)
            self.state["Active"] = [mission for mission in self.state["Active"] if mission["MissionID"] != mission_id]
            if 'Unknown' in self.state:
                self.state["Unknown"] = [mission for mission in self.state["Unknown"] if mission["MissionID"] != mission_id]
                if not self.state["Unknown"]:
                    self.state.pop("Unknown", None)
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionRedirected':
            existing_mission = next((mission for mission in self.state["Active"] if mission["MissionID"] == event.content.get('MissionID', 0)), None)
            new_destination_system = event.content.get('NewDestinationSystem', None)
            new_destination_station = event.content.get('NewDestinationStation', None)
            new_destination_settlement = event.content.get('NewDestinationSettlement', None)
            
            if existing_mission:
                if new_destination_system:
                    existing_mission["DestinationSystem"] = new_destination_system
                if new_destination_station:
                    existing_mission["DestinationStation"] = new_destination_station
                    if existing_mission["DestinationStation"] == existing_mission.get("OriginStation", None):
                        existing_mission["Name"] += " (Collect Reward)"
                if new_destination_settlement:
                    existing_mission["DestinationSettlement"] = new_destination_settlement
            
                self.state["Active"] = [mission for mission in self.state["Active"] if mission["MissionID"] != event.content.get('MissionID', 0)]
                self.state["Active"].append(existing_mission)
                
        # If we Undock with a new mission, we probably accepted it at the station we undocked from
        if isinstance(event, GameEvent) and event.content.get('event') == 'Undocked':
            for mission in self.state["Active"]:
                if 'Origin' not in mission:
                    mission["OriginStation"] = event.content.get('StationName', 'Unknown')
        # If we Dock with a new mission, we probably accepted it somewhere in space, so we don't know the exact origin
        if isinstance(event, GameEvent) and event.content.get('event') == 'Docked':
            for mission in self.state["Active"]:
                if 'Origin' not in mission:
                    mission["OriginStation"] = 'Unknown'
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionAbandoned':
            mission_id = event.content.get('MissionID', 0)
            self.state["Active"] = [mission for mission in self.state["Active"] if mission["MissionID"] != mission_id]
            if 'Unknown' in self.state:
                self.state["Unknown"] = [mission for mission in self.state["Unknown"] if mission["MissionID"] != mission_id]
                if not self.state["Unknown"]:
                    self.state.pop("Unknown", None)
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'MissionFailed':
            mission_id = event.content.get('MissionID', 0)
            self.state["Active"] = [mission for mission in self.state["Active"] if mission["MissionID"] != mission_id]
            if 'Unknown' in self.state:
                self.state["Unknown"] = [mission for mission in self.state["Unknown"] if mission["MissionID"] != mission_id]
                if not self.state["Unknown"]:
                    self.state.pop("Unknown", None)

# Define types for EngineerProgress Projection
EngineerState = TypedDict('EngineerState', {
    "Engineer": str,
    "EngineerID": int,
    "Progress": NotRequired[str],  # Invited/Acquainted/Unlocked/Barred
    "Rank": NotRequired[int],
    "RankProgress": NotRequired[int],
})

EngineerProgressState = TypedDict('EngineerProgressState', {
    "event": str,
    "timestamp": str,
    "Engineers": list[EngineerState],
})

@final
class EngineerProgress(Projection[EngineerProgressState]):
    @override
    def get_default_state(self) -> EngineerProgressState:
        return {
            "event": "EngineerProgress",
            "timestamp": "1970-01-01T00:00:00Z",
            "Engineers": [],
        }
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'EngineerProgress':
            # Handle startup form - save entire event
            if 'Engineers' in event.content:
                self.state = event.content
            
            # Handle update form - single engineer update
            elif 'Engineer' in event.content and 'EngineerID' in event.content:
                engineer_id = event.content.get('EngineerID', 0)
                
                # Ensure Engineers list exists
                if 'Engineers' not in self.state:
                    self.state["Engineers"] = []
                
                # Find existing engineer or create new one
                existing_engineer = None
                for i, engineer in enumerate(self.state["Engineers"]):
                    if engineer["EngineerID"] == engineer_id:
                        existing_engineer = self.state["Engineers"][i]
                        break
                
                if existing_engineer:
                    # Update existing engineer
                    if 'Engineer' in event.content:
                        existing_engineer["Engineer"] = event.content.get('Engineer', 'Unknown')
                    if 'Progress' in event.content:
                        existing_engineer["Progress"] = event.content.get('Progress', 'Unknown')
                    if 'Rank' in event.content:
                        existing_engineer["Rank"] = event.content.get('Rank', 0)
                    if 'RankProgress' in event.content:
                        existing_engineer["RankProgress"] = event.content.get('RankProgress', 0)
                else:
                    # Create new engineer entry
                    new_engineer: EngineerState = {
                        "Engineer": event.content.get('Engineer', 'Unknown'),
                        "EngineerID": engineer_id,
                    }
                    if 'Progress' in event.content:
                        new_engineer["Progress"] = event.content.get('Progress', 'Unknown')
                    if 'Rank' in event.content:
                        new_engineer["Rank"] = event.content.get('Rank', 0)
                    if 'RankProgress' in event.content:
                        new_engineer["RankProgress"] = event.content.get('RankProgress', 0)
                    
                    self.state["Engineers"].append(new_engineer)

# Define types for CommunityGoal Projection
CommunityGoalTopTier = TypedDict('CommunityGoalTopTier', {
    "Name": str,
    "Bonus": str,
})

CommunityGoalItem = TypedDict('CommunityGoalItem', {
    "CGID": int,
    "Title": str,
    "SystemName": str,
    "MarketName": str,
    "Expiry": str,
    "IsComplete": bool,
    "CurrentTotal": int,
    "PlayerContribution": int,
    "NumContributors": int,
    "TopTier": CommunityGoalTopTier,
    "TopRankSize": NotRequired[int],
    "PlayerInTopRank": NotRequired[bool],
    "TierReached": str,
    "PlayerPercentileBand": int,
    "Bonus": int,
})

CommunityGoalState = TypedDict('CommunityGoalState', {
    "event": NotRequired[str],
    "timestamp": NotRequired[str],
    "CurrentGoals": NotRequired[list[CommunityGoalItem]],
})

@final
class CommunityGoal(Projection[CommunityGoalState]):
    @override
    def get_default_state(self) -> CommunityGoalState:
        return {}

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'CommunityGoal':
            # Save entire event content when receiving CommunityGoal event
            self.state = cast(CommunityGoalState, event.content)
        
        elif isinstance(event, GameEvent) and event.content.get('event') == 'LoadGame':
            # Check for expired goals and remove them
            from datetime import datetime
            current_time = event.timestamp
            current_dt = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
            
            # Filter out expired goals
            active_goals = []
            for goal in self.state.get("CurrentGoals", []):
                expiry_time = goal.get("Expiry", "1970-01-01T00:00:00Z")
                expiry_dt = datetime.fromisoformat(expiry_time.replace('Z', '+00:00'))
                
                # Keep goal if it hasn't expired yet
                if current_dt < expiry_dt:
                    active_goals.append(goal)
            
            # Update state with only non-expired goals
            self.state["CurrentGoals"] = active_goals

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

FighterState = TypedDict('FighterState', {
    "ID": NotRequired[int],
    "Status": Literal['Ready', 'Launched', 'BeingRebuilt', 'Abandoned'],
    "Pilot": NotRequired[str],
    "RebuiltAt": NotRequired[str]
})

ShipInfoState = TypedDict('ShipInfoState', {
    "Name": str,
    "Type": str,
    "ShipIdent": str,
    "UnladenMass": float,
    "Cargo": float,
    "CargoCapacity": float,
    "ShipCargo": float,
    "FuelMain": float,
    "FuelMainCapacity": float,
    "FuelReservoir": float,
    "FuelReservoirCapacity": float,
    "FSDSynthesis":float,
    "ReportedMaximumJumpRange": float,
    "DriveOptimalMass":float,
    "DriveLinearConst":float,
    "DrivePowerConst":float,
    "GuardianfsdBooster":float,
    "DriveMaxFuel":float,
    "JetConeBoost":float,
    "MinimumJumpRange":float,
    "CurrentJumpRange":float,
    "MaximumJumpRange":float,
    "LandingPadSize": Literal['S', 'M', 'L', 'Unknown'],
    "IsMiningShip": bool,
    "hasLimpets": bool,
    "hasDockingComputer": bool,
    "Fighters": list[FighterState],
})

@final
class ShipInfo(Projection[ShipInfoState]):
    @override
    def get_default_state(self) -> ShipInfoState:
        return {
            "Name": 'Unknown',
            "Type": 'Unknown',
            "ShipIdent": "Unknown", 
            "UnladenMass": 0,
            "Cargo": 0,
            "CargoCapacity": 0,
            "ShipCargo": 0,
            "FuelMain": 0,
            "FuelMainCapacity": 0,
            "FuelReservoir": 0,
            "FuelReservoirCapacity": 0,
            "ReportedMaximumJumpRange": 0,
            "FSDSynthesis":0,
            "DriveOptimalMass": 0,
            "DriveLinearConst":0,
            "GuardianfsdBooster":0,
            "DrivePowerConst":0,
            "DriveMaxFuel":0,
            "JetConeBoost":1,
            "IsMiningShip": False,
            "hasLimpets": False,
            "hasDockingComputer": False,
            "Fighters": [],
            "MinimumJumpRange":0,
            "CurrentJumpRange":0,
            "MaximumJumpRange":0,
            "LandingPadSize": 'Unknown',
        }
    
    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
     
        if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
            status: Status = event.status  # pyright: ignore[reportAssignmentType]
            if 'Cargo' in event.status:
                self.state['Cargo'] = event.status.get('Cargo', 0)
                
            if 'Fuel' in status and status['Fuel']:
                self.state['FuelMain'] = status['Fuel'].get('FuelMain', 0)
                self.state['FuelReservoir'] = status['Fuel'].get('FuelReservoir', 0)
                
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Loadout':
            if 'ShipName' in event.content:
                self.state['Name'] = event.content.get('ShipName', 'Unknown')
            if 'Ship' in event.content:
                self.state['Type'] = event.content.get('Ship', 'Unknown')
            if 'ShipIdent' in event.content:
                self.state['ShipIdent'] = event.content.get('ShipIdent', 'Unknown')
            if 'UnladenMass' in event.content:
                self.state['UnladenMass'] = event.content.get('UnladenMass', 0)
            if 'CargoCapacity' in event.content:
                self.state['CargoCapacity'] = event.content.get('CargoCapacity', 0)
            if 'FuelCapacity' in event.content:
                self.state['FuelMainCapacity'] = event.content['FuelCapacity'].get('Main', 0)
                self.state['FuelReservoirCapacity'] = event.content['FuelCapacity'].get('Reserve', 0)

            if 'MaxJumpRange' in event.content:
                self.state['ReportedMaximumJumpRange'] = event.content.get('MaxJumpRange', 0)

            if 'Modules' in event.content:
                has_refinery = any(module["Item"].startswith("int_refinery") for module in event.content["Modules"])
                if has_refinery:
                    self.state['IsMiningShip'] = True
                else:
                    self.state['IsMiningShip'] = False

                has_limpets = any(
                    module.get("Item", "").startswith("int_dronecontrol")
                    or module.get("Item", "").startswith("int_multidronecontrol_")
                    for module in event.content["Modules"]
                )
                if has_limpets:
                    self.state['hasLimpets'] = True
                else:
                    self.state['hasLimpets'] = False

                has_docking_computer = any(
                    module.get("Item", "").startswith("int_dockingcomputer")
                    for module in event.content["Modules"]
                )
                if has_docking_computer:
                    self.state['hasDockingComputer'] = True
                else:
                    self.state['hasDockingComputer'] = False

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
                    self.state['Fighters'] = [{"Status": "Ready"} for _ in range(fighter_count)]
                else:
                    self.state['Fighters'] = []

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
                    self.state['DriveOptimalMass'] = engineering_optimal_mass_override if engineering_optimal_mass_override is not None else module_stat.get('opt_mass', 0.00)
                    self.state['DriveMaxFuel'] = engineering_max_fuel_override if engineering_max_fuel_override is not None else module_stat.get('max_fuel', 0.00)
                    self.state['DriveLinearConst'] = module_stat.get('linear_const', 0.0)
                    self.state['DrivePowerConst'] = module_stat.get('power_const', 0.0)

                    log('debug','mkii?: ',mkii,' Fsd type again :', module_item)
                    
                # Check for GuardianfsdBooster
                self.state['GuardianfsdBooster'] = 0
                for module in event.content.get("Modules", []):
                    module_item = module.get('Item')
                    if "int_guardianfsdbooster" in module_item.lower():    
                        module_size_match = re.search(r"size(\d+)", module_item)
                        module_size = int(module_size_match.group(1))
                        guardian_booster_stats = FSD_GUARDIAN_BOOSTER.get((module_size,"H"))
                        
                        self.state['GuardianfsdBooster'] =guardian_booster_stats.get('jump_boost', 0.0)
                          
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'JetConeBoost':
            fsd_star_boost = event.content.get('BoostValue', 1)
            self.state['JetConeBoost'] = fsd_star_boost
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Synthesis':
            fsd_inject_boost_name = event.content.get('Name', "")

            if fsd_inject_boost_name == "FSD Basic":
                self.state['FSDSynthesis'] = 0.25

            elif fsd_inject_boost_name == "FSD Standard":
                self.state['FSDSynthesis'] = 0.5

            elif fsd_inject_boost_name == "FSD Premium":
                self.state['FSDSynthesis'] = 1

        if isinstance(event,GameEvent) and event.content.get('event') == 'FSDJump':
            self.state['JetConeBoost'] = 1
            self.state['FSDSynthesis'] = 0

        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Cargo':
            self.state['Cargo'] = event.content.get('Count', 0)
            if event.content.get('Vessel') == 'Ship': 
                self.state['ShipCargo'] = event.content.get('Count', 0)

        if isinstance(event, GameEvent) and event.content.get('event') in ['RefuelAll','RepairAll','BuyAmmo']:
            if self.state['hasLimpets'] and self.state['Cargo'] < self.state['CargoCapacity']:
                projected_events.append(ProjectedEvent(content={"event": "RememberLimpets"}))

        if isinstance(event, GameEvent) and event.content.get('event') == 'SetUserShipName':
            if 'UserShipName' in event.content:
                self.state['Name'] = event.content.get('UserShipName', 'Unknown')
            if 'UserShipId' in event.content:
                self.state['ShipIdent'] = event.content.get('UserShipId', 'Unknown')

        # Fighter events
        # No events for crew fighter destroyed or docked...
        # if isinstance(event, GameEvent) and event.content.get('event') == 'CrewLaunchFighter':
        #     # Commander launches fighter for crew member
        #     crew_name = event.content.get('Crew', 'Unknown Crew')
        #
        #     # Find a ready fighter without ID to assign to crew
        #     for fighter in self.state['Fighters']:
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
                for fighter in self.state['Fighters']:
                    if fighter.get('ID') == fighter_id:
                        # Fighter with this ID already exists
                        fighter['Status'] = 'Launched'
                        fighter['Pilot'] = pilot
                        fighter_found = True
                        break
                
                if not fighter_found:
                    # Find a ready fighter without ID
                    for fighter in self.state['Fighters']:
                        if fighter['Status'] == 'Ready' and 'ID' not in fighter:
                            fighter['ID'] = fighter_id
                            fighter['Status'] = 'Launched'
                            fighter['Pilot'] = pilot
                            break

        if isinstance(event, GameEvent) and event.content.get('event') == 'DockFighter':
            fighter_id = event.content.get('ID')
            
            # Find fighter by ID and set to ready, clear ID
            for fighter in self.state['Fighters']:
                if fighter.get('ID') == fighter_id:
                    fighter['Status'] = 'Ready'
                    fighter.pop('ID', None)
                    fighter.pop('Pilot', None)
                    break

        if isinstance(event, GameEvent) and event.content.get('event') == 'FighterDestroyed':
            fighter_id = event.content.get('ID')
            
            # Calculate rebuild completion time (80 seconds from now)
            current_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            rebuild_time = current_time + timedelta(seconds=90)
            rebuild_timestamp = rebuild_time.isoformat().replace('+00:00', 'Z')
            
            # Find fighter by ID and set to being rebuilt
            for fighter in self.state['Fighters']:
                if fighter.get('ID') == fighter_id:
                    fighter['Status'] = 'BeingRebuilt'
                    fighter['RebuiltAt'] = rebuild_timestamp
                    fighter.pop('Pilot', None)
                    break

        if isinstance(event, GameEvent) and event.content.get('event') == 'FighterRebuilt':
            fighter_id = event.content.get('ID')
            
            # Find fighter by ID and set to ready, clear ID
            for fighter in self.state['Fighters']:
                if fighter.get('ID') == fighter_id:
                    fighter['Status'] = 'Ready'
                    fighter.pop('ID', None)
                    fighter.pop('Pilot', None)
                    fighter.pop('RebuiltAt', None)
                    break

        if isinstance(event, GameEvent) and event.content.get('event') == 'VehicleSwitch':
            vehicle_to = event.content.get('To', '')
            
            if vehicle_to == 'Mothership':
                # Commander switched back to mothership, fighter becomes abandoned
                for fighter in self.state['Fighters']:
                    if fighter.get('Pilot') == 'Commander' and fighter['Status'] == 'Launched':
                        fighter['Status'] = 'Abandoned'
                        fighter['Pilot'] = 'No pilot'
                        break
            
            elif vehicle_to == 'Fighter':
                # Commander switched to fighter, set fighter back to launched
                for fighter in self.state['Fighters']:
                    if fighter['Status'] == 'Abandoned' and fighter.get('Pilot') == 'No pilot':
                        fighter['Status'] = 'Launched'
                        fighter['Pilot'] = 'Commander'
                        break

        if self.state['Type'] != 'Unknown':
            self.state['LandingPadSize'] = ship_sizes.get(self.state['Type'], 'Unknown')
            
        # Recalculate jump ranges on weight, module or modifier changes
        if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
            try:
                min_jr,cur_jr,max_jr = self.calculate_jump_range()
                self.state['MinimumJumpRange'] = min_jr
                self.state['CurrentJumpRange'] = cur_jr
                self.state['MaximumJumpRange'] = max_jr
            except Exception as e:
                log('error', 'Error calculating jump ranges:', e, traceback.format_exc())
        
        return projected_events
    
    def calculate_jump_range(self) -> tuple[float, float, float]:

        unladen_mass   = self.state.get("UnladenMass")
        cargo_capacity = self.state.get("CargoCapacity")
        fuel_capacity  = self.state.get("FuelMainCapacity")
        maximum_jump_range     = self.state.get("ReportedMaximumJumpRange")
        drive_power_const   = self.state.get("DrivePowerConst")
        drive_optimal_mass = self.state.get("DriveOptimalMass")
        drive_linear_const  = self.state.get("DriveLinearConst") 
        drive_max_fuel  = self.state.get("DriveMaxFuel")
        fsd_star_boost = self.state.get("JetConeBoost")
        fsd_boost = self.state.get("GuardianfsdBooster")
        fsd_inject = self.state.get("FSDSynthesis") # +inject juice 25% , 50% ,100% but cant be with star_boost

        if not (unladen_mass > 0 and fuel_capacity > 0 and maximum_jump_range > 0 and drive_max_fuel):
            return 0, 0, 0

        current_cargo = self.state.get("ShipCargo")
        current_fuel  = self.state.get("FuelMain")
        current_fuel_reservoir = self.state.get("FuelReservoir")

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

TargetState = TypedDict('TargetState', {
    "EventID": NotRequired[str],
    "Ship": NotRequired[str],
    "ScanStage": NotRequired[int],

    "PilotName": NotRequired[str],
    "PilotRank": NotRequired[str],
    "Faction": NotRequired[str],
    "LegalStatus": NotRequired[str],
    "Bounty": NotRequired[int],
    "ShieldHealth": NotRequired[float],
    "HullHealth": NotRequired[float],
    "SubsystemHealth": NotRequired[float],

    "Subsystem": NotRequired[str],
})


@final
class Target(Projection[TargetState]):
    @override
    def get_default_state(self) -> TargetState:
        return {}

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        global keys
        if isinstance(event, GameEvent) and event.content.get('event') in ['LoadGame', 'Shutdown']:
            self.state = self.get_default_state()
        if isinstance(event, GameEvent) and event.content.get('event') == 'ShipTargeted':
            if not event.content.get('TargetLocked', False):
                self.state = self.get_default_state()
            else:
                self.state = self.get_default_state()
                self.state['Ship'] = event.content.get('Ship_Localised', event.content.get('Ship', ''))
                self.state['ScanStage'] = int(event.content.get('ScanStage', 0) or 0)

                pilot_name_value = event.content.get('PilotName_Localised') or event.content.get('PilotName')
                if pilot_name_value:
                    self.state["PilotName"] = pilot_name_value

                if 'PilotRank' in event.content:
                    self.state["PilotRank"] = event.content.get('PilotRank', '')

                if 'Faction' in event.content:
                    self.state["Faction"] = event.content.get('Faction', '')

                if 'LegalStatus' in event.content:
                    self.state["LegalStatus"] = event.content.get('LegalStatus', '')

                if 'Bounty' in event.content:
                    self.state["Bounty"] = int(event.content.get('Bounty', 0) or 0)
                    if event.content.get('Bounty', 0) > 1 and not event.content.get('Subsystem', False):
                        projected_events.append(ProjectedEvent(content={"event": "BountyScanned"}))

                if 'ShieldHealth' in event.content:
                    self.state["ShieldHealth"] = float(event.content.get('ShieldHealth', 0.0) or 0.0)

                if 'HullHealth' in event.content:
                    self.state["HullHealth"] = float(event.content.get('HullHealth', 0.0) or 0.0)

                if 'SubsystemHealth' in event.content:
                    self.state["SubsystemHealth"] = float(event.content.get('SubsystemHealth', 0.0) or 0.0)

                subsystem_value = event.content.get('Subsystem_Localised', event.content.get('Subsystem', ''))
                if subsystem_value:
                    self.state["Subsystem"] = subsystem_value
            self.state['EventID'] = event.content.get('id')
        return projected_events


StoredModuleItem = TypedDict('StoredModuleItem', {
    "Name": str,
    "Name_Localised": str,
    "StorageSlot": int,
    "BuyPrice": int,
    "Hot": bool,
    
    # Present when in transit
    "InTransit": NotRequired[bool],
    
    # Present when stored at location (not in transit)
    "StarSystem": NotRequired[str],
    "MarketID": NotRequired[int],
    "TransferCost": NotRequired[int],
    "TransferTime": NotRequired[int],
    
    # Optional in both states
    "EngineerModifications": NotRequired[str],
    "Level": NotRequired[int],
    "Quality": NotRequired[float],
})

FetchRemoteModuleItem = TypedDict('FetchRemoteModuleItem', {
    "MarketID": int,
    "StationName": str,
    "StarSystem": str,
    "StorageSlot": int,
    "TransferCompleteTime": str,  # ISO timestamp when transfer completes
    "TransferCost": int,
})

StoredModulesState = TypedDict('StoredModulesState', {
    "MarketID": int,
    "StationName": str,
    "StarSystem": str,
    "Items": list[StoredModuleItem],
    "ItemsInTransit": list[FetchRemoteModuleItem],
})


@final
class StoredModules(Projection[StoredModulesState]):
    @override
    def get_default_state(self) -> StoredModulesState:
        return {
            "MarketID": 0,
            "StationName": "",
            "StarSystem": "",
            "Items": [],
            "ItemsInTransit": []
        }

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, GameEvent) and event.content.get('event') == 'StoredModules':
            # Save the event as-is (all fields are required in the event)
            self.state['MarketID'] = event.content.get('MarketID', 0)
            self.state['StationName'] = event.content.get('StationName', '')
            self.state['StarSystem'] = event.content.get('StarSystem', '')
            self.state['Items'] = event.content.get('Items', [])

        if isinstance(event, GameEvent) and event.content.get('event') == 'FetchRemoteModule':
            # Calculate completion timestamp using the event's timestamp
            transfer_time_seconds = event.content.get('TransferTime', 0)
            event_timestamp = datetime.fromisoformat(event.content.get('timestamp', datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00'))
            completion_time = event_timestamp + timedelta(seconds=transfer_time_seconds)
            
            # Create an item in transit using data from the event and current state
            transit_item: FetchRemoteModuleItem = {
                "MarketID": self.state.get('MarketID', 0),
                "StationName": self.state.get('StationName', ''),
                "StarSystem": self.state.get('StarSystem', ''),
                "StorageSlot": event.content.get('StorageSlot', 0),
                "TransferCompleteTime": completion_time.isoformat(),
                "TransferCost": event.content.get('TransferCost', 0),
            }

            self.state['ItemsInTransit'].append(transit_item)

        # Check if any items in transit have completed
        if len(self.state['ItemsInTransit']) > 0:
            log('info', 'in transit')
            # Use event timestamp if available, otherwise use current time
            if isinstance(event, GameEvent) and 'timestamp' in event.content:
                current_time = datetime.fromisoformat(event.content.get('timestamp', '').replace('Z', '+00:00'))
            else:
                current_time = datetime.now(timezone.utc)
            
            completed_items: list[FetchRemoteModuleItem] = []
            
            for transit_item in self.state['ItemsInTransit']:
                completion_time = datetime.fromisoformat(transit_item['TransferCompleteTime'])
                if current_time >= completion_time:
                    completed_items.append(transit_item)
                    log('info', 'added to transit' + str(transit_item['StorageSlot']))

            # Process completed transfers
            for completed in completed_items:
                storage_slot = completed['StorageSlot']
                
                # Find the item in Items with matching StorageSlot and update it
                for item in self.state['Items']:
                    if item.get('StorageSlot') == storage_slot:
                        # Remove in-transit flag if present
                        if 'InTransit' in item:
                            del item['InTransit']
                        
                        # Add location information
                        item['StarSystem'] = completed['StarSystem']
                        item['MarketID'] = completed['MarketID']
                        item['TransferCost'] = completed['TransferCost']
                        item['TransferTime'] = 0  # Transfer is complete
                        break
                
                # Remove from ItemsInTransit
                self.state['ItemsInTransit'].remove(completed)
                projected_events.append(ProjectedEvent(content={"event": "FetchRemoteModuleCompleted"}))
                log('info', 'removed to transit' + str(completed['StorageSlot']))

        return projected_events


ShipHereItem = TypedDict('ShipHereItem', {
    "ShipID": int,
    "ShipType": str,
    "Name": str,
    "Value": int,
    "Hot": bool,
})

ShipRemoteItem = TypedDict('ShipRemoteItem', {
    "ShipID": int,
    "ShipType": str,
    "ShipType_Localised": NotRequired[str],
    "Name": str,
    "StarSystem": NotRequired[str],
    "ShipMarketID": NotRequired[int],
    "TransferPrice": NotRequired[int],
    "TransferTime": NotRequired[int],
    "Value": int,
    "Hot": bool,
    "InTransit": NotRequired[bool],
})

ShipInTransitItem = TypedDict('ShipInTransitItem', {
    "ShipID": int,
    "ShipType": str,
    "System": str,  # Destination system
    "ShipMarketID": int,  # Destination market
    "TransferCompleteTime": str,  # ISO timestamp
    "TransferPrice": int,
})

StoredShipsState = TypedDict('StoredShipsState', {
    "StationName": str,
    "MarketID": int,
    "StarSystem": str,
    "ShipsHere": list[ShipHereItem],
    "ShipsRemote": list[ShipRemoteItem],
    "ShipsInTransit": list[ShipInTransitItem],
})


@final
class StoredShips(Projection[StoredShipsState]):
    @override
    def get_default_state(self) -> StoredShipsState:
        return {
            "StationName": "",
            "MarketID": 0,
            "StarSystem": "",
            "ShipsHere": [],
            "ShipsRemote": [],
            "ShipsInTransit": []
        }

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, GameEvent) and event.content.get('event') == 'StoredShips':
            # Save the event as-is (all fields are required in the event)
            self.state['StationName'] = event.content.get('StationName', '')
            self.state['MarketID'] = event.content.get('MarketID', 0)
            self.state['StarSystem'] = event.content.get('StarSystem', '')
            self.state['ShipsHere'] = event.content.get('ShipsHere', [])
            self.state['ShipsRemote'] = event.content.get('ShipsRemote', [])

        if isinstance(event, GameEvent) and event.content.get('event') == 'ShipyardTransfer':
            # Calculate completion timestamp using the event's timestamp
            transfer_time_seconds = event.content.get('TransferTime', 0)
            event_timestamp = datetime.fromisoformat(event.content.get('timestamp', datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00'))
            completion_time = event_timestamp + timedelta(seconds=transfer_time_seconds)
            
            # Create a ship in transit using data from the event
            transit_item: ShipInTransitItem = {
                "ShipID": event.content.get('ShipID', 0),
                "ShipType": event.content.get('ShipType', ''),
                "System": self.state.get('StarSystem', ''),
                "ShipMarketID": self.state.get('MarketID', 0),
                "TransferCompleteTime": completion_time.isoformat(),
                "TransferPrice": event.content.get('TransferPrice', 0),
            }

            self.state['ShipsInTransit'].append(transit_item)

        # Check if any ships in transit have completed
        if len(self.state['ShipsInTransit']) > 0:
            # Use event timestamp if available, otherwise use current time
            if isinstance(event, GameEvent) and 'timestamp' in event.content:
                current_time = datetime.fromisoformat(event.content.get('timestamp', '').replace('Z', '+00:00'))
            else:
                current_time = datetime.now(timezone.utc)
            
            completed_items: list[ShipInTransitItem] = []
            
            for transit_item in self.state['ShipsInTransit']:
                completion_time = datetime.fromisoformat(transit_item['TransferCompleteTime'])
                if current_time >= completion_time:
                    completed_items.append(transit_item)
            
            # Process completed transfers
            for completed in completed_items:
                ship_id = completed['ShipID']
                
                # Find the ship in ShipsRemote with matching ShipID and update it
                for ship in self.state['ShipsRemote']:
                    if ship.get('ShipID') == ship_id:
                        # Remove in-transit flag if present
                        if 'InTransit' in ship:
                            del ship['InTransit']
                        
                        # Add location information
                        ship['StarSystem'] = completed['System']
                        ship['ShipMarketID'] = completed['ShipMarketID']
                        ship['TransferPrice'] = completed['TransferPrice']
                        ship['TransferTime'] = 0  # Transfer is complete
                        break
                
                # Remove from ShipsInTransit
                self.state['ShipsInTransit'].remove(completed)
                projected_events.append(ProjectedEvent(content={"event": "ShipyardTransferCompleted"}))

        return projected_events


NavRouteItem = TypedDict('NavRouteItem', {
    "StarSystem": str,
    "Scoopable": bool
})

NavInfoState = TypedDict('NavInfoState', {
    "NextJumpTarget": NotRequired[str],
    "NavRoute": list[NavRouteItem],
    # TODO: System local targets? (planet, station, etc)
})

@final
class NavInfo(Projection[NavInfoState]):
    def __init__(self, system_db: SystemDatabase):
        super().__init__()
        self.system_db = system_db
    
    @override
    def get_default_state(self) -> NavInfoState:
        return {
            "NextJumpTarget": 'Unknown',
            "NavRoute": [],
        }

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        # Process NavRoute event
        if isinstance(event, GameEvent) and event.content.get('event') == 'NavRoute':
            if event.content.get('Route', []):
                self.state['NavRoute'] = []
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
                        self.state['NavRoute'].append({
                            "StarSystem": star_system, 
                            "Scoopable": is_scoopable
                        })
                    else:
                        # No longer the first system after the first iteration
                        is_first_system = False
                
                # Fetch system data for systems in the route asynchronously
                if len(systems_to_lookup) > 1:
                    systems_to_lookup.pop(0)
                    self.system_db.fetch_multiple_systems_nonblocking(systems_to_lookup)

        # Process NavRouteClear
        if isinstance(event, GameEvent) and event.content.get('event') == 'NavRouteClear':
            self.state['NavRoute'] = []
            
        # Process FSDJump - remove visited systems from route
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump':
            for index, entry in enumerate(self.state['NavRoute']):
                if entry['StarSystem'] == event.content.get('StarSystem'):
                    self.state['NavRoute'] = self.state['NavRoute'][index+1:]
                    break

            if len(self.state['NavRoute']) == 0 and 'NextJumpTarget' in self.state:
                self.state.pop('NextJumpTarget')

            # Calculate remaining jumps based on fuel
            fuel_level = event.content.get('FuelLevel', 0)
            fuel_used = event.content.get('FuelUsed', 0)
            remaining_jumps = int(fuel_level / fuel_used)

            # Check if we have enough scoopable stars between current and destination system)
            if not len(self.state['NavRoute']) == 0 and remaining_jumps < len(self.state['NavRoute']) - 1:
                # Count scoopable stars in the remaining jumps
                scoopable_stars = sum(
                    1 for entry in self.state['NavRoute'][:remaining_jumps]
                    if entry.get('Scoopable', False)
                )

                # Only warn if we can't reach any scoopable stars
                if scoopable_stars == 0:
                    projected_events.append(ProjectedEvent(content={"event": "NoScoopableStars"}))

        # Process FSDTarget
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDTarget':
            if 'Name' in event.content:
                system_name = event.content.get('Name', 'Unknown')
                self.state['NextJumpTarget'] = system_name
                # Fetch system data for the target system asynchronously
                self.system_db.fetch_system_data_nonblocking(system_name)
                
        # Process Location to fetch system data
        if isinstance(event, GameEvent) and event.content.get('event') == 'Location':
            star_system = event.content.get('StarSystem', 'Unknown')
            if star_system != 'Unknown':
                # Fetch system data for the current system asynchronously
                self.system_db.fetch_system_data_nonblocking(star_system)

        if isinstance(event, GameEvent) and event.content.get('event') == 'Scan':
            auto_scan = event.content.get('ScanType')
            distancefromarrival = event.content.get('DistanceFromArrivalLS', 1)

            if auto_scan == 'AutoScan' and distancefromarrival < 0.2:  # pyright: ignore[reportOptionalOperand]
                was_discovered = event.content.get('WasDiscovered', True)  # system mapped

                if was_discovered == False:
                    projected_events.append(ProjectedEvent(content={"event": "FirstPlayerSystemDiscovered"}))

        return projected_events

# Define types for Backpack Projection
BackpackItem = TypedDict('BackpackItem', {
    "Name": str,
    "Name_Localised": NotRequired[str],
    "OwnerID": int,
    "Count": int
})

BackpackState = TypedDict('BackpackState', {
    "Items": list[BackpackItem],
    "Components": list[BackpackItem],
    "Consumables": list[BackpackItem],
    "Data": list[BackpackItem]
})

@final
class Backpack(Projection[BackpackState]):
    @override
    def get_default_state(self) -> BackpackState:
        return {
            "Items": [],
            "Components": [],
            "Consumables": [],
            "Data": []
        }
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent):
            # Full backpack update
            if event.content.get('event') == 'Backpack':
                # Reset and update all categories
                self.state["Items"] = event.content.get("Items", [])
                self.state["Components"] = event.content.get("Components", [])
                self.state["Consumables"] = event.content.get("Consumables", [])
                self.state["Data"] = event.content.get("Data", [])
            
            # Backpack additions
            elif event.content.get('event') == 'BackpackChange' and 'Added' in event.content:
                for item in event.content.get('Added', []):
                    item_type = item.get('Type', '')
                    # Create a copy without the Type field for storing
                    item_copy = {k: v for k, v in item.items() if k != 'Type'}
                    
                    if item_type == 'Item':
                        self._add_or_update_item("Items", item_copy)
                    elif item_type == 'Component':
                        self._add_or_update_item("Components", item_copy)
                    elif item_type == 'Consumable':
                        self._add_or_update_item("Consumables", item_copy)
                    elif item_type == 'Data':
                        self._add_or_update_item("Data", item_copy)
            
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
    
    def _add_or_update_item(self, category: str, new_item: dict) -> None:
        """Add a new item or update the count of an existing item in the specified category."""
        for item in self.state[category]:
            if item["Name"] == new_item["Name"]:
                # Item exists, update count
                item["Count"] += new_item["Count"]
                return
        
        # Item doesn't exist, add it
        self.state[category].append(new_item)
    
    def _remove_item(self, category: str, item_name: str, count: int) -> None:
        """Remove an item or reduce its count in the specified category."""
        for i, item in enumerate(self.state[category]):
            if item["Name"] == item_name:
                # Reduce count
                item["Count"] -= count
                
                # Remove item if count is zero or less
                if item["Count"] <= 0:
                    self.state[category].pop(i)
                
                break

class ExobiologyScanStateScan(TypedDict):
    lat: float
    long: float

ExobiologyScanState = TypedDict('ExobiologyScanState', {
    "within_scan_radius": NotRequired[bool],
    # "distance": NotRequired[float],
    "scan_radius": NotRequired[int],
    "scans": list[ExobiologyScanStateScan],
    "lat": NotRequired[float],
    "long": NotRequired[float],
    "life_form": NotRequired[str]
})
@final
class ExobiologyScan(Projection[ExobiologyScanState]):
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

    def haversine_distance(self, new_value:dict[str,float], old_value:dict[str,float], radius:int):
        lat1, lon1 = math.radians(new_value['lat']), math.radians(new_value['long'])
        lat2, lon2 = math.radians(old_value['lat']), math.radians(old_value['long'])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Haversine formula
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = radius * c
        return distance

    @override
    def get_default_state(self) -> ExobiologyScanState:
        return {
            "within_scan_radius": True,
            "scans": [],
        }

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, StatusEvent) and event.status.get("event") == "Status":
            self.state["lat"] = event.status.get("Latitude", 0)
            self.state["long"] = event.status.get("Longitude", 0)

            if self.state["scans"] and self.state.get('scan_radius', False):
                in_scan_radius = False
                if (self.state["lat"] != 0 and self.state["long"] != 0 and
                    event.status.get('PlanetRadius', False)):
                    distance_obj = {'lat': self.state["lat"], 'long': self.state["long"]}
                    for scan in self.state["scans"]:
                        distance = self.haversine_distance(scan, distance_obj, event.status['PlanetRadius'])
                        # self.state["distance"] = distance
                        # log('info', 'distance', distance)
                        if distance < self.state['scan_radius']:
                            in_scan_radius = True
                            break
                    if in_scan_radius:
                        if not self.state['within_scan_radius']:
                            projected_events.append(ProjectedEvent(content={"event": "ScanOrganicTooClose"}))
                            self.state['within_scan_radius'] = in_scan_radius
                    else:
                        if self.state['within_scan_radius']:
                            projected_events.append(ProjectedEvent(content={"event": "ScanOrganicFarEnough"}))
                            self.state['within_scan_radius'] = in_scan_radius
                else:
                    # log('info', 'status missing')
                    if self.state['scans']:
                        self.state["scans"].clear()
                        self.state.pop("scan_radius")


        if isinstance(event, GameEvent) and event.content.get('event') == 'ScanOrganic':
            content = event.content
            if content["ScanType"] == "Log":
                self.state['scans'].clear()
                self.state['scans'].append({'lat': self.state.get('lat', 0), 'long': self.state.get('long', 0)})
                self.state['scan_radius'] = self.colony_size[content['Genus'][11:-1]]
                species = event.content.get('Species_Localised', event.content.get('Species', 'unknown species'))
                variant = event.content.get('Variant_Localised', event.content.get('Variant', ''))
                if variant and variant != species:
                    life_form = f"{variant} ({species})"
                else:
                    life_form = f"{species}"
                self.state['life_form'] = life_form
                self.state['within_scan_radius'] = True
                projected_events.append(ProjectedEvent(content={**content, "event": "ScanOrganicFirst", "NewSampleDistance":self.state['scan_radius']}))

            elif content["ScanType"] == "Sample":
                if len(self.state['scans']) == 1:
                    self.state['scans'].append({'lat': self.state.get('lat', 0), 'long': self.state.get('long', 0)})
                    self.state['within_scan_radius'] = True
                    projected_events.append(ProjectedEvent(content={**content, "event": "ScanOrganicSecond"}))
                elif len(self.state['scans']) == 2:
                    projected_events.append(ProjectedEvent(content={**content, "event": "ScanOrganicThird"}))
                    if self.state['scans']:
                        self.state["scans"].clear()
                        self.state.pop('scan_radius', None)
                else:
                    projected_events.append(ProjectedEvent(content={**content, "event": "ScanOrganic"}))

            elif content["ScanType"] == "Analyse":
                pass

        if isinstance(event, GameEvent) and event.content.get('event') in ['SupercruiseEntry','FSDJump','Died','Shutdown','JoinACrew']:
            self.state["scans"].clear()
            self.state.pop('scan_radius', None)

        return projected_events


# Define types for SuitLoadout Projection
SuitWeaponModule = TypedDict('SuitWeaponModule', {
    "SlotName": str,
    "SuitModuleID": int,
    "ModuleName": str,
    "ModuleName_Localised": str,
    "Class": int,
    "WeaponMods": list[str]
})

SuitLoadoutState = TypedDict('SuitLoadoutState', {
    "SuitID": int,
    "SuitName": str,
    "SuitName_Localised": str,
    "SuitMods": list[str],
    "LoadoutID": int,
    "LoadoutName": str,
    "Modules": list[SuitWeaponModule]
})

@final
class SuitLoadout(Projection[SuitLoadoutState]):
    @override
    def get_default_state(self) -> SuitLoadoutState:
        return {
            "SuitID": 0,
            "SuitName": "Unknown",
            "SuitName_Localised": "Unknown",
            "SuitMods": [],
            "LoadoutID": 0,
            "LoadoutName": "Unknown",
            "Modules": []
        }
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'SuitLoadout':
            # Update the entire state with the new loadout information
            self.state["SuitID"] = event.content.get('SuitID', 0)
            self.state["SuitName"] = event.content.get('SuitName', 'Unknown')
            self.state["SuitName_Localised"] = event.content.get('SuitName_Localised', 'Unknown')
            self.state["SuitMods"] = event.content.get('SuitMods', [])
            self.state["LoadoutID"] = event.content.get('LoadoutID', 0)
            self.state["LoadoutName"] = event.content.get('LoadoutName', 'Unknown')
            
            # Process weapon modules
            modules = []
            for module in event.content.get('Modules', []):
                modules.append({
                    "SlotName": module.get('SlotName', 'Unknown'),
                    "SuitModuleID": module.get('SuitModuleID', 0),
                    "ModuleName": module.get('ModuleName', 'Unknown'),
                    "ModuleName_Localised": module.get('ModuleName_Localised', 'Unknown'),
                    "Class": module.get('Class', 0),
                    "WeaponMods": module.get('WeaponMods', [])
                })
            
            self.state["Modules"] = modules


# Define types for Friends Projection
OnlineFriendsState = TypedDict('OnlineFriendsState', {
    "Online": list[str],  # List of online friend names
    "Pending": list[str]
})


@final
class Friends(Projection[OnlineFriendsState]):
    @override
    def get_default_state(self) -> OnlineFriendsState:
        return {
            "Online": [],
            "Pending": []
        }

    @override
    def process(self, event: Event) -> None:
        # Clear the list on Fileheader event (new game session)
        if isinstance(event, GameEvent) and event.content.get('event') == 'Fileheader':
            self.state["Online"] = []
            self.state["Pending"] = []

        # Process Friends events
        if isinstance(event, GameEvent) and event.content.get('event') == 'Friends':
            friend_name = event.content.get('Name', '')
            friend_status = event.content.get('Status', '')

            # Skip if missing crucial information
            if not friend_name or not friend_status:
                return

            # If the friend is coming online, add them to the list
            if friend_status in ["Online", "Added"]:
                if friend_name not in self.state["Online"]:
                    self.state["Online"].append(friend_name)
                if friend_name in self.state["Pending"]:
                    self.state["Pending"].remove(friend_name)

            elif friend_status == "Requested":
                if friend_name not in self.state["Pending"]:
                    self.state["Pending"].append(friend_name)

            # If the friend was previously online but now has a different status, remove them
            elif friend_name in self.state["Online"] and friend_status in ["Offline", "Lost"]:
                self.state["Online"].remove(friend_name)

            elif friend_status == "Declined":
                if friend_name in self.state["Pending"]:
                    self.state["Pending"].remove(friend_name)


MaterialsCategory = Literal['Raw', 'Manufactured', 'Encoded']

MaterialEntry = TypedDict('MaterialEntry', {
    "Name": str,
    "Count": int,
    "Name_Localised": NotRequired[str]
})

MaterialsState = TypedDict('MaterialsState', {
    "Raw": list[MaterialEntry],
    "Manufactured": list[MaterialEntry],
    "Encoded": list[MaterialEntry],
    "LastUpdated": NotRequired[str]
})


MATERIAL_TEMPLATE: dict[MaterialsCategory, list[MaterialEntry]] = {
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


@final
class Materials(Projection[MaterialsState]):
    MATERIAL_CATEGORIES: tuple[MaterialsCategory, ...] = ('Raw', 'Manufactured', 'Encoded')
    TEMPLATE = MATERIAL_TEMPLATE
    LOOKUP = MATERIAL_NAME_LOOKUP

    @override
    def get_default_state(self) -> MaterialsState:
        return {
            "Raw": [entry.copy() for entry in self.TEMPLATE["Raw"]],
            "Manufactured": [entry.copy() for entry in self.TEMPLATE["Manufactured"]],
            "Encoded": [entry.copy() for entry in self.TEMPLATE["Encoded"]],
            "LastUpdated": ""
        }

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
                self.state["LastUpdated"] = timestamp

        # Apply a delta to the appropriate material entry, creating it if needed.
        def update_material(name: str | None, delta: int, category: str | None = None, localized: str | None = None):
            if not name or delta == 0:
                return
            name_key = name.lower()
            bucket_name = None
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
            bucket = self.state[bucket_name]
            for entry in bucket:
                if entry['Name'].lower() == name_key:
                    entry['Count'] = max(0, entry['Count'] + delta)
                    if localized:
                        entry['Name_Localised'] = localized
                    return
            if delta > 0:
                new_entry: MaterialEntry = {"Name": name, "Count": delta}
                if localized:
                    new_entry["Name_Localised"] = localized
                bucket.append(new_entry)

        if event_name == 'Materials':
            for category in self.MATERIAL_CATEGORIES:
                items = content.get(category, [])
                incoming = {}
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get('Name'):
                            incoming[item['Name']] = item
                bucket = self.state[category]
                for entry in bucket:
                    payload = incoming.pop(entry['Name'], None)
                    if payload:
                        entry['Count'] = payload.get('Count', 0) or 0
                        if payload.get('Name_Localised'):
                            entry['Name_Localised'] = payload['Name_Localised']
                    else:
                        entry['Count'] = 0
                for payload in incoming.values():
                    new_entry: MaterialEntry = {"Name": payload['Name'], "Count": payload.get('Count', 0) or 0}
                    if payload.get('Name_Localised'):
                        new_entry["Name_Localised"] = payload['Name_Localised']
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


ColonisationResourceItem = TypedDict('ColonisationResourceItem', {
    "Name": str,
    "Name_Localised": str,
    "RequiredAmount": int,
    "ProvidedAmount": int,
    "Payment": int
})

ColonisationConstructionState = TypedDict('ColonisationConstructionState', {
    "ConstructionProgress": float,
    "ConstructionComplete": bool,
    "ConstructionFailed": bool,
    "ResourcesRequired": list[ColonisationResourceItem],
    "MarketID": int,
    "StarSystem": str,
    "StarSystemRecall": str
})


@final
class ColonisationConstruction(Projection[ColonisationConstructionState]):
    @override
    def get_default_state(self) -> ColonisationConstructionState:
        return {
            "ConstructionProgress": 0.0,
            "ConstructionComplete": False,
            "ConstructionFailed": False,
            "ResourcesRequired": [],
            "MarketID": 0,
            "StarSystem": "Unknown",
            "StarSystemRecall": "Unknown"
        }

    @override
    def process(self, event: Event) -> None:
        # Process ColonisationConstructionDepot events
        if isinstance(event, GameEvent) and event.content.get('event') == 'ColonisationConstructionDepot':
            # Update construction status
            self.state["ConstructionProgress"] = event.content.get('ConstructionProgress', 0.0)
            self.state["ConstructionComplete"] = event.content.get('ConstructionComplete', False)
            self.state["ConstructionFailed"] = event.content.get('ConstructionFailed', False)
            self.state["MarketID"] = event.content.get('MarketID', 0)

            # Update resources required
            resources = event.content.get('ResourcesRequired', [])
            if resources:
                self.state["ResourcesRequired"] = resources
            self.state["StarSystem"] = self.state["StarSystemRecall"]

        if isinstance(event, GameEvent) and event.content.get('event') == 'Location':
            self.state["StarSystemRecall"] = event.content.get('StarSystem', 'Unknown')

        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseEntry':
            self.state["StarSystemRecall"] = event.content.get('StarSystem', 'Unknown')

        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseExit':
            self.state["StarSystemRecall"] = event.content.get('StarSystem', 'Unknown')

        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump':
            self.state["StarSystemRecall"] = event.content.get('StarSystem', 'Unknown')

@final
class DockingPrompt(Projection[dict[str, Any]]):
    @override
    def get_default_state(self) -> dict[str, Any]:
        return {
            "LastUndockedAt": None,
            "LastStationTarget": None,  # tracked after supercruise exit/drop toward a station
            "LastSupercruiseExit": None,
        }

    def _seconds_between(self, earlier: Any, later: Any) -> float | None:
        """Return seconds between two isoformat timestamps or None on failure/missing."""
        if not earlier or not later:
            return None
        try:
            earlier_dt = datetime.fromisoformat(str(earlier).replace("Z", "+00:00"))
            later_dt = datetime.fromisoformat(str(later).replace("Z", "+00:00"))
            return (later_dt - earlier_dt).total_seconds()
        except Exception:
            return None

    def _is_station_like(self, name: str = "", body_type: str = "", drop_type: str = "") -> bool:
        text = f"{name} {body_type} {drop_type}".lower()
        station_keywords = ["station", "starport", "outpost", "port", "mega ship", "megaship", "settlement", "carrier", "construction site"]
        return any(keyword in text for keyword in station_keywords)


    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        if isinstance(event, GameEvent):
            name = event.content.get("event")
            if name == "Undocked":
                if getattr(event, "historic", False):
                    return projected_events
                ts = event.content.get("timestamp") or event.timestamp
                self.state["LastUndockedAt"] = ts
                self.state["LastStationTarget"] = None
                return projected_events

            if name == "DockingRequested":
                # Manual docking request; clear any pending prompt context to avoid duplicate reminders.
                self.state["LastStationTarget"] = None
                self.state["LastSupercruiseExit"] = None
                return projected_events

            if name in ["DockingGranted", "DockingDenied", "DockingCancelled", "DockingCanceled", "DockingTimeout"]:
                # Docking flow completed/failed; clear context to avoid stale prompts.
                self.state["LastStationTarget"] = None
                self.state["LastSupercruiseExit"] = None
                return projected_events

            if name == "ApproachSettlement":
                body_type = event.content.get("BodyType", "") or event.content.get("StationType", "") or ""
                body_name = event.content.get("BodyName", "") or event.content.get("Body", "") or ""
                target_name = event.content.get("Name_Localised") or event.content.get("Name") or body_name
                market_id = event.content.get("MarketID")
                services = [s.lower() for s in event.content.get("StationServices", [])]
                dockable = any(s in ["dock", "autodock"] for s in services)
                ts = event.content.get("timestamp") or event.timestamp
                self.state["LastSupercruiseExit"] = ts
                # Once we're on a new approach, undock cooldown is no longer relevant.
                self.state["LastUndockedAt"] = None

                if dockable and (market_id or self._is_station_like(target_name, body_type, "")):
                    self.state["LastStationTarget"] = {
                        "name": target_name or body_name,
                        "timestamp": ts,
                        "market_id": market_id,
                        "body_type": body_type,
                        "drop_type": "",
                    }
                else:
                    self.state["LastStationTarget"] = None

            if name == "SupercruiseDestinationDrop":
                body_type = event.content.get("BodyType", "") or ""
                body_name = event.content.get("Body", "") or ""
                drop_type = event.content.get("Type", "") or ""
                target_name = event.content.get("Name_Localised") or event.content.get("Name") or body_name
                market_id = event.content.get("MarketID")
                ts = event.content.get("timestamp") or event.timestamp
                self.state["LastSupercruiseExit"] = ts
                # Once we've dropped toward a destination, undock cooldown is no longer relevant.
                self.state["LastUndockedAt"] = None

                if market_id or self._is_station_like(target_name, body_type, drop_type):
                    self.state["LastStationTarget"] = {
                        "name": target_name or drop_type or body_name,
                        "timestamp": ts,
                        "market_id": market_id,
                        "body_type": body_type,
                        "drop_type": drop_type,
                    }

                else:
                    self.state["LastStationTarget"] = None

            if name == "ReceiveText":
                channel = event.content.get("Channel", "")
                if channel not in ["npc", "station", "local", "starsystem"]:
                    return projected_events

                # Only respond to NFZ if we have an active station approach context
                if not self.state.get("LastStationTarget") and not self.state.get("LastSupercruiseExit"):
                    return projected_events

                message = (
                    event.content.get("Message_Localised")
                    or event.content.get("Message")
                    or ""
                ).lower()
                if "no fire zone entered" not in message:
                    return projected_events

                # We have already prompted based on NFZ warning; clear target so we don't prompt again on mass lock
                self.state["LastStationTarget"] = None
                self.state["LastSupercruiseExit"] = None


                # Skip if we just undocked within the cooldown window
                last_undocked_at = self.state.get("LastUndockedAt")
                if last_undocked_at:
                    try:
                        last_dt = datetime.fromisoformat(
                            str(last_undocked_at).replace("Z", "+00:00")
                        )
                        current_dt = datetime.fromisoformat(
                            str(event.timestamp).replace("Z", "+00:00")
                        )
                        delta = (current_dt - last_dt).total_seconds()
                        if delta < DOCKING_PROMPT_COOLDOWN_SECONDS:
                            return projected_events
                    except Exception:
                        pass


                projected_events.append(ProjectedEvent(content={"event": "PromptDockingRequest"}))

        if isinstance(event, StatusEvent):
            status_event_name = event.status.get("event")
            if status_event_name == "FsdMassLocked":
                target = self.state.get("LastStationTarget") or {}
                target_ts = target.get("timestamp")
                target_age = self._seconds_between(target_ts, event.timestamp)

                last_exit_at = self.state.get("LastSupercruiseExit")
                exit_delta = self._seconds_between(last_exit_at, event.timestamp)

                # Only prompt if mass lock follows a recent station approach after supercruise exit/drop
                last_undocked_at = self.state.get("LastUndockedAt")
                undock_delta = self._seconds_between(last_undocked_at, event.timestamp)
                show_chat_message(
                    "debug",
                    f"[DockingPrompt] FsdMassLocked received; target_age={target_age}, undock_delta={undock_delta}, exit_delta={exit_delta}, target={target}"
                )

                if target_ts and (target_age is None or target_age <= DOCKING_PROMPT_COOLDOWN_SECONDS):
                    if undock_delta is None or undock_delta >= DOCKING_PROMPT_COOLDOWN_SECONDS:
                        projected_events.append(ProjectedEvent(content={"event": "PromptDockingRequest"}))
                        # Avoid duplicate prompts for the same approach
                        self.state["LastStationTarget"] = None
                        self.state["LastSupercruiseExit"] = None
                else:
                    show_chat_message(
                        "debug",
                        "[DockingPrompt] FsdMassLocked ignored (no recent station target or target too old)."
                    )
            if status_event_name == "FsdMassLockEscaped":
                # Leaving mass lock; clear pending prompt context so we don't fire after departing.
                self.state["LastStationTarget"] = None
                self.state["LastSupercruiseExit"] = None
                show_chat_message("debug", "[DockingPrompt] FsdMassLockEscaped observed; cleared station target and exit context.")

        return projected_events



DockingEventsState = TypedDict('DockingEventsState', {
    "StationType": str,
    "LastEventType": str,
    "DockingComputerState": str,
    "Timestamp": str
})

@final
class DockingEvents(Projection[DockingEventsState]):
    @override
    def get_default_state(self) -> DockingEventsState:
        return {
            "StationType": 'Unknown',
            "LastEventType": 'Unknown',
            "DockingComputerState": 'deactivated',
            "Timestamp": "1970-01-01T00:00:00Z"
        }

    @override
    def process(self, event: Event) -> list[ProjectedEvent] | None:
        projected_events: list[ProjectedEvent] = []
        
        if isinstance(event, GameEvent) and event.content.get('event') in ['Docked', 'Undocked', 'DockingGranted', 'DockingRequested', 'DockingCanceled', 'DockingDenied', 'DockingTimeout']:
            self.state['DockingComputerState'] = "deactivated"
            self.state['StationType'] = event.content.get("StationType", "Unknown")
            self.state['LastEventType'] = event.content.get("event", "Unknown")
            if 'timestamp' in event.content:
                self.state['Timestamp'] = event.content['timestamp']

        if isinstance(event, GameEvent) and event.content.get('event') == 'Music':
            if event.content.get('MusicTrack', "Unknown") == "DockingComputer":
                self.state['DockingComputerState'] = 'activated'
                if self.state['LastEventType'] == "DockingGranted":
                    self.state['DockingComputerState'] = "auto-docking"
                    projected_events.append(ProjectedEvent(content={"event": "DockingComputerDocking"}))

                elif self.state['LastEventType'] == "Undocked" and self.state['StationType'] in ['Coriolis', 'Orbis', 'Ocellus']:
                    self.state['DockingComputerState'] = "auto-docking"
                    projected_events.append(ProjectedEvent(content={"event": "DockingComputerUndocking"}))

            elif self.state['DockingComputerState'] == "auto-docking":
                self.state['DockingComputerState'] = "deactivated"
                projected_events.append(ProjectedEvent(content={"event": "DockingComputerDeactivated"}))

        return projected_events

# Define types for InCombat Projection
InCombatState = TypedDict('InCombatState', {
    "InCombat": bool  # Current combat status
})


@final
class InCombat(Projection[InCombatState]):
    @override
    def get_default_state(self) -> InCombatState:
        return {
            "InCombat": False
        }

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
            if self.state["InCombat"] and not is_combat_music:
                # Generate a projected event for leaving combat
                projected_events.append(ProjectedEvent(content={"event": "CombatExited"}))
                self.state["InCombat"] = False
            # Check for transition from non-combat to combat
            elif not self.state["InCombat"] and is_combat_music:
                # Generate a projected event for entering combat
                projected_events.append(ProjectedEvent(content={"event": "CombatEntered"}))
                self.state["InCombat"] = True

        return projected_events


# Define types for Wing Projection
WingState = TypedDict('WingState', {
    "Members": list[str]
})

@final
class Wing(Projection[WingState]):
    @override
    def get_default_state(self) -> WingState:
        return {
            "Members": []
        }

    @override
    def process(self, event: Event) -> None:
        if isinstance(event, GameEvent) and event.content.get('event') == 'WingJoin':
            # Initialize with existing members if any
            others = event.content.get('Others', [])
            if others:
                self.state['Members'] = [member.get('Name', 'Unknown') for member in others]  # type: ignore
            else:
                self.state['Members'] = []
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'WingAdd':
            name = event.content.get('Name', 'Unknown')
            if name and name not in self.state['Members']:
                self.state['Members'].append(name)
        
        if isinstance(event, GameEvent) and event.content.get('event') in ['WingLeave', 'LoadGame']:
            self.state['Members'] = []


FSSSignalsState = TypedDict('FSSSignalsState', {
    "SystemAddress": int,
    
    "FleetCarrier": list[str], 
    "ResourceExtraction": list[str], 
    "Installation": list[str], 
    "NavBeacon": list[str], 
    "TouristBeacon": list[str], 
    "Megaship": list[str], 
    "Generic": list[str], 
    "Outpost": list[str], 
    "Combat": list[str], 
    "Station": list[str],
    "UnknownSignal": list[str],
})

@final
class FSSSignals(Projection[FSSSignalsState]):
    @override
    def get_default_state(self) -> dict:
        return {
            "SystemAddress": 0,
            "FleetCarrier": [],
            "ResourceExtraction": [],
            "Installation": [],
            "NavBeacon": [],
            "TouristBeacon": [],
            "Megaship": [],
            "Generic": [],
            "Outpost": [],
            "Combat": [],
            "Station": [],
            "UnknownSignal": []
        }

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSSSignalDiscovered':
            signal = cast(FSSSignalDiscoveredEvent, event.content)
            signal_type = signal.get("SignalType", "Unknown")
            signal_name = signal.get("SignalName", "Unknown")
            system_address = signal.get("SystemAddress", 0)
            if system_address != self.state.get("SystemAddress", 0):
                # New system, clear previous signals
                self.state = self.get_default_state()
                self.state["SystemAddress"] = system_address
            
            if signal_type in self.state:
                self.state[signal_type].append(signal_name)
            else:
                if signal.get("IsStation"):
                    self.state["Station"].append(signal_name)
                    signal_type = "Station"
                else:
                    self.state["UnknownSignal"].append(signal_name)
                    signal_type = "UnknownSignal"
            
            projected_events.append(ProjectedEvent(content={"event": f"{signal_type}Discovered", "SignalName": signal_name}))
        
        if isinstance(event, GameEvent) and event.content.get('event') in ['FSDJump', 'SupercruiseExit', 'FSSDiscoveryScan']:
            # These indicate that no more signals are discovered immediately, so we could batch on those
            pass
        
        return projected_events

# Define types for Idle Projection
IdleState = TypedDict('IdleState', {
    "LastInteraction": str,  # ISO timestamp of last interaction
    "IsIdle": bool  # Whether the user is currently idle
})

@final
class Idle(Projection[IdleState]):
    def __init__(self, idle_timeout: int):
        super().__init__()
        self.idle_timeout = idle_timeout

    @override
    def get_default_state(self) -> IdleState:
        return {
            "LastInteraction": "1970-01-01T00:00:00Z",  # Default to Unix epoch
            "IsIdle": True
        }

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        # Update last interaction time for any event
        if isinstance(event, ConversationEvent):
            self.state["LastInteraction"] = event.timestamp
            self.state["IsIdle"] = False

        # Check for idle status on Status events
        if (isinstance(event, StatusEvent) or isinstance(event, GameEvent)) and self.state["IsIdle"] == False:
            current_time = event.timestamp
            current_dt = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
            last_interaction = self.state["LastInteraction"]
            last_dt = datetime.fromisoformat(last_interaction.replace('Z', '+00:00'))
            time_delta = (current_dt - last_dt).total_seconds()

            # If more than idle_timeout seconds have passed since last interaction
            if time_delta > self.idle_timeout:
                self.state["IsIdle"] = True
                projected_events.append(ProjectedEvent(content={"event": "Idle"}))

        return projected_events


def registerProjections(event_manager: EventManager, system_db: SystemDatabase, idle_timeout: int):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())
    event_manager.register_projection(Location())
    event_manager.register_projection(Missions())
    event_manager.register_projection(EngineerProgress())
    event_manager.register_projection(CommunityGoal())
    event_manager.register_projection(ShipInfo())
    event_manager.register_projection(Target())
    event_manager.register_projection(NavInfo(system_db))
    event_manager.register_projection(ExobiologyScan())
    event_manager.register_projection(Cargo())
    event_manager.register_projection(Backpack())
    event_manager.register_projection(SuitLoadout())
    event_manager.register_projection(Materials())
    event_manager.register_projection(Friends())
    event_manager.register_projection(ColonisationConstruction())
    event_manager.register_projection(DockingEvents())
    event_manager.register_projection(InCombat())
    event_manager.register_projection(Wing())
    event_manager.register_projection(FSSSignals())
    event_manager.register_projection(DockingPrompt())
    event_manager.register_projection(Idle(idle_timeout))
    event_manager.register_projection(StoredModules())
    event_manager.register_projection(StoredShips())

    # ToDo: SLF, SRV,
    for proj in [
        'Commander',
        'ModuleInfo',
        'Rank',
        'Progress',
        'Reputation',
        'SquadronStartup',
        'Statistics',
        'Powerplay',
        'ShipLocker',
        'Loadout',
        'Shipyard',
        'Market',
        'Outfitting',
        'Shipyard',
    ]:
        p = latest_event_projection_factory(proj, proj)
        event_manager.register_projection(p())
