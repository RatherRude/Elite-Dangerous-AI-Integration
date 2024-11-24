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
        

# class Location(Projection):
#     @override
#     def get_default_state(self) -> dict[str, Any]:
#         return {"StarSystem": None}
#
#     @override
#     def process(self, event: Event) -> None:
#         if isinstance(event, GameEvent) and event.content.get('event') == 'Location':
#             location = {
#   "timestamp": "2024-11-10T15:47:05Z",
#   "event": "Location",
#   "DistFromStarLS": 507.757003,
#   "Docked": True,
#   "StationName": "Smith Landing",
#   "StationType": "Coriolis",
#   "MarketID": 3229680640,
#   "StationFaction": {
#     "Name": "Congressus Tenebris",
#     "FactionState": "Boom"
#   },
#   "StationGovernment": "$government_Corporate;",
#   "StationGovernment_Localised": "Corporate",
#   "StationServices": [
#     "dock",
#     "autodock",
#     "commodities",
#     "contacts",
#     "exploration",
#     "missions",
#     "outfitting",
#     "crewlounge",
#     "rearm",
#     "refuel",
#     "repair",
#     "shipyard",
#     "tuning",
#     "engineer",
#     "missionsgenerated",
#     "flightcontroller",
#     "stationoperations",
#     "powerplay",
#     "searchrescue",
#     "stationMenu",
#     "shop",
#     "livery",
#     "socialspace",
#     "bartender",
#     "vistagenomics",
#     "pioneersupplies",
#     "apexinterstellar",
#     "frontlinesolutions"
#   ],
#   "StationEconomy": "$economy_Industrial;",
#   "StationEconomy_Localised": "Industrial",
#   "StationEconomies": [
#     {
#       "Name": "$economy_Industrial;",
#       "Name_Localised": "Industrial",
#       "Proportion": 1.000000
#     }
#   ],
#   "Taxi": False,
#   "Multicrew": False,
#   "StarSystem": "HIP 38747",
#   "SystemAddress": 491547265379,
#   "StarPos": [
#     111.71875,
#     25.84375,
#     -95.03125
#   ],
#   "SystemAllegiance": "Independent",
#   "SystemEconomy": "$economy_Industrial;",
#   "SystemEconomy_Localised": "Industrial",
#   "SystemSecondEconomy": "$economy_Extraction;",
#   "SystemSecondEconomy_Localised": "Extraction",
#   "SystemGovernment": "$government_Corporate;",
#   "SystemGovernment_Localised": "Corporate",
#   "SystemSecurity": "$SYSTEM_SECURITY_medium;",
#   "SystemSecurity_Localised": "Medium Security",
#   "Population": 2420624,
#   "Body": "Smith Landing",
#   "BodyID": 33,
#   "BodyType": "Station",
#   "ControllingPower": "Felicia Winters",
#   "Powers": [
#     "Felicia Winters"
#   ],
#   "PowerplayState": "Stronghold",
#   "Factions": [
#     {
#       "Name": "HIP 38747 & Co",
#       "FactionState": "None",
#       "Government": "Corporate",
#       "Influence": 0.038268,
#       "Allegiance": "Independent",
#       "Happiness": "$Faction_HappinessBand2;",
#       "Happiness_Localised": "Happy",
#       "MyReputation": 0.000000
#     },
#     {
#       "Name": "Workers of HIP 38747 Progressive Party",
#       "FactionState": "None",
#       "Government": "Democracy",
#       "Influence": 0.030211,
#       "Allegiance": "Independent",
#       "Happiness": "$Faction_HappinessBand2;",
#       "Happiness_Localised": "Happy",
#       "MyReputation": 0.000000
#     },
#     {
#       "Name": "Defence Force of HIP 38747",
#       "FactionState": "None",
#       "Government": "Dictatorship",
#       "Influence": 0.034240,
#       "Allegiance": "Independent",
#       "Happiness": "$Faction_HappinessBand2;",
#       "Happiness_Localised": "Happy",
#       "MyReputation": 0.000000
#     },
#     {
#       "Name": "Silver United Co",
#       "FactionState": "None",
#       "Government": "Corporate",
#       "Influence": 0.024169,
#       "Allegiance": "Independent",
#       "Happiness": "$Faction_HappinessBand2;",
#       "Happiness_Localised": "Happy",
#       "MyReputation": 0.000000
#     },
#     {
#       "Name": "Congressus Tenebris",
#       "FactionState": "Boom",
#       "Government": "Corporate",
#       "Influence": 0.779456,
#       "Allegiance": "Independent",
#       "Happiness": "$Faction_HappinessBand2;",
#       "Happiness_Localised": "Happy",
#       "MyReputation": 15.000000,
#       "PendingStates": [
#         {
#           "State": "Expansion",
#           "Trend": 0
#         }
#       ],
#       "ActiveStates": [
#         {
#           "State": "Boom"
#         }
#       ]
#     },
#     {
#       "Name": "Wraith Shipping",
#       "FactionState": "None",
#       "Government": "Cooperative",
#       "Influence": 0.093656,
#       "Allegiance": "Independent",
#       "Happiness": "$Faction_HappinessBand2;",
#       "Happiness_Localised": "Happy",
#       "MyReputation": 0.000000
#     }
#   ],
#   "SystemFaction": {
#     "Name": "Congressus Tenebris",
#     "FactionState": "Boom"
#   }
# }
#
#             new_projection = {
#                 "system": {
#                     "name": location["StarSystem"],
#                     "allegiance": {
#                         "superPower": "",
#                         "power": "",
#                         "faction": ""
#                     },
#                     "economy": location["SystemEconomy_Localised"],
#                     "second_economy": location["SystemSecondEconomy_Localised"],
#                     "government": location["SystemGovernment_Localised"],
#                     "security": location["SystemSecurity_Localised"],
#                     "population": location["Population"],
#                 },
#                 "station": {
#                     "name": location["Body"],
#                     "type": location["BodyType"],
#                     "government": location["StationGovernment_Localised"],
#                     "economy": location["SystemEconomy_Localised"], # secondary economy?
#                 },
#                 "body": {
#                     "name": location["Body"],
#                     "type": location["BodyType"],
#                     "coordinates": {
#                         "latitude": 0,
#                         "longitude": 0,
#                         "altitude": 0,
#                     }
#                 },
#                 "settlement": {
#
#                 },
#                 "factions": [
#                     {
#                         "name": location["Factions"][0]["Name"],
#                         "state": location["Factions"][0]["FactionState"],
#                         "reputation": location["Factions"][0]["MyReputation"]
#                     }
#                 ]
#             }
#
#             self.state = new_projection


def registerProjections(event_manager: EventManager):
    event_manager.register_projection(EventCounter())
    event_manager.register_projection(CurrentStatus())
    event_manager.register_projection(Location())

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
