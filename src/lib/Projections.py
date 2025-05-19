import math
from typing import Any, Literal, TypedDict, final
from datetime import datetime, timezone, timedelta

from typing_extensions import NotRequired, override

from .Event import Event, StatusEvent, GameEvent, ProjectedEvent
from .EventManager import EventManager, Projection
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


LocationState = TypedDict('LocationState', {
    "StarSystem": str,
    "Star": NotRequired[str],
    "Planet": NotRequired[str],
    "PlanetaryRing": NotRequired[str],
    "StellarRing": NotRequired[str],
    "Station": NotRequired[str],
    "AsteroidCluster": NotRequired[str],
    "Docked": NotRequired[Literal[True]],
    "Landed": NotRequired[Literal[True]], # only set when true
    "NearestDestination": NotRequired[str], # only when landed on a planet
})

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
                total_items = 0
                
                for item in event.content.get('Inventory', []):
                    self.state['Inventory'].append({
                        "Name": item.get('Name_Localised', item.get('Name', 'Unknown')),
                        "Count": item.get('Count', 0),
                        "Stolen": item.get('Stolen', 0) > 0
                    })
                    total_items += item.get('Count', 0)
                
                self.state['TotalItems'] = total_items

        # Get cargo capacity from Loadout event
        if isinstance(event, GameEvent) and event.content.get('event') == 'Loadout':
            self.state['Capacity'] = event.content.get('CargoCapacity', 0)
            
        # Update from Status event
        if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
            if 'Cargo' in event.status:
                self.state['TotalItems'] = event.status.get('Cargo', 0)

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
            
            self.state = {
                "StarSystem": star_system,
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
            }
                
        if isinstance(event, GameEvent) and event.content.get('event') == 'SupercruiseExit':
            star_system = event.content.get('StarSystem', 'Unknown')
            body_type = event.content.get('BodyType', 'Null')
            body = event.content.get('Body', 'Unknown')
            
            self.state = {
                "StarSystem": star_system,
            }
            if body_type and body_type != 'Null':
                self.state[body_type] = body
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump':
            star_system = event.content.get('StarSystem', 'Unknown')
            body_type = event.content.get('BodyType', 'Null')
            body = event.content.get('Body', 'Unknown')
            self.state = {
                "StarSystem": star_system,
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


ShipInfoState = TypedDict('ShipInfoState', {
    "Name": str,
    "Type": str,
    "ShipIdent": str,
    "UnladenMass": float,
    "Cargo": float,
    "CargoCapacity": float,
    "FuelMain": float,
    "FuelMainCapacity": float,
    "FuelReservoir": float,
    "FuelReservoirCapacity": float,
    "MaximumJumpRange": float,
    #"CurrentJumpRange": float,
    "LandingPadSize": Literal['S', 'M', 'L', 'Unknown'],
    "IsMiningShip": bool,
})

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
    'typex':                         'M',
    'typex_2':                       'M',
    'typex_3':                       'M',
    'viper':                         'S',
    'viper_mkiv':                    'S',
    'vulture':                       'S',
}

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
            "FuelMain": 0,
            "FuelMainCapacity": 0,
            "FuelReservoir": 0,
            "FuelReservoirCapacity": 0,
            "MaximumJumpRange": 0,
            #"CurrentJumpRange": 0,
            "IsMiningShip": False,
            "LandingPadSize": 'Unknown',
        }
    
    @override
    def process(self, event: Event) -> None:
        if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
            status: Status = event.status  # pyright: ignore[reportAssignmentType]
            if 'Cargo' in event.status:
                self.state['Cargo'] = event.status.get('Cargo', 0)
                
            if 'Fuel' in status and status['Fuel']:
                self.state['FuelMain'] = status['Fuel'].get('FuelMain', 0)
                self.state['FuelReservoir'] = status['Fuel'].get('FuelReservoir', 0)
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'Loadout':
            # { "timestamp":"2024-07-12T21:01:20Z", "event":"Loadout", "Ship":"empire_courier", "ShipID":88, "ShipName":" ", "ShipIdent":"TR-12E", "HullValue":2542931, "ModulesValue":9124352, "HullHealth":1.000000, "UnladenMass":61.713188, "CargoCapacity":0, "MaxJumpRange":50.628967, "FuelCapacity":{ "Main":12.000000, "Reserve":0.410000 }, "Rebuy":583368,
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
                self.state['MaximumJumpRange'] = event.content.get('MaxJumpRange', 0)
            if 'Modules' in event.content:
                has_refinery = any(module["Item"].startswith("int_refinery") for module in event.content["Modules"])
                if has_refinery:
                    self.state['IsMiningShip'] = True
                else:
                    self.state['IsMiningShip'] = False

        if isinstance(event, GameEvent) and event.content.get('event') == 'Cargo':
            self.state['Cargo'] = event.content.get('Cargo', 0)
            self.state['CargoCapacity'] = len(event.content.get('Inventory', []))

        if self.state['Type'] != 'Unknown':
            self.state['LandingPadSize'] = ship_sizes.get(self.state['Type'], 'Unknown')

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
    def process(self, event: Event) -> None:
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
                    self.state["Bounty"] = event.content.get('Bounty', '')
                if event.content.get('Subsystem_Localised', False):
                    self.state["Subsystem"] = event.content.get('Subsystem_Localised', '')
            self.state['EventID'] = event.content.get('id')


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
            # Calculate remaining jumps based on fuel
            fuel_level = event.content.get('FuelLevel', 0)
            fuel_used = event.content.get('FuelUsed', 0)
            remaining_jumps = int(fuel_level / fuel_used)

            # Check if we have enough scoopable stars between current and destination system)
            if remaining_jumps < len(self.state['NavRoute'])-1:
                if remaining_jumps == 0:
                    remaining_jumps = 1
                # Count scoopable stars in the remaining jumps
                scoopable_stars = sum(
                    1 for entry in self.state['NavRoute'][:remaining_jumps][:-1]
                    if entry.get('Scoopable', False)
                )

                # Only warn if we can't reach any scoopable stars
                if scoopable_stars == 0:
                    projected_events.append(ProjectedEvent({"event": "NotEnoughFuel"}))

            for index, entry in enumerate(self.state['NavRoute']):
                if entry['StarSystem'] == event.content.get('StarSystem'):
                    self.state['NavRoute'] = self.state['NavRoute'][index+1:]
                    break

            if len(self.state['NavRoute']) == 0 and 'NextJumpTarget' in self.state:
                self.state.pop('NextJumpTarget')

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
    "DockingComputerState": str
})

