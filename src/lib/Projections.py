import math
from typing import Any, Literal, TypedDict, final

from typing_extensions import NotRequired, override

from .Event import Event, StatusEvent, GameEvent, ProjectedEvent
from .EventManager import EventManager, Projection
from .StatusParser import parse_status_flags, parse_status_json, Status


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
            docked = event.content.get('Docked', False)
            
            self.state = {
                "StarSystem": star_system,
                "Docked": docked,
            }
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
            if 'Cargo' in status and status['Cargo']:
                self.state['Cargo'] = status['Cargo']
                
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
        
        if self.state['Type'] != 'Unknown':
            self.state['LandingPadSize'] = ship_sizes.get(self.state['Type'], 'Unknown')
            

NavInfoState = TypedDict('NavInfoState', {
    "NextJumpTarget": NotRequired[str],
    #"NavRouteTarget": NotRequired[str],  # TODO: use the navroute.json to set this
    "JumpsRemaining": NotRequired[int],
    "InJump": NotRequired[bool],
    # TODO: System local targets? (planet, station, etc)
})

@final
class NavInfo(Projection[NavInfoState]):
    @override
    def get_default_state(self) -> NavInfoState:
        return {
            "NextJumpTarget": 'Unknown',
            #"NavRouteTarget": 'Unknown',
            "JumpsRemaining": 0,
        }
    
    @override
    def process(self, event: Event) -> None:
        #if isinstance(event, StatusEvent) and event.status.get('event') == 'Status':
        #    status: Status = event.status  # pyright: ignore[reportAssignmentType]
        #    if 'Destination' in status and status['Destination']:
        #        self.state['Destination'] = status['Destination'].get('Name', 'Unknown')  # TODO: this could be used for system local target, like planets or stations
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDTarget':
            if 'RemainingJumpsInRoute' in event.content:
                self.state['JumpsRemaining'] = event.content.get('RemainingJumpsInRoute', 0)  # TODO: according to comments in the old journal code, this number is wrong when < 3 jumps remain
            if 'Name' in event.content:
                self.state['NextJumpTarget'] = event.content.get('Name', 'Unknown')
            self.state.pop('InJump', None)
        
        if isinstance(event, GameEvent) and event.content.get('event') == 'StartJump':
            self.state['InJump'] = True
            
        if isinstance(event, GameEvent) and event.content.get('event') == 'FSDJump':
            if self.state.get('InJump', False):
                self.state = {} # we ended the jump with no new target, so we arrived
        
        # TODO: when do we clear the route? if 'FSDJump' 'StarSystem' = 'NavRouteTarget'? or if remaining jumps = 0? what if the user clears?

class ExobiologyScanStateScan(TypedDict):
    lat: float
    long: float

ExobiologyScanState = TypedDict('ExobiologyScanState', {
    "within_scan_radius": NotRequired[bool],
    "scan_radius": NotRequired[int],
    "scans": list[ExobiologyScanStateScan],
    "lat": NotRequired[float],
    "long": NotRequired[float]
})

@final
class ExobiologyScan(Projection[ExobiologyScanState]):
    colony_size = {
        "Aleoids_Genus_Name": 150,      # Aleoida
        "Vents_Genus_Name": 100,        # Amphora Plant
        "Sphere_Genus_Name": 100,       # Anemone
        "Bacterial_Genus_Name": 500,    # Bacterium
        "Cone_Genus_Name": 100,         # Bark Mound
        "Brancae_Name": 100,         # Brain Tree
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
            self.state["lat"] = event.status.get("Latitude")
            self.state["long"] = event.status.get("Longitude")

            if self.state["scans"] and self.state.get('scan_radius', False):
                in_scan_radius = False
                if (event.status.get('Latitude', False) and
                    event.status.get('Longitude', False) and
                    event.status.get('PlanetRadius', False)):
                    distance_obj = {'lat': self.state["lat"], 'long': self.state["long"]}
                    for scan in self.state["scans"]:
                        distance = self.haversine_distance(scan, distance_obj, event.status['PlanetRadius'])
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
                self.state['within_scan_radius'] = True
                projected_events.append(ProjectedEvent({**content, "event": "ScanOrganicFirst", "NewSampleDistance":self.state['scan_radius']}))

            elif content["ScanType"] == "Sample":
                if len(self.state['scans']) == 1:
                    self.state['scans'].append({'lat': self.state.get('lat', 0), 'long': self.state.get('long', 0)})
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



def registerProjections(event_manager: EventManager):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())
    event_manager.register_projection(Location())
    event_manager.register_projection(Missions())
    event_manager.register_projection(ShipInfo())
    event_manager.register_projection(NavInfo())
    event_manager.register_projection(ExobiologyScan())

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
    ]:
        p = latest_event_projection_factory(proj, proj)
        event_manager.register_projection(p())
