import math
import re
import traceback
from typing import Any, Literal, TypedDict, final, List, cast
from datetime import datetime, timezone, timedelta
from webbrowser import get

from typing_extensions import NotRequired, override

from .Event import Event, StatusEvent, GameEvent, ProjectedEvent, ExternalEvent, ConversationEvent, ToolEvent
from .EventManager import EventManager, Projection
from .Logger import log
from .EDFuelCalc import RATING_BY_CLASSNUM , FSD_OVERCHARGE_STATS ,FSD_OVERCHARGE_V2PRE_STATS, FSD_STATS ,FSD_GUARDIAN_BOOSTER
from .StatusParser import parse_status_flags, parse_status_json, Status
from .SystemDatabase import SystemDatabase


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
    'diamondback':                   'S',
    'diamondbackxl':                 'S',
    'dolphin':                       'S',
    'eagle':                         'S',
    'empire_courier':                'S',
    'empire_eagle':                  'S',
    'empire_fighter':                'Unknown',
    'empire_trader':                 'L',
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
    'corsair':                       'M',
    'orca':                          'L',
    'python':                        'M',
    'python_nx':                     'M',
    'scout':                         'Unknown',
    'sidewinder':                    'S',
    'testbuggy':                     'Unknown',
    'type6':                         'M',
    'type7':                         'L',
    'type8':                         'L',
    'type9':                         'L',
    'type9_military':                'L',
    'panthermkii':                   'L',
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
            "DriveOptimalMass": 0,
            "DriveLinearConst":0,
            "GuardianfsdBooster":0,
            "DrivePowerConst":0,
            "DriveMaxFuel":0,
            "JetConeBoost":1,
            "IsMiningShip": False,
            "hasLimpets": False,
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

                has_limpets = any(module["Item"].startswith("int_dronecontrol") for module in event.content["Modules"])
                if has_limpets:
                    self.state['hasLimpets'] = True
                else:
                    self.state['hasLimpets'] = False

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

                    all_module_stats = FSD_OVERCHARGE_STATS if over else FSD_STATS
                    module_stat: dict = all_module_stats.get((module_size, module_rating))
                    self.state['DriveOptimalMass'] = engineering_optimal_mass_override if engineering_optimal_mass_override is not None else module_stat.get('opt_mass', 0.00)
                    self.state['DriveMaxFuel'] = engineering_max_fuel_override if engineering_max_fuel_override is not None else module_stat.get('max_fuel', 0.00)
                    self.state['DriveLinearConst'] = module_stat.get('linear_const', 0.0)
                    self.state['DrivePowerConst'] = module_stat.get('power_const', 0.0)
                    
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
        
        if isinstance(event,GameEvent) and event.content.get('event') == 'FSDJump':
            self.state['JetConeBoost'] = 1
        
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Cargo':
            self.state['Cargo'] = event.content.get('Count', 0)
            if event.content.get('Vessel') == 'Ship': 
                self.state['ShipCargo'] = event.content.get('Count', 0)

        if isinstance(event, GameEvent) and event.content.get('event') in ['RefuelAll','RepairAll','BuyAmmo']:
            if self.state['hasLimpets'] and self.state['Cargo'] < self.state['CargoCapacity']:
                projected_events.append(ProjectedEvent({"event": "RememberLimpets"}))

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
        maximum_jump_range     = self.state.get("MaximumJumpRange")
        drive_power_const   = self.state.get("DrivePowerConst")
        drive_optimal_mass = self.state.get("DriveOptimalMass")
        drive_linear_const  = self.state.get("DriveLinearConst") 
        drive_max_fuel  = self.state.get("DriveMaxFuel")
        fsd_star_boost = self.state.get("JetConeBoost")
        fsd_boost = self.state.get("GuardianfsdBooster")
        fsd_inject = 0 # +inject juice 25% , 50% ,100% but cant be with star_boost

        if not (unladen_mass > 0 and fuel_capacity > 0 and maximum_jump_range > 0 and drive_max_fuel):
            return 0, 0, 0

        current_cargo = self.state.get("ShipCargo")
        current_fuel  = self.state.get("FuelMain")
        current_fuel_reservoir = self.state.get("FuelReservoir")

        minimal_mass = unladen_mass + drive_max_fuel  #max jump with just right anmount
        current_mass = unladen_mass + current_cargo + current_fuel + current_fuel_reservoir  #current mass
        maximal_mass = unladen_mass + cargo_capacity + fuel_capacity  # minimal jump with min mass
        log('info', 'minimal_mass', minimal_mass)
        log('info', 'current_mass', current_mass)
        log('info', 'maximal_mass', maximal_mass)
        
        base = lambda M: (drive_optimal_mass / M) * ( (10**3 * drive_max_fuel) / drive_linear_const )**(1/drive_power_const)
        # adding stuff here for more future fsd boost stuff 
        min_ly = (base(maximal_mass) + fsd_boost) * fsd_star_boost
        cur_ly = (base(current_mass) + fsd_boost) * fsd_star_boost
        max_ly = (base(minimal_mass) + fsd_boost) * fsd_star_boost
        
        return min_ly, cur_ly, max_ly

TargetState = TypedDict('TargetState', {
    "EventID": NotRequired[str],
    "Ship":NotRequired[str],
    "Scanned":NotRequired[bool],

    "PilotName":NotRequired[str],
    "PilotRank":NotRequired[str],
    "Faction":NotRequired[str],
    "LegalStatus":NotRequired[str],
    "Bounty": NotRequired[int],

    "Subsystem":NotRequired[str],
})