@final
class DockingEvents(Projection[DockingEventsState]):
    @override
    def get_default_state(self) -> DockingEventsState:
        return {
            "StationType": 'Unknown',
            "LastEventType": 'Unknown',
            "DockingComputerState": 'deactivated'
        }

    @override
    def process(self, event: Event) -> list[ProjectedEvent] | None:
        projected_events: list[ProjectedEvent] = []
        if isinstance(event, GameEvent) and event.content.get('event') in ['DockingGranted', 'Undocked', 'DockingRequested', 'DockingCanceled', 'DockingDenied', 'DockingTimeout']:
            self.state['DockingComputerState'] = "deactivated"
            self.state['StationType'] = event.content.get("StationType", "Unknown")
            self.state['LastEventType'] = event.content.get("event", "Unknown")

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

def registerProjections(event_manager: EventManager, system_db: SystemDatabase):

    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())
    event_manager.register_projection(Location())
    event_manager.register_projection(Missions())
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

    # ToDo: SLF, SRV,
    for proj in [
        'Commander',
        'Materials',
        'ModuleInfo',
        'Rank',
        'Progress',
        'Reputation',
        'EngineerProgress',
        'SquadronStartup',
        'Statistics',
        'Powerplay',
        'ShipLocker',
        'Loadout',
        'Shipyard',
        'StoredShips',
        'Market',
        'Outfitting',
        'Shipyard',
    ]:
        p = latest_event_projection_factory(proj, proj)
        event_manager.register_projection(p())
