from typing import Any, Generic, Literal, TypeVar, TypedDict, final
from typing_extensions import NotRequired, override
from .StatusParser import parse_status_flags, parse_status_json, Status
from .Event import Event, StatusEvent, GameEvent
from .Logger import log
from .EventManager import EventManager, Projection


def latest_event_projection_factory(projectionName: str, gameEvent: str):
    class LatestEvent(Projection):
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
    "Donation": NotRequired[int],
    "TargetFaction": NotRequired[str],
    "DestinationSystem": NotRequired[str],
    "DestinationSettlement": NotRequired[str],
    "DestinationStation": NotRequired[str],
    "Reward": NotRequired[int],
    # TODO: Are there more fields?
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
            if 'TargetFaction' in event.content:
                mission["TargetFaction"] = event.content.get('TargetFaction', 'Unknown')
            if 'DestinationSystem' in event.content:
                mission["DestinationSystem"] = event.content.get('DestinationSystem', 'Unknown')
            if 'DestinationSettlement' in event.content:
                mission["DestinationSettlement"] = event.content.get('DestinationSettlement', 'Unknown')
            if 'DestinationStation' in event.content:
                mission["DestinationStation"] = event.content.get('DestinationStation', 'Unknown')
            if 'Reward' in event.content:
                mission["Reward"] = event.content.get('Reward', 0)
                
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
                if new_destination_settlement:
                    existing_mission["DestinationSettlement"] = new_destination_settlement
            
                self.state["Active"] = [mission for mission in self.state["Active"] if mission["MissionID"] != event.content.get('MissionID', 0)]
                self.state["Active"].append(existing_mission)


def registerProjections(event_manager: EventManager):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())
    event_manager.register_projection(Location())
    event_manager.register_projection(Missions())

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