@final
class Target(Projection[TargetState]):
    @override
    def get_default_state(self) -> TargetState|None:
        return {}

    @override
    def process(self, event: Event) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []

        global keys
        if isinstance(event, GameEvent) and event.content.get('event') == 'LoadGame':
            self.state = self.get_default_state()
        if isinstance(event, GameEvent) and event.content.get('event') == 'ShipTargeted':
            if not event.content.get('TargetLocked', False):
                self.state = self.get_default_state()
            else:
                # self.state['SubsystemToTarget'] = 'Drive'
                self.state['Ship'] = event.content.get('Ship', '')
                if event.content.get('ScanStage', 0) < 3:
                    self.state['Scanned'] = False
                else:
                    self.state['Scanned'] = True
                    self.state["PilotName"] = event.content.get('PilotName_Localised', '')
                    self.state["PilotRank"] = event.content.get('PilotRank', '')
                    self.state["Faction"] = event.content.get('Faction', '')
                    self.state["LegalStatus"] = event.content.get('LegalStatus', '')
                    self.state["Bounty"] = event.content.get('Bounty', 0)

                    if (event.content.get('Bounty', 0) > 1 and not event.content.get('Subsystem', False)):
                        projected_events.append(ProjectedEvent({"event": "BountyScanned"}))
                if event.content.get('Subsystem_Localised', False):
                    self.state["Subsystem"] = event.content.get('Subsystem_Localised', '')
            self.state['EventID'] = event.content.get('id')
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
                if systems_to_lookup:
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
                    projected_events.append(ProjectedEvent({"event": "NoScoopableStars"}))

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
                            projected_events.append(ProjectedEvent({"event": "ScanOrganicTooClose"}))
                            self.state['within_scan_radius'] = in_scan_radius
                    else:
                        if self.state['within_scan_radius']:
                            projected_events.append(ProjectedEvent({"event": "ScanOrganicFarEnough"}))
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
                projected_events.append(ProjectedEvent({**content, "event": "ScanOrganicFirst", "NewSampleDistance":self.state['scan_radius']}))

            elif content["ScanType"] == "Sample":
                if len(self.state['scans']) == 1:
                    self.state['scans'].append({'lat': self.state.get('lat', 0), 'long': self.state.get('long', 0)})
                    self.state['within_scan_radius'] = True
                    projected_events.append(ProjectedEvent({**content, "event": "ScanOrganicSecond"}))
                elif len(self.state['scans']) == 2:
                    projected_events.append(ProjectedEvent({**content, "event": "ScanOrganicThird"}))
                    if self.state['scans']:
                        self.state["scans"].clear()
                        self.state.pop('scan_radius', None)
                else:
                    projected_events.append(ProjectedEvent({**content, "event": "ScanOrganic"}))

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
    "Online": list[str]  # List of online friend names
})


@final
class Friends(Projection[OnlineFriendsState]):
    @override
    def get_default_state(self) -> OnlineFriendsState:
        return {
            "Online": []
        }

    @override
    def process(self, event: Event) -> None:
        # Clear the list on Fileheader event (new game session)
        if isinstance(event, GameEvent) and event.content.get('event') == 'Fileheader':
            self.state["Online"] = []

        # Process Friends events
        if isinstance(event, GameEvent) and event.content.get('event') == 'Friends':
            friend_name = event.content.get('Name', '')
            friend_status = event.content.get('Status', '')

            # Skip if missing crucial information
            if not friend_name or not friend_status:
                return

            # If the friend is coming online, add them to the list
            if friend_status == "Online":
                if friend_name not in self.state["Online"]:
                    self.state["Online"].append(friend_name)

            # If the friend was previously online but now has a different status, remove them
            elif friend_name in self.state["Online"]:
                self.state["Online"].remove(friend_name)


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
                    projected_events.append(ProjectedEvent({"event": "DockingComputerDocking"}))

                elif self.state['LastEventType'] == "Undocked" and self.state['StationType'] in ['Coriolis', 'Orbis', 'Ocellus']:
                    self.state['DockingComputerState'] = "auto-docking"
                    projected_events.append(ProjectedEvent({"event": "DockingComputerUndocking"}))

            elif self.state['DockingComputerState'] == "auto-docking":
                self.state['DockingComputerState'] = "deactivated"
                projected_events.append(ProjectedEvent({"event": "DockingComputerDeactivated"}))

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
                projected_events.append(ProjectedEvent({"event": "CombatExited"}))
                self.state["InCombat"] = False
            # Check for transition from non-combat to combat
            elif not self.state["InCombat"] and is_combat_music:
                # Generate a projected event for entering combat
                projected_events.append(ProjectedEvent({"event": "CombatEntered"}))
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
        if isinstance(event, ConversationEvent) and event.kind == 'user':
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
                projected_events.append(ProjectedEvent({"event": "Idle"}))

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
    event_manager.register_projection(Friends())
    event_manager.register_projection(ColonisationConstruction())
    event_manager.register_projection(DockingEvents())
    event_manager.register_projection(InCombat())
    event_manager.register_projection(Wing())
    event_manager.register_projection(Idle(idle_timeout))

    # ToDo: SLF, SRV,
    for proj in [
        'Commander',
        'Materials',
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
        'StoredShips',
        'StoredModules',
        'Market',
        'Outfitting',
        'Shipyard',
    ]:
        p = latest_event_projection_factory(proj, proj)
        event_manager.register_projection(p())
